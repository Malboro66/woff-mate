"""Explicit R0.3 composition entry; never discovers or defaults a data source."""
from __future__ import annotations

import argparse
from importlib import metadata, util
from pathlib import Path
import re
import sys
import threading
from typing import NoReturn

from PySide6.QtCore import QThread, Signal, Slot, qVersion
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ..source_preview_contracts import PreviewFailure, PreviewRequest, SourceSelection
from ..source_preview_service import PreviewSetupError, SourcePreviewService
from ..ui_contracts import RequestId
from .window import SourcePreviewWindow


def _check_bindings() -> None:
    # Same pinned/optional policy as the approved adoption path; no dependency
    # on the fixture-only launcher or its graph ownership.
    bindings = ("PySide", "PySide2", "PySide6", "PyQt4", "PyQt5", "PyQt6")
    installed = {re.sub(r"[-_.]+", "-", item.metadata["Name"]).lower()
                 for item in metadata.distributions() if item.metadata["Name"]}
    found = {name for name in bindings if util.find_spec(name) is not None or
             any(item == name.lower() or item.startswith(name.lower() + "-") for item in installed)}
    packages = ("PySide6", "PySide6-Essentials", "PySide6-Addons", "shiboken6")
    if (found != {"PySide6"} or qVersion() != "6.11.2" or
            any(metadata.version(package) != "6.11.2" for package in packages)):
        raise ValueError("Unsupported experimental Qt environment")


class PreviewWorker(QThread):
    catalog_ready = Signal(object)
    snapshot_ready = Signal(object)
    startup_failed = Signal(object)

    def __init__(self, manifest: str) -> None:
        super().__init__()
        self._manifest = manifest
        self._condition = threading.Condition()
        self._stopping = False
        self._pending: PreviewRequest | None = None

    @Slot(object)
    def request(self, request: PreviewRequest) -> None:
        with self._condition:
            if not self._stopping:
                # Exactly one pending selection. Rapid requests replace it.
                self._pending = request
                self._condition.notify()

    @Slot()
    def stop(self) -> None:
        with self._condition:
            self._stopping = True
            self._pending = None
            self._condition.notify()

    def run(self) -> None:
        with self._condition:
            if self._stopping:
                return
        try:
            service = SourcePreviewService(self._manifest)
        except PreviewSetupError as error:
            self.startup_failed.emit(error.failure)
            return
        except Exception:
            self.startup_failed.emit(PreviewFailure.MANIFEST)
            return
        with self._condition:
            if self._stopping:
                return
        self.catalog_ready.emit(service.selections)
        independent: list[SourceSelection] = [item for item in service.selections if not item.alias.startswith("S-")]
        while True:
            with self._condition:
                if self._stopping:
                    return
                if self._pending is not None:
                    request = self._pending
                    self._pending = None
                elif independent:
                    selection = independent.pop(0)
                    request = PreviewRequest(selection, RequestId("initial-" + selection.alias))
                else:
                    self._condition.wait()
                    continue
            snapshot = service.query(request)
            with self._condition:
                if self._stopping:
                    return
                superseded = request.selection.alias.startswith("S-") and self._pending is not None
            if not superseded:
                self.snapshot_ready.emit(snapshot)


class _Arguments(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        # Avoid echoing a user's private arguments in failure evidence.
        del message
        self.print_usage(sys.stderr)
        self.exit(2, "An explicit --manifest argument is required; no automatic source discovery.\n")


def main() -> int:
    parser = _Arguments(description="Experimental immutable-copy preview; R1 HOLD.")
    parser.add_argument("--manifest", required=True, help="existing private legacy R0 manifest")
    args = parser.parse_args()
    try:
        _check_bindings()
    except Exception:
        print("Preview unavailable: use the approved isolated PySide6/Qt 6.11.2 environment.", file=sys.stderr)
        return 2
    app = QApplication.instance() or QApplication([sys.argv[0]])
    icon = QIcon(str(Path(__file__).absolute().parents[1] / "assets/ui/branding/woff_mate_app.ico"))
    window = SourcePreviewWindow(icon)
    worker = PreviewWorker(args.manifest)
    window.worker_active = True
    window.source_requested.connect(worker.request)
    window.close_requested.connect(worker.stop)
    worker.catalog_ready.connect(window.set_catalog)
    worker.snapshot_ready.connect(window.accept_snapshot)
    worker.startup_failed.connect(window.show_startup_failure)
    worker.finished.connect(window.worker_finished)
    app.aboutToQuit.connect(worker.stop)
    window.show()
    worker.start()
    result = app.exec()
    worker.stop()
    worker.wait()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
