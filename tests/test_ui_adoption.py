"""Focused regression checks for the bounded #177 candidate, Qt optional."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import ui_adoption_support as policy

ROOT = Path(__file__).resolve().parents[1]


def test_optional_dependency_policy():
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import pip._vendor.tomli as tomllib  # type: ignore[no-redef]
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    assert project['optional-dependencies']['ui'] == ['PySide6==6.11.2']
    assert not any('pyside' in dep.lower() or 'pyqt' in dep.lower() for dep in project['dependencies'])


@pytest.mark.parametrize('alternate', ['PyQt5', 'PyQt6', 'PySide2', 'PySide'])
@pytest.mark.parametrize('discovery', ['metadata', 'import'])
def test_reject_mixed_bindings(monkeypatch, alternate, discovery):
    names = ['PySide6', alternate] if discovery == 'metadata' else ['PySide6']
    monkeypatch.setattr(policy.metadata, 'distributions', lambda: [SimpleNamespace(metadata={'Name': n}) for n in names])
    monkeypatch.setattr(policy.importlib.util, 'find_spec', lambda name: object() if name in (['PySide6', alternate] if discovery == 'import' else []) else None)
    with pytest.raises(RuntimeError, match='Expected Qt bindings'):
        policy.check_bindings()


def test_base_requires_zero_bindings_and_ui_exact_version(monkeypatch):
    monkeypatch.setattr(policy.metadata, 'distributions', lambda: [])
    monkeypatch.setattr(policy.importlib.util, 'find_spec', lambda name: None)
    assert policy.check_bindings(base=True) == {'bindings': [], 'versions': {}}
    with pytest.raises(RuntimeError):
        policy.check_bindings()
    monkeypatch.setattr(policy.importlib.util, 'find_spec', lambda name: object() if name == 'PySide6' else None)
    monkeypatch.setattr(policy.metadata, 'version', lambda name: '6.11.1')
    with pytest.raises(RuntimeError, match='must all be'):
        policy.check_bindings()
    with pytest.raises(RuntimeError):
        policy.check_bindings(base=True)


@pytest.mark.parametrize('path', [
    'PySide6/Qt/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll',
    'PySide6/Qt/lib/libQt6VirtualKeyboard.so.6', 'PySide6/Qt6Quick.dll',
    'PySide6/Qt/plugins/imageformats/qpdf.dll', 'PySide6/Qt/plugins/tls/qopensslbackend.dll',
    'PySide6/Qt/plugins/platforms/qfuture.dll', 'PyQt6/QtCore.pyd',
])
def test_forbidden_bundle_components_fail_closed(path):
    assert not policy.allowed_qt_file(path)


def test_allow_retained_widgets_platform_and_svg():
    for name in ['PySide6/Qt6Widgets.dll', 'PySide6/Qt/lib/libQt6Svg.so.6',
                 'PySide6/Qt/plugins/platforms/qwindows.dll', 'PySide6/QtTest.pyd']:
        assert policy.allowed_qt_file(name)


def test_candidate_boundary_and_historical_render_inputs_unchanged():
    forbidden = {'sqlite3', 'requests', 'watchdog', 'woff.database', 'woff.parsers', 'woff.repositories', 'woff.woff_watchdog'}
    for filename in ['ui_adoption_launcher.py', 'scripts/ui_adoption_probe.py', 'scripts/ui_adoption_support.py']:
        for node in ast.walk(ast.parse((ROOT / filename).read_text())):
            names = ([n.name for n in node.names] if isinstance(node, ast.Import) else
                     [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
            assert not any(n == f or n.startswith(f + '.') for n in names for f in forbidden)
    for name in ['woff/p0_desktop/window.py', 'woff/p0_desktop/fixtures.py',
                 'woff/ui_contracts.py', 'p0_desktop.spec', 'build.spec']:
        prior = subprocess.check_output(['git', 'rev-parse', f'741bad8192517c4ade38e9e718845f086beff849:{name}'], cwd=ROOT).strip()
        # Git's canonical blob respects checkout LF/CRLF filters on Windows.
        current = subprocess.check_output(['git', 'hash-object', f'--path={name}', name], cwd=ROOT).strip()
        assert current == prior


@pytest.mark.skipif(policy.importlib.util.find_spec('PySide6') is None, reason='Optional UI extra unavailable')
def test_actual_candidate_keyboard_and_accessibility(tmp_path):
    output = tmp_path / 'smoke.json'
    result = subprocess.run([sys.executable, 'ui_adoption_launcher.py', '--smoke', '--evidence', str(output)],
                            cwd=ROOT, env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_text())
    assert data['status'] == 'passed'
    assert len(data['controls']) == 10
    assert data['environment']['qt'] == policy.VERSION
    assert data['basic_windows_uia'] == 'not measured by Qt interface probe'
