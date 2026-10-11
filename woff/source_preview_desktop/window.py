"""Native presentation of immutable source snapshots; no input I/O or parsing."""
from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from ..source_preview_contracts import (
    DiagnosticPreview, MissionLogPreview, PilotSquadsPreview, PreviewFailure,
    PreviewField, PreviewRequest, PreviewSnapshot, SourceSelection,
)
from ..ui_contracts import RequestId, ScreenState

_STYLE = """
QMainWindow, QWidget { background: #18231F; color: #F4EFE2; font-family: 'Segoe UI'; font-size: 14px; }
QLabel#brand { font-family: Georgia; font-size: 25px; font-weight: bold; }
QLabel#qualification { color: #E0B65C; }
QFrame#card, QFrame#card QLabel { background: #E7D8B8; color: #201D18; }
QFrame#card { border: 1px solid #A99A7C; border-radius: 6px; }
QLabel { padding: 3px; }
QComboBox, QPushButton { min-height: 36px; padding: 4px 10px; border: 1px solid #46534C; border-radius: 4px; background: #26332D; }
QComboBox:hover, QPushButton:hover { border-color: #C2A86B; }
QComboBox:focus, QPushButton:focus, QTabBar::tab:focus { border: 2px solid #F7F2E6; background: #334138; }
QFrame#card QLabel:focus { border: 2px solid #544324; }
QScrollArea { border: 0; }
QTabWidget::pane { border: 1px solid #46534C; }
QTabBar::tab { padding: 10px; background: #26332D; border: 1px solid #46534C; }
QTabBar::tab:selected { background: #334138; border-bottom: 2px solid #E0B65C; }
"""
_PILOT_FIELDS = (
    ("squadron", "Squadron"), ("aircraft", "Aircraft"),
    ("aerodrome", "Aerodrome"), ("sector", "Sector"),
    ("source_record_date", "Source-record date"), ("rank", "Rank"),
)
_MISSION_FIELDS = (
    ("date", "Mission date"), ("time", "Mission time"),
    ("squadron", "Squadron"), ("aircraft", "Aircraft"),
    ("weather", "Weather"), ("result", "Supported result"),
)


def _label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _card(spec: tuple[tuple[str, str], ...]) -> tuple[QFrame, dict[str, QLabel]]:
    card = QFrame()
    card.setObjectName("card")
    form = QFormLayout(card)
    form.setContentsMargins(18, 16, 18, 16)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    values = {}
    for name, title in spec:
        value = _label("Unavailable — no source loaded")
        value.setAccessibleName(title)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse |
                                      Qt.TextInteractionFlag.TextSelectableByKeyboard)
        value.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        form.addRow(_label(title), value)
        values[name] = value
    return card, values


def _page() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(14)
    scroll.setWidget(content)
    return scroll, layout


class SourcePreviewWindow(QMainWindow):
    source_requested = Signal(object)
    close_requested = Signal()

    def __init__(self, icon: QIcon | None = None) -> None:
        super().__init__()
        self.setWindowTitle("WoFF Mate — Local Source Preview")
        if icon is not None:
            self.setWindowIcon(icon)
        self.resize(1050, 780)
        self.setMinimumSize(640, 480)
        self.setStyleSheet(_STYLE)
        self.worker_active = False
        self._closing = False
        self._catalog: tuple[SourceSelection, ...] = ()
        self._current_request: PreviewRequest | None = None
        self._independent_requests: dict[str, PreviewRequest] = {}
        self.current_snapshot: PreviewSnapshot | None = None
        self.mission_snapshot: PreviewSnapshot | None = None
        self.diagnostic_snapshots: dict[str, PreviewSnapshot] = {}
        shell = QWidget()
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(20, 18, 20, 18)
        self.setCentralWidget(shell)
        brand = _label("WoFF Mate · Local Source Preview")
        brand.setObjectName("brand")
        outer.addWidget(brand)
        self.qualification = _label("Immutable local copies — no live updates")
        self.qualification.setObjectName("qualification")
        outer.addWidget(self.qualification)
        outer.addWidget(_label("Experimental R0.3 · source aliases are copies, not verified careers · R1 HOLD"))
        self.startup_status = _label("Loading the explicit private manifest…")
        outer.addWidget(self.startup_status)
        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Source preview sections")
        outer.addWidget(self.tabs, 1)
        pilot_page, pilot_layout = _page()
        selector_row = QHBoxLayout()
        selector_label = _label("&Source")
        selector_label.setTextFormat(Qt.TextFormat.AutoText)
        self.source_selector = QComboBox()
        self.source_selector.setAccessibleName("Select PilotSquads source copy")
        self.source_selector.setEnabled(False)
        self.source_selector.setMinimumWidth(160)
        selector_label.setBuddy(self.source_selector)
        selector_row.addWidget(selector_label)
        selector_row.addWidget(self.source_selector, 1)
        pilot_layout.addLayout(selector_row)
        self.pilot_status = _label("No source selected")
        pilot_layout.addWidget(self.pilot_status)
        pilot_card, self.pilot_fields = _card(_PILOT_FIELDS)
        pilot_layout.addWidget(pilot_card)
        self.pilot_provenance = _label()
        pilot_layout.addWidget(self.pilot_provenance)
        pilot_layout.addStretch()
        self.tabs.addTab(pilot_page, "&PilotSquads")
        mission_page, mission_layout = _page()
        mission_layout.addWidget(_label("M-01 · Independent Mission.log"))
        association = _label("Career association: UNVERIFIED")
        association.setObjectName("qualification")
        mission_layout.addWidget(association)
        self.mission_status = _label("Loading independent source…")
        mission_layout.addWidget(self.mission_status)
        mission_card, self.mission_fields = _card(_MISSION_FIELDS)
        mission_layout.addWidget(mission_card)
        self.mission_counts = _label("Formation entries: unavailable · Waypoints: unavailable")
        mission_layout.addWidget(self.mission_counts)
        self.mission_provenance = _label()
        mission_layout.addWidget(self.mission_provenance)
        self.inspection_button = QPushButton("Inspect local parser entries")
        self.inspection_button.setCheckable(True)
        self.inspection_button.setEnabled(False)
        self.inspection_button.setAccessibleName("Show or hide local formation and route entries")
        mission_layout.addWidget(self.inspection_button)
        self.inspection = _label()
        self.inspection.setVisible(False)
        mission_layout.addWidget(self.inspection)
        self.inspection_button.toggled.connect(self.inspection.setVisible)
        mission_layout.addStretch()
        self.tabs.addTab(mission_page, "Independent &Mission.log")
        diagnostic_page, diagnostic_layout = _page()
        diagnostic_layout.addWidget(_label("Admission diagnostics · D/C numbering is diagnostic grouping only"))
        diagnostic_layout.addWidget(_label("Current authoritative admission only. Historical explanations are not supplied.\n"
                                           "Dossier/Claims diagnostics do not establish a career, roster census or victory total."))
        self.diagnostic_rows = {}
        for family in ("D", "C"):
            for index in range(1, 7):
                alias = f"{family}-{index:02d}"
                label = _label(f"{alias} · Loading diagnostic source…")
                diagnostic_layout.addWidget(label)
                self.diagnostic_rows[alias] = label
        diagnostic_layout.addStretch()
        self.tabs.addTab(diagnostic_page, "Admission &diagnostics")
        self.source_selector.currentIndexChanged.connect(self._source_changed)

    @Slot(object)
    def set_catalog(self, selections: tuple[SourceSelection, ...]) -> None:
        if self._closing:
            return
        if (type(selections) is not tuple or len(selections) != 19 or
                any(not isinstance(value, SourceSelection) for value in selections) or
                len({value.alias for value in selections}) != 19 or
                len({value.dataset_id for value in selections}) != 1):
            self.show_startup_failure(PreviewFailure.MANIFEST)
            return
        self._catalog = selections
        self._current_request = None
        self.current_snapshot = None
        self.mission_snapshot = None
        self.diagnostic_snapshots.clear()
        self._clear_mission()
        for alias, label in self.diagnostic_rows.items():
            label.setText(f"{alias} · Loading diagnostic source…")
        self._independent_requests = {
            selection.alias: PreviewRequest(selection, RequestId("initial-" + selection.alias))
            for selection in selections if not selection.alias.startswith("S-")
        }
        self.source_selector.blockSignals(True)
        self.source_selector.clear()
        for selection in selections:
            if selection.alias.startswith("S-"):
                self.source_selector.addItem(selection.alias, selection)
        self.source_selector.blockSignals(False)
        self.source_selector.setEnabled(True)
        self.startup_status.setText("Explicit captured dataset · hash verification precedes each parse · game freshness UNKNOWN")
        self._source_changed(0)
        self.source_selector.setFocus()

    def _source_changed(self, index: int) -> None:
        self._current_request = None
        self.current_snapshot = None
        self.pilot_provenance.clear()
        for label in self.pilot_fields.values():
            label.setText("Unavailable — loading selected source")
        self.pilot_status.setText("Loading selected source…")
        if self._closing or index < 0:
            return
        selection = self.source_selector.itemData(index)
        if not isinstance(selection, SourceSelection) or selection not in self._catalog:
            self.pilot_status.setText(PreviewFailure.UNSAFE.message)
            return
        self._current_request = PreviewRequest(selection, RequestId(str(uuid4())))
        self.source_requested.emit(self._current_request)

    @Slot(object)
    def accept_snapshot(self, snapshot: PreviewSnapshot) -> bool:
        if self._closing or not isinstance(snapshot, PreviewSnapshot):
            return False
        alias = snapshot.request.selection.alias
        expected = self._current_request if alias.startswith("S-") else self._independent_requests.get(alias)
        # Equality binds dataset, alias, opaque generation AND latest request ID.
        if snapshot.request != expected:
            return False
        if alias.startswith("S-"):
            self.current_snapshot = snapshot
            if isinstance(snapshot.payload, PilotSquadsPreview):
                for name, title in _PILOT_FIELDS:
                    self._render_field(self.pilot_fields[name], getattr(snapshot.payload, name), title)
                self.pilot_status.setText(f"{alias} · Parsed source values · " +
                                          ("Source records complete" if snapshot.payload.is_complete else
                                           "Partial source — some physical records rejected"))
                self.pilot_provenance.setText(self._provenance(snapshot))
            else:
                for label in self.pilot_fields.values():
                    label.setText("Unavailable — selected source has no accepted preview")
                self.pilot_provenance.clear()
                self.pilot_status.setText(self._failure_text(snapshot))
        elif alias == "M-01":
            self._clear_mission()
            self.mission_snapshot = snapshot
            if isinstance(snapshot.payload, MissionLogPreview):
                mission = snapshot.payload
                for name, title in _MISSION_FIELDS:
                    self._render_field(self.mission_fields[name], getattr(mission, name), title)
                self.mission_status.setText("M-01 · Parsed independent source values · Career association: UNVERIFIED")
                self.mission_counts.setText(f"Formation entries: {mission.formation_count} · Waypoints: {mission.waypoint_count}")
                self.mission_provenance.setText(self._provenance(snapshot))
                rows = ("Formation — parser labels, not verified identities", *mission.formation_entries,
                        "Route — parser type and altitude; units not independently certified",
                        *(f"{row.kind.display('Type')} · {row.altitude.display('Altitude')}" for row in mission.route_entries))
                self.inspection.setText("\n".join(rows))
                self.inspection_button.setEnabled(True)
            else:
                self.mission_status.setText(self._failure_text(snapshot))
        else:
            self.diagnostic_snapshots[alias] = snapshot
            diagnostic = snapshot.payload
            if isinstance(diagnostic, DiagnosticPreview):
                if alias.startswith("D-"):
                    text = ("Admitted by current guarded parser (diagnostic only)" if diagnostic.admitted else
                            "Rejected by current authoritative admission")
                    detail = f"{diagnostic.status.value} · roster_complete={diagnostic.is_complete}"
                else:
                    text = "Current Claims parser status; no career victory total"
                    declared = diagnostic.declared_records.value
                    detail = (f"declared={declared if declared is not None else 'unavailable'} · "
                              f"observed={diagnostic.observed_records} · rejected={diagnostic.rejected_records} · "
                              f"is_complete={diagnostic.is_complete} · valid_empty={diagnostic.valid_empty}")
                self.diagnostic_rows[alias].setText(f"{alias} · {text}\n{detail}\nHash-verified captured copy · diagnostic-only")
            else:
                self.diagnostic_rows[alias].setText(f"{alias} · {self._failure_text(snapshot)}")
        return True

    @staticmethod
    def _render_field(label: QLabel, value: PreviewField, title: str) -> None:
        label.setText(value.display(title))
        label.setAccessibleDescription(value.evidence.value)
        label.setToolTip(value.evidence.value)

    @staticmethod
    def _provenance(snapshot: PreviewSnapshot) -> str:
        provenance = snapshot.provenance
        if provenance is None:
            return ""
        return (f"{provenance.selection.alias} · Hash-verified immutable copy · verified at "
                f"{provenance.verified_at.isoformat(timespec='seconds')}\n{provenance.policy.value}\n"
                f"{provenance.parser_projection} · current checkout · {provenance.contract_version}\n"
                "Verification matches acquisition; it does not establish current game synchronization.")

    @staticmethod
    def _failure_text(snapshot: PreviewSnapshot) -> str:
        return snapshot.failure.message if snapshot.failure else "Loading selected source…"

    def _clear_mission(self) -> None:
        for label in self.mission_fields.values():
            label.setText("Unavailable — no accepted independent preview")
        self.mission_status.setText("Loading independent source…")
        self.mission_counts.setText("Formation entries: unavailable · Waypoints: unavailable")
        self.mission_provenance.clear()
        self.inspection_button.setChecked(False)
        self.inspection_button.setEnabled(False)
        self.inspection.clear()
        self.inspection.hide()

    @Slot(object)
    def show_startup_failure(self, failure: PreviewFailure) -> None:
        self._catalog = ()
        self._current_request = None
        self._independent_requests.clear()
        self.current_snapshot = None
        self.mission_snapshot = None
        self.diagnostic_snapshots.clear()
        self.source_selector.blockSignals(True)
        self.source_selector.clear()
        self.source_selector.blockSignals(False)
        self.source_selector.setEnabled(False)
        self._source_changed(-1)
        self._clear_mission()
        self.startup_status.setText(f"HOLD on real-data acceptance · {failure.message}")
        self.pilot_status.setText(failure.message)
        self.mission_status.setText(failure.message)
        for alias, label in self.diagnostic_rows.items():
            label.setText(f"{alias} · {failure.message}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker_active:
            event.ignore()
            if not self._closing:
                self._closing = True
                self.show_startup_failure(PreviewFailure.CANCELLED)
                self.tabs.setEnabled(False)
                self.startup_status.setText("Closing safely after the bounded worker stops…")
                self.close_requested.emit()
        else:
            self._closing = True
            event.accept()

    @Slot()
    def worker_finished(self) -> None:
        self.worker_active = False
        if self._closing:
            self.close()
