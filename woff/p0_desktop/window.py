"""Experimental Qt Widgets shell; no production service or mutable model imports."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, Qt, QSize, QEvent, QObject
from PySide6.QtGui import QIcon, QPixmap, QResizeEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..ui_contracts import (
    FieldValue, PilotId, ScreenState, SnapshotReason, UnavailableReason,
)
from .fixtures import FixturePresentation, SCREENS, Snapshot, ReportsView

_ASSETS = Path(__file__).resolve().parents[1] / "assets/ui"
_EMPTY_MESSAGES = {
    "OPR-01": "No operations recorded in this synthetic view.",
    "DOS-01": "No pilot dossier entries recorded in this synthetic view.",
    "MIS-01": "No missions recorded in this synthetic view.",
    "SQD-01": "No squadron members recorded in this synthetic view.",
    "JRN-01": "No diary entries recorded in this synthetic view.",
    "RPT-01": "No reports recorded in this synthetic view.",
    "SYS-01": "No diagnostics recorded in this synthetic view.",
}
_PALETTE = """
QMainWindow, QWidget#shell { background: #18231F; color: #F4EFE2; font-family: 'Segoe UI'; font-size: 14px; }
QWidget#rail { background: #111614; border-right: 1px solid #46534C; }
QWidget#context { background: #26332D; border-bottom: 1px solid #46534C; }
QScrollArea, QScrollArea > QWidget > QWidget { background: #18231F; border: 0; }
QLabel#brand { font-family: Georgia; font-size: 19px; font-weight: bold; color: #F4EFE2; }
QLabel#heading { font-family: Georgia; font-size: 28px; font-weight: bold; color: #F4EFE2; }
QLabel#muted, QLabel#caption { color: #C2BCAF; }
QLabel#paper, QLabel#paperTitle { color: #201D18; background: #E7D8B8; }
QLabel#paperTitle { font-family: Georgia; font-size: 19px; font-weight: bold; }
QFrame#card { background: #E7D8B8; border: 1px solid #A99A7C; border-radius: 6px; }
QFrame#notice { background: #26332D; border-left: 3px solid #E0B65C; }
QPushButton, QComboBox { min-height: 40px; padding: 3px 10px; border-radius: 4px;
  border: 1px solid #46534C; background: #26332D; color: #F4EFE2; text-align: left; }
QPushButton:hover, QComboBox:hover { border-color: #C2A86B; }
QPushButton:checked { border-left: 3px solid #C2A86B; background: #334138; }
QPushButton:focus, QComboBox:focus { border: 2px solid #F7F2E6; background: #334138; }
QPushButton#skip { background: #18231F; }
"""


def _svg_icon(path: Path, color: str, size: int = 20) -> QIcon:
    # #129 masters are immutable currentColor SVG. Resolve color in memory only.
    data = path.read_text(encoding="utf-8").replace("currentColor", color).encode()
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        raise ValueError("Invalid committed icon")
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def _field_text(value: FieldValue) -> str:
    if value.value is not None:
        return str(value.value)
    reason = value.reason
    if reason is None:
        raise ValueError("Unavailable value requires a reason")
    return {
        UnavailableReason.UNKNOWN: "Unknown",
        UnavailableReason.REDACTED: "Hidden",
        UnavailableReason.SOURCE_CONFLICT: "Unknown — source conflict",
        UnavailableReason.TRUNCATED: "Not available — incomplete",
        UnavailableReason.UNREADABLE: "Not available — unreadable",
        UnavailableReason.UNSUPPORTED: "Not available — unsupported",
    }.get(reason, "Not available")


def _line(text: str, paper: bool = False, title: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName("paperTitle" if title else "paper" if paper else "muted")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class P0Window(QMainWindow):
    def __init__(self, fixtures: Optional[FixturePresentation] = None) -> None:
        super().__init__()
        self.fixtures = fixtures or FixturePresentation()
        self.active_career_id: Optional[PilotId] = self.fixtures.careers[0].pilot_id
        self.destination = "OPR-01"
        self.fixture_state = "ready"
        self.current_snapshot: Optional[Snapshot] = None
        self.current_case_id = ""
        self.setWindowTitle("WoFF Mate — Synthetic P0")
        self.setWindowIcon(QIcon(str(_ASSETS / "branding/woff_mate_app.ico")))
        self.resize(1200, 850)
        self.setMinimumSize(680, 520)
        self.setStyleSheet(_PALETTE)
        shell = QWidget()
        shell.setObjectName("shell")
        self.setCentralWidget(shell)
        outer = QHBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        rail = QWidget()
        rail.setObjectName("rail")
        self.rail = rail
        rail.setFixedWidth(256)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(16, 20, 16, 20)
        rail_layout.setSpacing(8)
        brand_row = QHBoxLayout()
        self.brand_symbol = QLabel()
        self.brand_symbol.setPixmap(_svg_icon(_ASSETS / "branding/woff_mate_symbol_light.svg", "#F4EFE2", 32).pixmap(32, 32))
        brand_row.addWidget(self.brand_symbol)
        self.brand_name = QLabel("WoFF Mate")
        self.brand_name.setObjectName("brand")
        brand_row.addWidget(self.brand_name)
        brand_row.addStretch()
        rail_layout.addLayout(brand_row)
        rail_layout.addSpacing(22)
        self.skip = QPushButton("Skip to content")
        self.skip.setObjectName("skip")
        self.skip.clicked.connect(lambda: self.heading.setFocus())
        rail_layout.addWidget(self.skip)
        rail_layout.addSpacing(12)
        self.nav_buttons: dict[str, QPushButton] = {}
        for screen, title, icon in SCREENS[:6]:
            button = self._nav_button(screen, title, icon)
            rail_layout.addWidget(button)
        rail_layout.addStretch()
        rail_layout.addWidget(_line("SYSTEM", title=False))
        screen, title, icon = SCREENS[6]
        rail_layout.addWidget(self._nav_button(screen, title, icon))
        outer.addWidget(rail)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        outer.addWidget(right, 1)
        context = QWidget()
        context.setObjectName("context")
        context_layout = QVBoxLayout(context)
        context_layout.setContentsMargins(24, 12, 24, 12)
        context_layout.setSpacing(8)
        career_row = QHBoxLayout()
        career_row.setSpacing(12)
        selector_label = QLabel("CAREER")
        selector_label.setObjectName("muted")
        career_row.addWidget(selector_label)
        self.career = QComboBox()
        self.career.setAccessibleName("Select synthetic career")
        self.career.setMinimumWidth(220)
        for option in self.fixtures.careers:
            self.career.addItem(f"{_field_text(option.display_name)} · WoFF Pilot {_field_text(option.source_slot)}", option.pilot_id.value)
        self.career.currentIndexChanged.connect(self._career_changed)
        career_row.addWidget(self.career, 1)
        context_layout.addLayout(career_row)
        state_row = QHBoxLayout()
        state_row.setSpacing(12)
        self.coverage = _line("Synthetic fixture-backed only")
        state_row.addWidget(self.coverage, 1)
        self.state_picker = QComboBox()
        self.state_picker.setAccessibleName("P0 fixture state")
        for state in ("ready", "loading", "empty", "missing", "stale/unavailable", "error"):
            self.state_picker.addItem(state)
        self.state_picker.currentTextChanged.connect(self.set_fixture_state)
        state_row.addWidget(_line("P0 FIXTURE STATE"))
        state_row.addWidget(self.state_picker)
        context_layout.addLayout(state_row)
        right_layout.addWidget(context)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.page = QWidget()
        self.page_layout = QVBoxLayout(self.page)
        self.page_layout.setContentsMargins(24, 24, 24, 32)
        self.page_layout.setSpacing(16)
        scroll.setWidget(self.page)
        right_layout.addWidget(scroll, 1)
        self._render(focus=False)
        # Structural tab order: skip, selector, navigation, status, page controls.
        QWidget.setTabOrder(self.skip, self.career)
        previous: QWidget = self.career
        for screen, _, _ in SCREENS:
            QWidget.setTabOrder(previous, self.nav_buttons[screen])
            previous = self.nav_buttons[screen]
        QWidget.setTabOrder(previous, self.state_picker)

    def resizeEvent(self, event: QResizeEvent) -> None:
        compact = self.width() < 1000
        self.rail.setFixedWidth(184 if compact else 256)
        self.brand_name.setStyleSheet("font-size: 15px;" if compact else "")
        size = 24 if compact else 32
        self.brand_symbol.setPixmap(_svg_icon(_ASSETS / "branding/woff_mate_symbol_light.svg", "#F4EFE2", size).pixmap(size, size))
        self.nav_buttons["SYS-01"].setText("Data && System\nStatus" if compact else "Data && System Status")
        super().resizeEvent(event)

    def _nav_button(self, screen: str, title: str, icon: str) -> QPushButton:
        button = QPushButton(title.replace("&", "&&"))
        button.setCheckable(True)
        button.setAccessibleName(title)
        button.setIconSize(QSize(20, 20))
        button.clicked.connect(lambda checked=False, target=screen: self.navigate(target))
        button.installEventFilter(self)
        self.nav_buttons[screen] = button
        return button

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(obj, QPushButton) and obj in self.nav_buttons.values():
            from PySide6.QtGui import QKeyEvent
            if isinstance(event, QKeyEvent) and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                items = list(self.nav_buttons.values())
                index = items.index(obj)
                items[(index + (1 if event.key() == Qt.Key.Key_Down else -1)) % len(items)].setFocus()
                return True
        return super().eventFilter(obj, event)

    def navigate(self, screen: str) -> None:
        if screen not in self.nav_buttons:
            raise ValueError("Unknown primary destination")
        self.destination = screen
        self.fixture_state = "ready"
        self.state_picker.blockSignals(True)
        self.state_picker.setCurrentText("ready")
        self.state_picker.blockSignals(False)
        self._render(focus=True)

    def _career_changed(self, index: int) -> None:
        if index < 0:
            return
        selected = PilotId(self.career.itemData(index))
        if selected == self.active_career_id:
            return
        # Clear before updating active identity, including portrait and pending page.
        self._clear_page()
        self.current_snapshot = None
        self.current_case_id = ""
        self.active_career_id = selected
        self.fixture_state = "ready"
        self.state_picker.blockSignals(True)
        self.state_picker.setCurrentText("ready")
        self.state_picker.blockSignals(False)
        self._render(focus=True)

    def set_fixture_state(self, state: str) -> None:
        if state not in ("ready", "loading", "empty", "missing", "stale/unavailable", "error"):
            raise ValueError("Unknown fixture state")
        self.fixture_state = state
        if self.state_picker.currentText() != state:
            self.state_picker.blockSignals(True)
            self.state_picker.setCurrentText(state)
            self.state_picker.blockSignals(False)
        self._render(focus=False)

    def _clear_page(self) -> None:
        while self.page_layout.count():
            item = self.page_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                widget = item.widget()
                if widget is not None:
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()

    def _card(self, title: str, lines: list[str]) -> None:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(9)
        layout.addWidget(_line(title, title=True))
        for item in lines:
            layout.addWidget(_line(item, paper=True))
        self.page_layout.addWidget(card)

    def _render(self, focus: bool) -> None:
        self._clear_page()
        case_id, snapshot = self.fixtures.snapshot(self.destination, self.active_career_id, self.fixture_state)
        self.current_snapshot = snapshot
        self.current_case_id = case_id
        envelope = snapshot.envelope
        screen_title = next(label for key, label, _ in SCREENS if key == self.destination)
        self.heading = QLabel(screen_title)
        self.heading.setObjectName("heading")
        self.heading.setAccessibleName(f"{screen_title} page heading")
        self.heading.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.page_layout.addWidget(self.heading)
        self.page_layout.addWidget(_line(f"{self.destination}  ·  Synthetic  ·  {case_id}  ·  {envelope.state.value}"))
        self.coverage.setText(f"Synthetic · {envelope.state.value} · {envelope.freshness.value}")
        for screen, button in self.nav_buttons.items():
            button.setChecked(screen == self.destination)
            icon = next(i for s, _, i in SCREENS if s == screen)
            style = "filled" if screen == self.destination else "regular"
            path = _ASSETS / f"icons/ui_nav_{icon}_20_{style}.svg"
            button.setIcon(_svg_icon(path, "#F4EFE2" if style == "regular" else "#C2A86B"))
        if envelope.state in {ScreenState.READY, ScreenState.EMPTY, ScreenState.STALE_OR_UNAVAILABLE}:
            self._content(snapshot)
        if envelope.state is not ScreenState.READY or envelope.warnings:
            messages = list(dict.fromkeys(
                [warning.message for warning in envelope.warnings]
                + ([envelope.failure.message] if envelope.failure else [])
            ))
            if not messages:
                messages.append({
                    ScreenState.LOADING: "Loading the synthetic view.",
                    ScreenState.EMPTY: _EMPTY_MESSAGES[self.destination],
                    ScreenState.MISSING: ("Select a career." if envelope.reason is SnapshotReason.CAREER_NOT_SELECTED
                                          else "This synthetic career has no source for this view."),
                    ScreenState.STALE_OR_UNAVAILABLE: "This synthetic source is unavailable. No current value is inferred.",
                }.get(envelope.state, ""))
            notice = QFrame()
            notice.setObjectName("notice")
            layout = QVBoxLayout(notice)
            for message in messages:
                layout.addWidget(_line(message))
            if envelope.observed_at.value:
                layout.addWidget(_line(f"Observed: {envelope.observed_at.value.isoformat()} · {envelope.freshness.value}"))
            self.page_layout.addWidget(notice)
        can_retry = (
            envelope.state is ScreenState.ERROR
            and envelope.failure is not None
            and envelope.failure.retryable
        ) or (
            self.destination == "OPR-01"
            and envelope.state is ScreenState.STALE_OR_UNAVAILABLE
        )
        if can_retry:
            retry = QPushButton("Retry fixture view")
            retry.setIcon(_svg_icon(_ASSETS / "icons/ui_action_retry_20_regular.svg", "#F4EFE2"))
            retry.clicked.connect(lambda: self.set_fixture_state("ready"))
            self.page_layout.addWidget(retry)
        if self.destination != "SYS-01" and envelope.state in {ScreenState.ERROR, ScreenState.MISSING, ScreenState.STALE_OR_UNAVAILABLE}:
            status = QPushButton("View data status")
            status.clicked.connect(lambda: self.navigate("SYS-01"))
            self.page_layout.addWidget(status)
        self.page_layout.addStretch()
        if focus:
            self.heading.setFocus(Qt.FocusReason.OtherFocusReason)

    def _content(self, snapshot: Snapshot) -> None:
        from ..ui_contracts import (OperationsSnapshot, PilotDossierSnapshot, MissionsSnapshot,
                                    SquadronSnapshot, WarDiarySnapshot, SystemStatusSnapshot)
        if isinstance(snapshot, (OperationsSnapshot, PilotDossierSnapshot)):
            if snapshot.pilot:
                pilot = snapshot.pilot
                affiliation = pilot.affiliation.value
                service = affiliation.service_label if affiliation else _field_text(pilot.affiliation)
                self._card("Career identity", [
                    f"{_field_text(pilot.display_name)} · WoFF Pilot {_field_text(pilot.source_slot)}",
                    f"Service: {service} · Squadron: {_field_text(pilot.squadron_label)}",
                    f"Status: {_field_text(pilot.status)}",
                ])
                if self.destination == "DOS-01":
                    portrait = QLabel()
                    path = (_ASSETS / "portraits/ui_portrait_synthetic_aster_master.png"
                            if self.current_case_id == "pilot-ready" else
                            _ASSETS / "portraits/ui_portrait_unavailable.svg")
                    portrait.setPixmap(QPixmap(str(path)).scaled(140, 176,
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    portrait.setAccessibleName(f"Portrait of {_field_text(pilot.display_name)}" if self.current_case_id == "pilot-ready" else "Portrait unavailable")
                    self.page_layout.addWidget(portrait)
                    if self.current_case_id != "pilot-ready":
                        self.page_layout.addWidget(_line("Portrait unavailable"))
            if snapshot.statistics:
                stats = snapshot.statistics
                self._card("Service record", [
                    f"Missions: {_field_text(stats.missions)} · Flight time: {_field_text(stats.flight_minutes)} min",
                    f"Claims: {_field_text(stats.claims)} · Confirmed victories: {_field_text(stats.confirmed_victories)}",
                    f"Skill: {_field_text(stats.skill)} · Reputation: {_field_text(stats.reputation)}",
                ])
            if isinstance(snapshot, OperationsSnapshot) and (
                snapshot.pilot is not None
                or snapshot.statistics is not None
                or bool(snapshot.recent_missions)
            ):
                self._card("Latest mission", ["No recent mission supplied in this overview snapshot."])
        elif isinstance(snapshot, MissionsSnapshot):
            for mission in snapshot.missions:
                self._card(_field_text(mission.title), [
                    f"{mission.occurred_at.value.date().isoformat() if mission.occurred_at.value else 'Unknown'} · {_field_text(mission.result)}",
                    f"Claims: {_field_text(mission.claims)} · Confirmed victories: {_field_text(mission.confirmed_victories)}",
                ])
        elif isinstance(snapshot, SquadronSnapshot):
            if snapshot.squadron:
                self._card("Squadron", [_field_text(snapshot.squadron.display_name)])
            for member in snapshot.members:
                self._card(_field_text(member.display_name), [
                    f"Role: {_field_text(member.role)} · Transfer status: {_field_text(member.transfer_status)}"])
        elif isinstance(snapshot, WarDiarySnapshot):
            for entry in snapshot.entries:
                self._card("War Diary entry", [
                    f"{entry.occurred_at.value.date().isoformat() if entry.occurred_at.value else 'Unknown'} · Mission {entry.mission_id.value.value if entry.mission_id.value else 'Unknown'}",
                    _field_text(entry.narrative),
                ])
        elif isinstance(snapshot, ReportsView):
            for report in snapshot.reports:
                self._card(_field_text(report.title), [_field_text(report.summary)])
        elif isinstance(snapshot, SystemStatusSnapshot):
            if snapshot.profile:
                self._card("Read-only profile", [_field_text(snapshot.profile),
                    "Live installation, database, watchdog and last sync: Not available in P0."])
            for diagnostic in snapshot.diagnostics:
                self._card("Diagnostic", [diagnostic.message])
