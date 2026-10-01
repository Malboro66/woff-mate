"""Behavioral and structural checks for the synthetic desktop milestone."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import os
import subprocess
import sys

import pytest

from woff.p0_desktop.fixtures import FixturePresentation, SCREENS, ReportsView
from woff.ui_contracts import (
    MissionsSnapshot, OperationsSnapshot, PilotDossierSnapshot, PilotId,
    ScreenState, UnavailableReason,
)

ROOT = Path(__file__).resolve().parents[1]
STATES = ("ready", "loading", "empty", "missing", "stale/unavailable", "error")


def test_all_routes_and_six_states_use_closed_fixture_snapshots() -> None:
    demo = FixturePresentation()
    first, second = (career.pilot_id for career in demo.careers)
    assert first != second
    assert demo.careers[0].display_name == demo.careers[1].display_name
    assert len(SCREENS) == 7
    for screen, _, _ in SCREENS:
        for state in STATES:
            fixture_id, snapshot = demo.snapshot(screen, first, state)
            assert fixture_id and snapshot.envelope.contract_version.value == 'synthetic-ui-v1'
            assert snapshot.envelope.state is ScreenState(state)
            if screen == 'RPT-01':
                assert isinstance(snapshot, ReportsView)
            if screen == 'SYS-01':
                continue
            assert getattr(snapshot, 'pilot_id') == first
            if isinstance(snapshot, MissionsSnapshot):
                assert all(item.pilot_id == first for item in snapshot.missions)
    assert isinstance(demo.snapshot('OPR-01', first)[1], OperationsSnapshot)
    assert isinstance(demo.snapshot('MIS-01', first)[1], MissionsSnapshot)


def test_second_homonym_never_borrows_first_career_payload() -> None:
    demo = FixturePresentation()
    first, second = (career.pilot_id for career in demo.careers)
    for screen, _, _ in SCREENS[:6]:
        before = demo.snapshot(screen, first)[1]
        after = demo.snapshot(screen, second)[1]
        assert before.envelope.state is ScreenState.READY
        assert after.envelope.state is ScreenState.MISSING
        assert getattr(after, 'pilot_id') == second
        assert after.envelope.observed_at.value is None
        for key in ('pilot', 'statistics', 'missions', 'members', 'entries', 'reports'):
            assert not getattr(after, key, None)
    with pytest.raises(ValueError):
        demo.snapshot('OPR-01', PilotId('foreign-career'))
    with pytest.raises((FrozenInstanceError, AttributeError)):
        setattr(demo.snapshot('OPR-01', first)[1], 'pilot_id', second)


@pytest.mark.parametrize('screen', ('OPR-01', 'DOS-01'))
def test_empty_pilot_views_preserve_only_supplied_subject_identity(screen: str) -> None:
    demo = FixturePresentation()
    first, second = (career.pilot_id for career in demo.careers)
    case_id, snapshot = demo.snapshot(screen, first, 'empty')
    assert isinstance(snapshot, (OperationsSnapshot, PilotDossierSnapshot))
    assert case_id == 'empty-records'
    assert snapshot.envelope.state is ScreenState.EMPTY
    assert snapshot.pilot_id == first
    pilot = snapshot.pilot
    assert pilot is not None
    assert pilot.pilot_id == first
    assert pilot.display_name == demo.careers[0].display_name
    for field in (
        pilot.source_slot,
        pilot.affiliation,
        pilot.squadron_id,
        pilot.squadron_label,
        pilot.status,
    ):
        assert field.value is None
        assert field.reason is UnavailableReason.NOT_SUPPLIED
    assert snapshot.statistics is None

    _, isolated = demo.snapshot(screen, second, 'empty')
    assert isinstance(isolated, (OperationsSnapshot, PilotDossierSnapshot))
    assert isolated.envelope.state is ScreenState.MISSING
    assert isolated.pilot_id == second
    assert isolated.pilot is None
    assert isolated.statistics is None


def test_fixture_selection_and_asset_inventory_are_deterministic() -> None:
    demo = FixturePresentation()
    for screen, _, _ in SCREENS:
        assert demo.snapshot(screen, demo.careers[0].pilot_id)[0] == demo.snapshot(screen, demo.careers[0].pilot_id)[0]
    assets = ROOT / 'woff/assets/ui'
    for path in (assets / 'branding/woff_mate_app.ico',
                 assets / 'branding/woff_mate_symbol_light.svg',
                 assets / 'portraits/ui_portrait_synthetic_aster_master.png',
                 assets / 'portraits/ui_portrait_unavailable.svg'):
        assert path.is_file()
    for _, _, icon in SCREENS:
        assert (assets / f'icons/ui_nav_{icon}_20_regular.svg').is_file()
        assert (assets / f'icons/ui_nav_{icon}_20_filled.svg').is_file()


def test_qt_and_forbidden_live_modules_do_not_cross_boundary() -> None:
    forbidden = ('sqlite3', 'socket', 'urllib', 'requests', 'watchdog', 'woff.database',
                 'woff.parsers', 'woff.repositories', 'woff.woff_watchdog')
    for path in (ROOT / 'woff/p0_desktop').glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or '']
            else:
                continue
            assert not any(module == item or module.startswith(item + '.')
                           for module in modules for item in forbidden), path
            if path.name == 'fixtures.py':
                assert not any(module.startswith('PySide6') for module in modules)
    for path in (ROOT / 'woff').glob('*.py'):
        assert 'PySide6' not in path.read_text(encoding='utf-8')
    assert 'PySide6' not in (ROOT / 'build.spec').read_text(encoding='utf-8')
    assert 'PySide6' not in (ROOT / 'pyproject.toml').read_text()
    assert '"woff.p0_desktop"' in (ROOT / 'pyproject.toml').read_text()


@pytest.mark.skipif(__import__('importlib').util.find_spec('PySide6') is None,
                    reason='Optional P0 toolkit unavailable')
def test_offscreen_shell_navigation_switch_focus_and_retry() -> None:
    # Subprocess isolates QApplication and proves clean exit/reopen without a display.
    code = '''
from PySide6.QtWidgets import QApplication
from woff.p0_desktop.window import P0Window
from woff.ui_contracts import ScreenState
app = QApplication([])
for _ in range(2):
 w = P0Window(); w.show(); app.processEvents()
 assert w.current_case_id == 'pilot-ready'
 assert w.rail.width() == 256
 assert all(button.text() and button.accessibleName() for button in w.nav_buttons.values())
 for screen in w.nav_buttons:
  w.navigate(screen); app.processEvents()
  assert w.destination == screen and w.heading.hasFocus()
 w.navigate('DOS-01'); app.processEvents()
 w.career.setCurrentIndex(1); app.processEvents()
 assert w.active_career_id.value == 'synthetic-career-03'
 assert w.current_snapshot.envelope.state is ScreenState.MISSING
 assert w.current_snapshot.pilot is None and w.heading.hasFocus()
 assert all('Portrait of' not in label.accessibleName() for label in w.findChildren(__import__('PySide6').QtWidgets.QLabel))
 w.career.setCurrentIndex(0); w.set_fixture_state('error'); app.processEvents()
 assert w.current_snapshot.envelope.state is ScreenState.ERROR
 w.resize(680, 520); app.processEvents()
 assert w.rail.width() == 184 and '\\n' in w.nav_buttons['SYS-01'].text()
 assert all(button.text() and button.accessibleName() for button in w.nav_buttons.values())
 assert w.brand_name.fontMetrics().horizontalAdvance(w.brand_name.text()) <= w.brand_name.width()
 w.close()
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR='2')
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(__import__('importlib').util.find_spec('PySide6') is None,
                    reason='Optional P0 toolkit unavailable')
def test_offscreen_operations_stale_retry_and_payload_guard() -> None:
    code = '''
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from woff.p0_desktop.window import P0Window
from woff.ui_contracts import ScreenState
app = QApplication([])
w = P0Window(); w.show(); app.processEvents()
assert any(label.text() == 'Latest mission' for label in w.findChildren(QLabel))
w.set_fixture_state('stale/unavailable'); app.processEvents()
assert w.current_snapshot.envelope.state is ScreenState.STALE_OR_UNAVAILABLE
assert not any(label.text() == 'Latest mission' for label in w.findChildren(QLabel))
retry = next(button for button in w.findChildren(QPushButton)
             if button.text() == 'Retry fixture view')
retry.click(); app.processEvents()
assert w.current_snapshot.envelope.state is ScreenState.READY
assert any(label.text() == 'Latest mission' for label in w.findChildren(QLabel))
w.close()
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(__import__('importlib').util.find_spec('PySide6') is None,
                    reason='Optional P0 toolkit unavailable')
def test_offscreen_state_messages_and_context_label_semantics() -> None:
    code = '''
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton
from woff.p0_desktop.window import P0Window
from woff.ui_contracts import ScreenState
app = QApplication([])
w = P0Window(); w.show(); app.processEvents()
career_label = next(label for label in w.findChildren(QLabel) if label.text() == 'CAREER')
assert career_label.objectName() == 'muted'
w.set_fixture_state('error'); app.processEvents()
failure_message = w.current_snapshot.envelope.failure.message
notice = next(frame for frame in w.findChildren(QFrame) if frame.objectName() == 'notice')
assert [label.text() for label in notice.findChildren(QLabel)].count(failure_message) == 1
retry = next(button for button in w.findChildren(QPushButton)
             if button.text() == 'Retry fixture view')
retry.click(); app.processEvents()
assert w.current_snapshot.envelope.state is ScreenState.READY
empty_messages = {
 'OPR-01': 'No operations recorded in this synthetic view.',
 'DOS-01': 'No pilot dossier entries recorded in this synthetic view.',
 'MIS-01': 'No missions recorded in this synthetic view.',
 'SQD-01': 'No squadron members recorded in this synthetic view.',
 'JRN-01': 'No diary entries recorded in this synthetic view.',
 'RPT-01': 'No reports recorded in this synthetic view.',
 'SYS-01': 'No diagnostics recorded in this synthetic view.',
}
assert len(set(empty_messages.values())) == len(w.nav_buttons) == 7
for screen, expected in empty_messages.items():
 w.navigate(screen); w.set_fixture_state('empty'); app.processEvents()
 notice = next(frame for frame in w.findChildren(QFrame) if frame.objectName() == 'notice')
 assert [label.text() for label in notice.findChildren(QLabel)].count(expected) == 1
 if screen in {'OPR-01', 'DOS-01'}:
  labels = [label.text() for label in w.findChildren(QLabel)]
  assert 'Career identity' in labels
  assert any(label.startswith('Synthetic Pilot Aster') for label in labels)
  assert 'Service record' not in labels
w.close()
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stderr
