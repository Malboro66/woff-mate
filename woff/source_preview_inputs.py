"""Read only explicit, preacquired copies from the legacy private R0 manifest.

This is not the production ingestion/snapshot reader. Original-location fields
are used lexically for exclusion and are never opened, resolved or enumerated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import contextlib
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
from typing import Iterator
from uuid import NAMESPACE_OID, uuid5

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 512 * 1024
MAX_RECORDS = 10000
REQUIRED_ALIASES = tuple(f"S-{i:02d}" for i in range(1, 7)) + ("M-01",) + tuple(
    f"{family}-{i:02d}" for family in ("D", "C") for i in range(1, 7)
)
_CATEGORIES = {"S": "PilotSquads", "M": "Mission.log", "D": "Dossier", "C": "PilotClaims"}
_BASENAMES = {
    "S": re.compile(r"Pilot[0-9]+Squads\.txt", re.IGNORECASE),
    "M": re.compile(r"Mission\.log", re.IGNORECASE),
    "D": re.compile(r"Pilot[0-9]+Dossier\.txt", re.IGNORECASE),
    "C": re.compile(r"Pilot[0-9]+Claims\.txt", re.IGNORECASE),
}


class CopyInputError(Exception):
    """Closed internal codes only; never retain an underlying exception."""

    def __init__(self, code: str) -> None:
        if code not in {"manifest", "missing", "unsafe", "integrity", "limit", "unreadable"}:
            raise ValueError("Unknown input failure")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, repr=False)
class CopySource:
    alias: str
    category: str
    path: Path = field(repr=False)
    basename: str = field(repr=False)
    sha256: str = field(repr=False)
    generation: str


def _path(raw: str) -> Path:
    if type(raw) is not str or not raw or any(ord(c) < 32 for c in raw):
        raise CopyInputError("unsafe")
    windows = PureWindowsPath(raw)
    if raw.startswith(("\\", "//")) or ".." in windows.parts or ".." in Path(raw).parts:
        raise CopyInputError("unsafe")
    # A local drive prefix is the only colon permitted (no alternate streams).
    tail = raw[2:] if re.match(r"^[A-Za-z]:", raw) else raw
    if ":" in tail or (windows.drive and not windows.is_absolute()):
        raise CopyInputError("unsafe")
    for part in windows.parts[1:] if windows.anchor else windows.parts:
        if (part.endswith((".", " ")) or
                part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
            raise CopyInputError("unsafe")
    return Path(os.path.abspath(raw))


def _signature(value: os.stat_result) -> tuple[int, ...]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
            value.st_ctime_ns, value.st_nlink, getattr(value, "st_file_attributes", 0))


def _check_components(path: Path) -> os.stat_result:
    result = None
    for component in (*reversed(path.parents), path):
        result = component.lstat()
        if stat.S_ISLNK(result.st_mode) or getattr(result, "st_file_attributes", 0) & 0x400:
            raise CopyInputError("unsafe")
        if component != path and not stat.S_ISDIR(result.st_mode):
            raise CopyInputError("unsafe")
    assert result is not None
    if not stat.S_ISREG(result.st_mode) or result.st_nlink != 1:
        raise CopyInputError("unsafe")
    return result


def _windows_open(path: Path, *, directory: bool = False) -> int:
    if sys.platform != "win32":
        raise CopyInputError("unsafe")
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                      wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    # Native read handles participate in the same opt-in subprocess access
    # audit as os.open. No write-capable native API is used by this reader.
    sys.audit("open", str(path), "r", os.O_RDONLY)
    # OPEN_REPARSE_POINT prevents following the final component. Locked parent
    # handles below protect intermediate components from namespace replacement.
    handle = create(str(path), 0 if directory else 0x80000000,
                    3 if directory else 1, None, 3,
                    0x00200000 | (0x02000000 if directory else 0), None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        if error in (2, 3):
            raise FileNotFoundError("Copy unavailable")
        raise OSError(error, "Read-only copy access failed")
    return handle


def _windows_close(handle: int) -> None:
    if sys.platform != "win32":
        raise CopyInputError("unsafe")
    import ctypes
    from ctypes import wintypes
    close = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    close(handle)


@contextlib.contextmanager
def _locked_parents(path: Path) -> Iterator[None]:
    handles: list[int] = []
    try:
        if os.name == "nt":
            for component in reversed(path.parents):
                # No FILE_SHARE_DELETE: hold each directory before advancing.
                # A reparse point opened as itself is rejected before traversing.
                handles.append(_windows_open(component, directory=True))
                info = component.lstat()
                if getattr(info, "st_file_attributes", 0) & 0x400:
                    raise CopyInputError("unsafe")
        yield
    finally:
        for handle in reversed(handles):
            _windows_close(handle)


def _open_read(path: Path) -> int:
    if os.name == "nt":
        import msvcrt
        handle = _windows_open(path)
        try:
            # File share mode is READ only: writes/replacement are denied for
            # this observation, without modifying source permissions or flags.
            return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except Exception:
            _windows_close(handle)
            raise
    return os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))


def _observe(path: Path, limit: int) -> tuple[bytes, tuple[int, ...], tuple[int, ...]]:
    with _locked_parents(path):
        return _observe_locked(path, limit)


def _observe_locked(path: Path, limit: int) -> tuple[bytes, tuple[int, ...], tuple[int, ...]]:
    before = _check_components(path)
    if before.st_size <= 0 or before.st_size > limit:
        raise CopyInputError("limit")
    descriptor = _open_read(path)
    try:
        fd_before = os.fstat(descriptor)
        if not stat.S_ISREG(fd_before.st_mode) or fd_before.st_nlink != 1:
            raise CopyInputError("unsafe")
        # Compare identity/size only across descriptor/path views. ctime is
        # compared only within its own view, including on native Windows.
        if (before.st_dev, before.st_ino, before.st_size) != (
                fd_before.st_dev, fd_before.st_ino, fd_before.st_size):
            raise CopyInputError("integrity")
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        fd_after = os.fstat(descriptor)
        after = _check_components(path)
        if len(data) > limit:
            raise CopyInputError("limit")
        if (len(data) != before.st_size or _signature(before) != _signature(after) or
                _signature(fd_before) != _signature(fd_after)):
            raise CopyInputError("integrity")
        return data, _signature(after), _signature(fd_after)
    finally:
        os.close(descriptor)


def _verified_read(path: Path, limit: int, expected: str | None = None) -> bytes:
    try:
        first = _observe(path, limit)
        second = _observe(path, limit)
        if first != second:
            raise CopyInputError("integrity")
        data = second[0]
        if expected is not None and hashlib.sha256(data).hexdigest() != expected:
            raise CopyInputError("integrity")
        return data
    except CopyInputError:
        raise
    except FileNotFoundError:
        raise CopyInputError("missing") from None
    except OSError:
        raise CopyInputError("unreadable") from None


def _digest(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise CopyInputError("manifest")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CopyInputError("manifest")
        result[key] = value
    return result


class VerifiedCopyInputs:
    """Private paths and digests remain in this reader; no originals are read."""

    def __init__(self, manifest: str) -> None:
        self._manifest = _path(manifest)
        self._manifest_bytes = _verified_read(self._manifest, MAX_MANIFEST_BYTES)
        self._root = self._manifest.parent / "inputs"
        try:
            self._load()
        except CopyInputError:
            raise
        except (ValueError, TypeError, KeyError, RecursionError):
            raise CopyInputError("manifest") from None

    def _load(self) -> None:
        records = json.loads(self._manifest_bytes.decode("utf-8"), object_pairs_hook=_unique_object)
        if type(records) is not list or not 19 <= len(records) <= 64:
            raise CopyInputError("manifest")
        self.dataset_id = str(uuid5(NAMESPACE_OID, hashlib.sha256(self._manifest_bytes).hexdigest()))
        sources = []
        aliases: set[str] = set()
        paths: set[Path] = set()
        original_parents: set[Path] = set()
        for record in records:
            if type(record) is not dict or type(record.get("alias")) is not str:
                raise CopyInputError("manifest")
            alias = record["alias"]
            if alias in aliases:
                raise CopyInputError("manifest")
            aliases.add(alias)
            # Only lexical original locations supply the capture boundary.
            original = record.get("actual_source")
            if type(original) is not str or not Path(original).is_absolute():
                raise CopyInputError("manifest")
            original_parents.add(_path(original).parent)
            if alias not in REQUIRED_ALIASES:
                continue
            family = alias[0]
            basename = record.get("basename")
            if (record.get("category") != _CATEGORIES[family] or type(basename) is not str or
                    _BASENAMES[family].fullmatch(basename) is None):
                raise CopyInputError("manifest")
            if not all(record.get(key) is True for key in (
                    "stable_acquisition", "copy_integrity", "basename_preserved", "readable")):
                raise CopyInputError("manifest")
            expected = _digest(record.get("sha256_before"))
            if record.get("sha256_after") != expected or record.get("copy_sha256") != expected:
                raise CopyInputError("manifest")
            raw_copy = record.get("copied_input")
            if type(raw_copy) is not str or not Path(raw_copy).is_absolute():
                raise CopyInputError("manifest")
            copy = _path(raw_copy)
            if (not copy.is_relative_to(self._root) or copy.name != basename or copy in paths):
                raise CopyInputError("unsafe")
            paths.add(copy)
            sources.append(CopySource(alias, record["category"], copy, basename, expected,
                                     str(uuid5(NAMESPACE_OID, self.dataset_id + alias + expected))))
        if {source.alias for source in sources} != set(REQUIRED_ALIASES):
            raise CopyInputError("manifest")
        repository = Path(__file__).absolute().parent.parent
        if self._root.is_relative_to(repository) or any(
                self._root.is_relative_to(parent) or parent.is_relative_to(self._root)
                for parent in original_parents):
            raise CopyInputError("unsafe")
        by_alias = {source.alias: source for source in sources}
        self.sources = tuple(by_alias[alias] for alias in REQUIRED_ALIASES)
        # Admission does not chmod inputs or infer a readonly file attribute.
        # Integrity is captured-generation equality plus this process's read-only policy.

    def read(self, source: CopySource) -> bytes:
        if source not in self.sources:
            raise CopyInputError("unsafe")
        if _verified_read(self._manifest, MAX_MANIFEST_BYTES) != self._manifest_bytes:
            raise CopyInputError("integrity")
        # Bound the admitted dataset, without opening unrelated acquired copies.
        try:
            total = 0
            for item in self.sources:
                try:
                    total += _check_components(item.path).st_size
                except FileNotFoundError:
                    continue
        except OSError:
            raise CopyInputError("unreadable") from None
        if total > MAX_TOTAL_BYTES:
            raise CopyInputError("limit")
        data = _verified_read(source.path, MAX_FILE_BYTES, source.sha256)
        if len(data.splitlines()) > MAX_RECORDS:
            raise CopyInputError("limit")
        return data
