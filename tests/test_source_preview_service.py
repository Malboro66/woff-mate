"""Fictional input, parser fidelity, safety, privacy and isolation checks."""
from __future__ import annotations

from dataclasses import replace
import ast
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

import pytest

from source_preview_support import mission, replace_source, squads, write_dataset
from woff.source_preview_contracts import (
    DiagnosticPreview, DiagnosticStatus, FieldEvidence, MissionLogPreview,
    PilotSquadsPreview, PreviewFailure, PreviewRequest,
)
from woff.source_preview_inputs import CopyInputError, VerifiedCopyInputs, _path
from woff.source_preview_service import SourcePreviewService
from woff.ui_contracts import RequestId, ScreenState


@pytest.fixture
def dataset(tmp_path):
    return write_dataset(tmp_path)


def query(service, alias):
    source = next(source for source in service.selections if source.alias == alias)
    return service.query(PreviewRequest(source, RequestId("fictional-request")))


def test_six_distinct_copies_exact_fields_last_accepted_and_empty_rank(dataset):
    service = SourcePreviewService(str(dataset))
    selections = [source for source in service.selections if source.alias.startswith("S-")]
    assert [source.alias for source in selections] == [f"S-{i:02d}" for i in range(1, 7)]
    assert len({source.generation for source in selections}) == 6
    for index in range(1, 7):
        snapshot = query(service, f"S-{index:02d}")
        assert snapshot.state is ScreenState.READY
        pilot = snapshot.payload
        assert isinstance(pilot, PilotSquadsPreview)
        assert pilot.squadron.value.value == f"Fictional squadron {index}"
        assert pilot.aircraft.value.value == f"Fictional aircraft {index}"
        assert pilot.aerodrome.value.value == f"Fictional aerodrome {index}"
        assert pilot.sector.value.value == f"Fictional sector {index}"
        assert pilot.source_record_date.value.value == "1917-04-02"
        assert pilot.rank.value.value == ("" if index == 5 else f"Fictional rank {index}")
        assert pilot.rank.evidence is (FieldEvidence.EMPTY if index == 5 else FieldEvidence.PARSED)
        assert pilot.observed_records == 3 and pilot.rejected_records == 1
        assert pilot.is_complete is False
        assert not hasattr(pilot, "pilot_id") and not hasattr(pilot, "name")


def test_mission_independence_and_current_fixture_counts(dataset):
    service = SourcePreviewService(str(dataset))
    before = query(service, "M-01")
    assert isinstance(before.payload, MissionLogPreview)
    assert before.payload.squadron.value.value == "Fictional independent mission squadron"
    assert before.payload.date.value.value == "1917-04-02"
    assert before.payload.time.value.value == "08:25"
    assert before.payload.weather.value.value == "Dynamic"
    assert before.payload.result.value.value == "Completed"
    assert before.payload.formation_count == 5 and before.payload.waypoint_count == 6
    assert type(before.payload.formation_entries) is tuple
    for index in range(1, 7):
        query(service, f"S-{index:02d}")
    after = query(service, "M-01")
    assert before.payload == after.payload
    assert before.payload.career_association == "UNVERIFIED"


@pytest.mark.parametrize("formation,waypoints", [(1, 0), (2, 3), (0, 0)])
def test_mission_counts_are_not_hardcoded(dataset, formation, waypoints):
    replace_source(dataset, "M-01", mission(formation, waypoints))
    preview = query(SourcePreviewService(str(dataset)), "M-01").payload
    assert isinstance(preview, MissionLogPreview)
    assert preview.formation_count == formation
    assert preview.waypoint_count == (waypoints if formation else 0)


def test_parser_fallbacks_and_missing_fields_are_unavailable(dataset):
    replace_source(dataset, "M-01", mission(weather=False, time=False, result=False, player=False))
    preview = query(SourcePreviewService(str(dataset)), "M-01").payload
    assert isinstance(preview, MissionLogPreview)
    for name in ("weather", "time", "squadron", "aircraft", "result"):
        assert getattr(preview, name).evidence is FieldEvidence.UNAVAILABLE


def test_dossier_guard_and_claims_incomplete_semantics(dataset, monkeypatch):
    from woff import source_preview_service as module
    original = module.WoFFDossierParser.parse_bytes
    calls = []
    def guarded(self, data, basename, *, require_verified_layout=False):
        calls.append((self, require_verified_layout))
        return original(self, data, basename, require_verified_layout=require_verified_layout)
    monkeypatch.setattr(module.WoFFDossierParser, "parse_bytes", guarded)
    service = SourcePreviewService(str(dataset))
    for index in range(1, 7):
        dossier = query(service, f"D-{index:02d}").payload
        assert isinstance(dossier, DiagnosticPreview)
        assert dossier.status is DiagnosticStatus.INVALID_ROSTER
        assert not dossier.admitted and not dossier.is_complete
        assert not hasattr(dossier, "pilot") and not hasattr(dossier, "roster")
        claims = query(service, f"C-{index:02d}").payload
        assert isinstance(claims, DiagnosticPreview)
        assert claims.declared_records.value == 0
        assert (claims.observed_records, claims.rejected_records) == (1, 1)
        assert not claims.is_complete and not claims.valid_empty
        assert claims.status is DiagnosticStatus.CLAIMS_INCOMPLETE
    assert len(calls) == 6 and len({id(parser) for parser, _ in calls}) == 6
    assert all(guard for _, guard in calls)


def test_admission_status_is_not_forced_to_historical_rejection(dataset):
    replace_source(dataset, "C-01", b"0\r\n")
    claims = query(SourcePreviewService(str(dataset)), "C-01").payload
    assert isinstance(claims, DiagnosticPreview)
    assert claims.is_complete and claims.valid_empty
    assert claims.status is DiagnosticStatus.CLAIMS_COMPLETE


def test_missing_modified_and_manifest_changed_clear_payload(dataset):
    service = SourcePreviewService(str(dataset))
    reader = VerifiedCopyInputs(str(dataset))
    source = reader.sources[0]
    assert query(service, "S-01").state is ScreenState.READY
    source.path.write_bytes(b"Fictional changed generation")
    changed = query(service, "S-01")
    assert changed.failure is PreviewFailure.INTEGRITY and changed.payload is None
    source.path.unlink()
    missing = query(service, "S-01")
    assert missing.failure is PreviewFailure.MISSING and missing.payload is None
    dataset.write_text(dataset.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert query(service, "S-02").failure is PreviewFailure.INTEGRITY


@pytest.mark.parametrize("change", ["duplicate", "missing", "wrong-category", "basename", "hash", "no-hash",
                                  "unverified", "outside", "traversal", "original-overlap", "same-copy"])
def test_manifest_validation(dataset, change):
    records = json.loads(dataset.read_text(encoding="utf-8"))
    if change == "duplicate": records.append(records[0].copy())
    elif change == "missing": records.pop()
    elif change == "wrong-category": records[0]["category"] = "PilotClaims"
    elif change == "basename": records[0]["basename"] = "Pilot8Squads.txt"
    elif change == "hash": records[0]["sha256_before"] = "z" * 64
    elif change == "no-hash": del records[0]["sha256_before"]
    elif change == "unverified": records[0]["stable_acquisition"] = False
    elif change == "outside": records[0]["copied_input"] = str(dataset.parent / "Pilot1Squads.txt")
    elif change == "traversal": records[0]["copied_input"] = str(dataset.parent / "inputs/../Pilot1Squads.txt")
    elif change == "original-overlap": records[0]["actual_source"] = records[0]["copied_input"]
    elif change == "same-copy": records[1].update({k: records[0][k] for k in ("basename", "copied_input")})
    dataset.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(CopyInputError):
        VerifiedCopyInputs(str(dataset))


@pytest.mark.parametrize("raw", [r"\\server\share\source", r"\\?\C:\source", r"\\.\NUL", r"C:\copy\source:stream",
                                r"C:\copy\..\source", r"C:relative", "inputs/../source", "NUL.txt", "copy. ", "bad\x00"])
def test_windows_unsafe_path_forms(raw):
    with pytest.raises(CopyInputError):
        _path(raw)


@pytest.mark.parametrize("operation", ["open", "close"])
def test_windows_native_entrypoints_reject_non_windows(tmp_path, monkeypatch, operation):
    from woff import source_preview_inputs as module
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(CopyInputError, match="unsafe"):
        if operation == "open":
            module._windows_open(tmp_path / "fictional-unsupported.txt")
        else:
            module._windows_close(0)


def test_hardlink_substitution_denied(dataset):
    reader = VerifiedCopyInputs(str(dataset))
    source = reader.sources[0]
    os.link(source.path, dataset.parent / "fictional-hardlink")
    with pytest.raises(CopyInputError, match="unsafe"):
        reader.read(source)


@pytest.mark.skipif(os.name == "nt", reason="Windows symlinks require host privilege; junction checked separately")
def test_symlink_substitution_denied(dataset):
    reader = VerifiedCopyInputs(str(dataset))
    source = reader.sources[0]
    moved = dataset.parent / "fictional-target"
    source.path.rename(moved)
    source.path.symlink_to(moved)
    with pytest.raises(CopyInputError, match="unsafe"):
        reader.read(source)


def test_reparse_attribute_denied_without_new_path_api(dataset, monkeypatch):
    reader = VerifiedCopyInputs(str(dataset))
    source = reader.sources[0]
    actual = Path.lstat
    class Reparse:
        st_file_attributes = 0x400
        st_mode = 0o100600
    monkeypatch.setattr(Path, "lstat", lambda path: Reparse() if path == source.path else actual(path))
    with pytest.raises(CopyInputError, match="unsafe"):
        reader.read(source)


@pytest.mark.skipif(os.name != "nt", reason="Native Windows junction admission check")
def test_native_windows_junction_substitution_denied(dataset):
    reader = VerifiedCopyInputs(str(dataset))
    source = reader.sources[0]
    target = dataset.parent / "fictional-junction-target"
    source.path.parent.rename(target)
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(source.path.parent), str(target)],
                            capture_output=True, text=True)
    assert result.returncode == 0, "Fictional junction setup failed"
    with pytest.raises(CopyInputError, match="unsafe"):
        reader.read(source)


def test_two_observations_reject_change_and_replacement(dataset, monkeypatch):
    from woff import source_preview_inputs as module
    reader = VerifiedCopyInputs(str(dataset))
    source = reader.sources[0]
    original = module._observe
    calls = 0
    def observe(path, limit):
        nonlocal calls
        result = original(path, limit)
        if path == source.path:
            calls += 1
            if calls == 1:
                temporary = source.path.with_suffix(".replacement")
                temporary.write_bytes(result[0])
                os.replace(temporary, source.path)
        return result
    monkeypatch.setattr(module, "_observe", observe)
    with pytest.raises(CopyInputError, match="integrity"):
        reader.read(source)


def test_access_denial_is_sanitized(dataset, monkeypatch):
    from woff import source_preview_inputs as module
    service = SourcePreviewService(str(dataset))
    original = module._open_read
    def denied(path):
        if Path(path).name.endswith("Squads.txt"):
            raise PermissionError("PRIVATE_SENTINEL")
        return original(path)
    monkeypatch.setattr(module, "_open_read", denied)
    failure = query(service, "S-01")
    assert failure.failure is PreviewFailure.UNREADABLE and failure.payload is None
    assert "PRIVATE_SENTINEL" not in repr(failure)


@pytest.mark.parametrize("kind", ["file", "records", "rows", "field", "entities", "total"])
def test_explicit_size_and_output_limits(dataset, kind, monkeypatch):
    from woff import source_preview_inputs as module
    alias = "S-01"
    if kind == "file": replace_source(dataset, alias, b"x" * (module.MAX_FILE_BYTES + 1))
    elif kind == "records": replace_source(dataset, alias, b"x\n" * (module.MAX_RECORDS + 1))
    elif kind == "rows": alias = "M-01"; replace_source(dataset, alias, mission(101, 6))
    elif kind == "field": replace_source(dataset, alias, squads(1).replace(b"Fictional sector 1", b"x" * 1001))
    elif kind == "entities": alias = "M-01"; replace_source(dataset, alias, b'<!DOCTYPE test><Mission><Params/></Mission>')
    elif kind == "total": monkeypatch.setattr(module, "MAX_TOTAL_BYTES", 1)
    result = query(SourcePreviewService(str(dataset)), alias)
    assert result.failure is PreviewFailure.LIMIT and result.payload is None


def test_parser_logs_stdout_stderr_and_exceptions_never_escape(dataset, monkeypatch, capsys, caplog):
    from woff import source_preview_service as module
    def sensitive(self, data, basename):
        print("PRIVATE_SENTINEL_STDOUT")
        print("PRIVATE_SENTINEL_STDERR", file=sys.stderr)
        logging.getLogger("WoFFWatch").critical("PRIVATE_SENTINEL_LOG")
        logging.getLogger().critical("PRIVATE_SENTINEL_ROOT")
        raise RuntimeError("PRIVATE_SENTINEL_EXCEPTION")
    monkeypatch.setattr(module.WoFFPilotDataParser, "parse_bytes", sensitive)
    before = logging.root.manager.disable
    service = SourcePreviewService(str(dataset))
    result = query(service, "S-01")
    assert result.failure is PreviewFailure.PARSER and result.payload is None
    assert "PRIVATE_SENTINEL" not in repr(result)
    captured = capsys.readouterr()
    assert "PRIVATE_SENTINEL" not in captured.out + captured.err + caplog.text
    assert logging.root.manager.disable == before


def test_foreign_dataset_generation_rejected(dataset):
    service = SourcePreviewService(str(dataset))
    request = PreviewRequest(replace(service.selections[0], generation=service.selections[1].generation), RequestId("foreign"))
    assert service.query(request).failure is PreviewFailure.UNSAFE


def test_duplicate_json_keys_and_wrong_manifest_type_are_rejected(dataset):
    records = dataset.read_text(encoding="utf-8")
    dataset.write_text(records.replace('"alias": "S-01"', '"alias": "S-01", "alias": "S-01"', 1), encoding="utf-8")
    with pytest.raises(CopyInputError, match="manifest"):
        VerifiedCopyInputs(str(dataset))
    dataset.write_text('{"schema_version": 1, "sources": []}', encoding="utf-8")
    with pytest.raises(CopyInputError, match="manifest"):
        VerifiedCopyInputs(str(dataset))


def test_bytes_changing_during_single_observation_are_rejected(dataset, monkeypatch):
    from woff import source_preview_inputs as module
    reader = VerifiedCopyInputs(str(dataset))
    source = reader.sources[0]
    original = module.os.read
    def changed(descriptor, count):
        data = original(descriptor, count)
        if os.fstat(descriptor).st_ino == source.path.stat().st_ino and data:
            # Simulate altered read bytes even on Windows, where the read-only
            # handle's sharing policy blocks concurrent physical source writes.
            return bytes([data[0] ^ 1]) + data[1:]
        return data
    monkeypatch.setattr(module.os, "read", changed)
    with pytest.raises(CopyInputError, match="integrity"):
        reader.read(source)


@pytest.mark.skipif(os.name != "nt", reason="Native Windows read sharing boundary")
def test_native_windows_read_observation_blocks_write_and_parent_replacement(dataset, monkeypatch):
    from woff import source_preview_inputs as module
    reader = VerifiedCopyInputs(str(dataset))
    source = reader.sources[0]
    original = module.os.read
    attempts = []
    def read(descriptor, count):
        data = original(descriptor, count)
        if os.fstat(descriptor).st_ino == source.path.stat().st_ino and data:
            with pytest.raises(OSError):
                source.path.write_bytes(b"fictional forbidden write")
            with pytest.raises(OSError):
                source.path.parent.rename(dataset.parent / "fictional-replaced-parent")
            attempts.append(True)
        return data
    monkeypatch.setattr(module.os, "read", read)
    data = reader.read(source)
    assert attempts and hashlib.sha256(data).hexdigest() == source.sha256


def test_widget_and_p0_import_boundaries_and_source_package_exclusion():
    root = Path(__file__).resolve().parents[1]
    window = ast.parse((root / "woff/source_preview_desktop/window.py").read_text(encoding="utf-8"))
    for node in ast.walk(window):
        if isinstance(node, ast.ImportFrom) and node.level:
            assert node.module in {"source_preview_contracts", "ui_contracts"}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "Path", "SourcePreviewService"}
    for path in (root / "woff/p0_desktop").glob("*.py"):
        assert "source_preview" not in path.read_text(encoding="utf-8")
    assert '"woff.source_preview_desktop.*"' in (root / "pyproject.toml").read_text(encoding="utf-8")


def test_subprocess_runtime_access_boundary(dataset):
    script = r'''
import os,sys
from pathlib import Path
sys.dont_write_bytecode=True
root=Path(sys.argv[1]).parent
def audit(event,args):
 if event=='import' and any(args[0]==x or args[0].startswith(x+'.') for x in ('sqlite3','woff.database','woff.ingestion','watchdog','woff.config','woff.win_registry')):
  raise AssertionError('forbidden-module')
 if event=='sqlite3.connect' or event.startswith('socket.'):
  raise AssertionError('external-access')
 if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
  path=Path(os.path.abspath(os.fsdecode(args[0])))
  if path.is_relative_to(root/'forbidden-originals') or path.suffix in ('.db','.sqlite','.sqlite3'):
   raise AssertionError('original-or-database')
  if args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_APPEND|os.O_TRUNC):
   raise AssertionError('write')
 if event in ('os.rename','os.remove','os.rmdir','os.chmod','os.link','os.symlink'):
  raise AssertionError('mutation')
sys.addaudithook(audit)
from woff.source_preview_service import SourcePreviewService
from woff.source_preview_contracts import PreviewRequest
from woff.ui_contracts import RequestId,ScreenState
s=SourcePreviewService(sys.argv[1])
assert all(s.query(PreviewRequest(x,RequestId('audit'))).state is ScreenState.READY for x in s.selections)
assert not any(x in sys.modules for x in ('sqlite3','woff.database','woff.ingestion','watchdog'))
print('PASS')
'''
    result = subprocess.run([sys.executable, "-B", "-c", script, str(dataset)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PASS"
