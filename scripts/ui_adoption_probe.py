"""Real key-event and Qt accessibility probe for the fixture-only candidate window."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QAccessible, QAccessibleActionInterface
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton

from woff.p0_desktop.window import P0Window
from .ui_adoption_support import environment, provenance


def probe() -> dict:
    started = time.perf_counter()
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    window = P0Window()
    window.show()
    app.processEvents()
    first_window_ms = round((time.perf_counter() - started) * 1000, 3)
    layout = []
    for width, height in ((680, 520), (999, 700), (1000, 700), (1200, 850), (680, 520)):
        window.resize(width, height)
        QTest.qWait(100)
        advance = window.brand_name.fontMetrics().horizontalAdvance(window.brand_name.text())
        available = window.brand_name.width()
        assert advance <= available, (width, advance, available)
        assert window.brand_symbol.geometry().right() < window.brand_name.geometry().left()
        shell = window.centralWidget()
        assert shell is not None and window.rail.geometry().right() < shell.width()
        assert window.career.width() >= window.career.minimumWidth()
        layout.append({"requested_viewport": [width, height], "actual_viewport": [window.width(), window.height()],
                       "brand_advance": advance, "brand_available": available, "rail_width": window.rail.width(),
                       "font": window.brand_name.font().toString(), "device_pixel_ratio": window.devicePixelRatioF()})
    window.resize(1200, 850)
    QTest.qWait(100)
    controls = [window.skip, window.career, *window.nav_buttons.values(), window.state_picker]
    semantics = []
    for control in controls:
        interface = QAccessible.queryAccessibleInterface(control)
        if interface is None:
            raise AssertionError("Missing accessibility interface")
        name = interface.text(QAccessible.Text.Name)
        state = interface.state()
        role = interface.role()
        assert name and state.focusable and not state.disabled, (name, role)
        expected = (QAccessible.Role.CheckBox if control.isCheckable() else QAccessible.Role.Button) if isinstance(control, QPushButton) else QAccessible.Role.ComboBox
        assert role == expected, (name, role, expected)
        semantics.append({"name": name, "role": role.name, "focusable": bool(state.focusable)})
    selector_focus = []
    # A plain native combo is the control experiment, without app callbacks/style.
    native = QComboBox(window)
    native.addItems(["one", "two"])
    native.show()
    for control in (window.career, window.state_picker, native):
        window.skip.setFocus()
        interface = QAccessible.queryAccessibleInterface(control)
        assert interface is not None
        actions = interface.actionInterface()
        assert actions is not None
        actions.doAction(QAccessibleActionInterface.setFocusAction())
        app.processEvents()
        action_focused = control.hasFocus()
        control.setFocus()
        app.processEvents()
        assert control.hasFocus() and interface.state().focused
        selector_focus.append({"name": control.accessibleName() or "plain native QComboBox",
                               "actions": actions.actionNames(), "accessible_set_focus": action_focused,
                               "widget_focus": True, "qt_accessible_focused": True})
    native.hide()
    window.skip.setFocus()
    for control in controls[1:]:
        focused = app.focusWidget()
        assert focused is not None
        QTest.keyClick(focused, Qt.Key.Key_Tab)
        app.processEvents()
        assert control.hasFocus(), control.accessibleName()
        interface = QAccessible.queryAccessibleInterface(control)
        assert interface is not None and interface.state().focused
    for control in reversed(controls[:-1]):
        focused = app.focusWidget()
        assert focused is not None
        QTest.keyClick(focused, Qt.Key.Key_Backtab)
        app.processEvents()
        assert control.hasFocus(), control.accessibleName()
        interface = QAccessible.queryAccessibleInterface(control)
        assert interface is not None and interface.state().focused
    navigation = list(window.nav_buttons.items())
    for index, (screen, button) in enumerate(navigation):
        button.setFocus()
        QTest.keyClick(button, Qt.Key.Key_Down)
        assert navigation[(index + 1) % len(navigation)][1].hasFocus()
        focused = app.focusWidget()
        assert focused is not None
        QTest.keyClick(focused, Qt.Key.Key_Up)
        assert button.hasFocus()
        QTest.keyClick(button, Qt.Key.Key_Space)
        app.processEvents()
        assert window.destination == screen and window.heading.hasFocus()
    window.navigate("OPR-01")
    window.career.setFocus()
    QTest.keyClick(window.career, Qt.Key.Key_Down)
    app.processEvents()
    assert window.career.currentIndex() == 1
    assert window.current_snapshot is not None
    assert window.current_snapshot.envelope.state.value == "missing"
    QTest.keyClick(window.career, Qt.Key.Key_Up)
    app.processEvents()
    assert window.career.currentIndex() == 0
    window.state_picker.setFocus()
    QTest.keyClick(window.state_picker, Qt.Key.Key_Down)
    app.processEvents()
    assert window.fixture_state == "loading" and window.state_picker.hasFocus()
    QTest.keyClick(window.state_picker, Qt.Key.Key_Up)
    assert window.fixture_state == "ready"
    window.navigate("OPR-01")
    for state in ("loading", "empty", "missing", "stale/unavailable", "error"):
        window.set_fixture_state(state)
        app.processEvents()
        assert window.current_snapshot is not None
        assert window.current_snapshot.envelope.state.value == state
    retry = next(b for b in window.findChildren(QPushButton) if b.text() == "Retry fixture view")
    retry.setFocus()
    QTest.keyClick(retry, Qt.Key.Key_Space)
    app.processEvents()
    assert window.current_snapshot is not None and window.current_snapshot.envelope.state.value == "ready"
    forbidden = ("sqlite3", "_sqlite3", "watchdog", "requests", "woff.database", "woff.parsers", "woff.repositories", "woff.woff_watchdog")
    assert not [name for name in sys.modules if any(name == f or name.startswith(f + ".") for f in forbidden)]
    frozen = bool(getattr(sys, "frozen", False))
    source = (json.loads((Path(getattr(sys, "_MEIPASS")) / "adoption-build.json").read_text())
              if frozen else provenance())
    window.close()
    app.processEvents()
    return {"schema": 1, "eval": "EVAL-UI-ADOPTION-MATRIX-001", "status": "passed",
            "environment": {**environment(), "qt": qVersion(), "platform_plugin": QApplication.platformName()},
            "candidate": "fixture-only", "frozen": frozen, "provenance": source,
            "first_window_ms": first_window_ms, "timing_scope": "in-process window construction; not cold startup",
            "layout": layout, "scale_factor": os.environ.get("QT_SCALE_FACTOR", "1"),
            "selector_focus": selector_focus, "controls": semantics, "keyboard": ["Tab", "Shift+Tab", "Up", "Down", "Space", "career selector", "retry"],
            "enter_activation": "not required for non-default QPushButton; Space is the activation key",
            "basic_windows_uia": "not measured by Qt interface probe",
            "screen_reader_speech": "out of scope", "fixture_boundary": "passed"}
