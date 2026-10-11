"""Optional Qt checks with fictional copies; no private files in public CI."""
from __future__ import annotations

from dataclasses import replace
import os
from uuid import uuid4

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from source_preview_support import write_dataset
from woff.source_preview_contracts import PreviewFailure, PreviewRequest, PreviewSnapshot
from woff.source_preview_desktop.__main__ import PreviewWorker, _check_bindings
from woff.source_preview_desktop.window import SourcePreviewWindow
from woff.source_preview_service import SourcePreviewService
from woff.ui_contracts import RequestId, ScreenState


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def service(tmp_path):
    return SourcePreviewService(str(write_dataset(tmp_path)))


def await_condition(predicate, seconds=5):
    if predicate():
        return
    # A real Qt event loop releases the GIL. Repeated native QTest.qWait calls
    # can starve the Python parsing worker on Windows, unlike app.exec().
    loop = QEventLoop()
    timer = QTimer()
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    timer.start(10)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    deadline.start(int(seconds * 1000))
    loop.exec()
    timer.stop()
    deadline.stop()
    assert predicate()


def prepare(app, service):
    window = SourcePreviewWindow()
    requests = []
    window.source_requested.connect(requests.append)
    window.show()
    window.set_catalog(service.selections)
    app.processEvents()
    return window, requests


def test_title_qualification_six_sources_and_fields(app, service):
    window, requests = prepare(app, service)
    assert window.windowTitle() == "WoFF Mate — Local Source Preview"
    assert window.qualification.text() == "Immutable local copies — no live updates"
    assert [window.source_selector.itemText(i) for i in range(6)] == [f"S-{i:02d}" for i in range(1, 7)]
    assert window.source_selector.count() == 6
    for index in range(6):
        window.source_selector.setCurrentIndex(index)
        assert window.accept_snapshot(service.query(requests[-1]))
        assert window.pilot_fields["squadron"].text() == f"Fictional squadron {index + 1}"
        rank = window.pilot_fields["rank"].text()
        assert ("parser returned an empty value" in rank) if index == 4 else rank == f"Fictional rank {index + 1}"
        assert window.pilot_fields["source_record_date"].text() == "1917-04-02"
    window.close()


def test_clear_is_immediate_and_late_reply_cannot_restore_previous_source(app, service):
    window, requests = prepare(app, service)
    first = service.query(requests[-1])
    assert window.accept_snapshot(first)
    window.source_selector.setCurrentIndex(4)
    assert window.current_snapshot is None
    assert all("Fictional" not in label.text() for label in window.pilot_fields.values())
    assert not window.pilot_provenance.text()
    assert not window.accept_snapshot(first)
    assert window.accept_snapshot(service.query(requests[-1]))
    assert "parser returned an empty value" in window.pilot_fields["rank"].text()
    window.close()


def test_rapid_switch_and_all_four_response_identity_dimensions(app, service):
    window, requests = prepare(app, service)
    for index in (4, 5, 0, 2, 4, 0):
        window.source_selector.setCurrentIndex(index)
    newest = service.query(requests[-1])
    for request in requests[:-1]:
        assert not window.accept_snapshot(service.query(request))
    for changed in (
        replace(newest.request, request_id=RequestId("old-request")),
        replace(newest.request, selection=replace(newest.request.selection, dataset_id=str(uuid4()))),
        replace(newest.request, selection=replace(newest.request.selection, generation=str(uuid4()))),
        PreviewRequest(service.selections[1], newest.request.request_id),
    ):
        assert not window.accept_snapshot(PreviewSnapshot(changed, ScreenState.ERROR, failure=PreviewFailure.INTEGRITY))
    assert window.accept_snapshot(newest)
    assert window.pilot_fields["squadron"].text() == "Fictional squadron 1"
    window.close()


def test_independent_mission_and_diagnostics_and_collapsed_inspection(app, service):
    window, requests = prepare(app, service)
    for source in service.selections[6:]:
        response = service.query(PreviewRequest(source, RequestId("initial-" + source.alias)))
        assert window.accept_snapshot(response)
    mission = window.mission_snapshot
    counts = window.mission_counts.text()
    assert counts == "Formation entries: 5 · Waypoints: 6"
    assert window.mission_fields["squadron"].text() == "Fictional independent mission squadron"
    assert not window.inspection_button.isChecked() and window.inspection.isHidden()
    window.tabs.setCurrentIndex(1)
    window.inspection_button.setFocus()
    QTest.keyClick(window.inspection_button, Qt.Key.Key_Space)
    assert window.inspection_button.isChecked() and not window.inspection.isHidden()
    assert "Fictional0" in window.inspection.text()
    for index in (4, 5, 0):
        window.source_selector.setCurrentIndex(index)
        window.accept_snapshot(service.query(requests[-1]))
        assert window.mission_snapshot is mission and window.mission_counts.text() == counts
    assert len(window.diagnostic_snapshots) == 12
    for alias, row in window.diagnostic_rows.items():
        assert "Rejected by current authoritative admission" in row.text() if alias.startswith("D-") else "is_complete=False" in row.text()
    window.close()


def test_source_failure_clears_prior_data_and_no_fallback(app, service):
    window, requests = prepare(app, service)
    window.accept_snapshot(service.query(requests[-1]))
    failure = PreviewSnapshot(requests[-1], ScreenState.ERROR, failure=PreviewFailure.INTEGRITY)
    assert window.accept_snapshot(failure)
    assert window.current_snapshot is not None and window.current_snapshot.payload is None
    assert all("Fictional" not in row.text() for row in window.pilot_fields.values())
    assert not window.pilot_provenance.text()
    assert window.source_selector.currentText() == "S-01"
    window.show_startup_failure(PreviewFailure.MANIFEST)
    assert window.source_selector.count() == 0
    assert not window.source_selector.isEnabled() and "HOLD" in window.startup_status.text()
    assert window.mission_snapshot is None
    window.close()


def test_keyboard_selection_focus_and_readable_compact_size(app, service):
    window, requests = prepare(app, service)
    window.source_selector.setFocus()
    app.processEvents()
    assert window.source_selector.hasFocus()
    QTest.keyClick(window.source_selector, Qt.Key.Key_Down)
    assert window.source_selector.currentText() == "S-02"
    assert requests[-1].selection.alias == "S-02"
    QTest.keyClick(window.source_selector, Qt.Key.Key_Tab)
    app.processEvents()
    assert QApplication.focusWidget() is not window.source_selector
    focused = QApplication.focusWidget()
    assert focused is not None
    QTest.keyClick(focused, Qt.Key.Key_Backtab)
    assert window.source_selector.hasFocus()
    for width, height in ((640, 480), (1050, 780), (680, 520)):
        window.resize(width, height)
        app.processEvents()
        assert window.tabs.width() > 500
        assert window.source_selector.height() >= 36
    assert "QComboBox:focus" in window.styleSheet()
    window.close()


def test_native_plaintext_rendering_cannot_interpret_source_html(app, service):
    window, requests = prepare(app, service)
    assert all(row.textFormat() is Qt.TextFormat.PlainText for row in window.pilot_fields.values())
    assert window.inspection.textFormat() is Qt.TextFormat.PlainText
    window.close()


def test_worker_end_to_end_close_and_reopen(app, tmp_path):
    manifest = write_dataset(tmp_path)
    for _ in range(2):
        window = SourcePreviewWindow()
        worker = PreviewWorker(str(manifest))
        window.worker_active = True
        window.source_requested.connect(worker.request)
        window.close_requested.connect(worker.stop)
        worker.catalog_ready.connect(window.set_catalog)
        worker.snapshot_ready.connect(window.accept_snapshot)
        worker.startup_failed.connect(window.show_startup_failure)
        worker.finished.connect(window.worker_finished)
        window.show()
        worker.start()
        try:
            await_condition(lambda: window.current_snapshot is not None and len(window.diagnostic_snapshots) == 12)
            for index in (4, 5, 0, 3, 2):
                window.source_selector.setCurrentIndex(index)
            await_condition(lambda: window.current_snapshot is not None and
                            window.current_snapshot.request.selection.alias == "S-03")
            window.close()
            await_condition(lambda: not worker.isRunning() and not window.isVisible())
            assert not window.worker_active
        finally:
            worker.stop()
            assert worker.wait(5000)
            window.worker_finished()
            window.close()


def test_worker_close_before_manifest_loaded_and_closed_replies_ignored(app, service, tmp_path):
    window, requests = prepare(app, service)
    reply = service.query(requests[-1])
    window.close()
    assert not window.accept_snapshot(reply)
    worker = PreviewWorker(str(tmp_path / "missing.private.json"))
    worker.stop()
    worker.start()
    assert worker.wait(5000)


def test_binding_matches_approved_environment():
    _check_bindings()
