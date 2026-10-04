"""Focused regression checks for the bounded #177 candidate, Qt optional."""
from __future__ import annotations

import ast
import hashlib
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
    for name in ['woff/p0_desktop/fixtures.py',
                 'woff/ui_contracts.py', 'p0_desktop.spec', 'build.spec']:
        prior = subprocess.check_output(['git', 'rev-parse', f'741bad8192517c4ade38e9e718845f086beff849:{name}'], cwd=ROOT).strip()
        # Git's canonical blob respects checkout LF/CRLF filters on Windows.
        current = subprocess.check_output(['git', 'hash-object', f'--path={name}', name], cwd=ROOT).strip()
        assert current == prior


@pytest.mark.skipif(policy.importlib.util.find_spec('PySide6') is None, reason='Optional UI extra unavailable')
@pytest.mark.parametrize('scale', ['1', '1.25', '1.5', '2'])
def test_actual_candidate_keyboard_and_accessibility(tmp_path, scale):
    output = tmp_path / 'smoke.json'
    result = subprocess.run([sys.executable, 'ui_adoption_launcher.py', '--smoke', '--evidence', str(output)],
                            cwd=ROOT, env=dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR=scale),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_text())
    assert data['status'] == 'passed'
    assert len(data['controls']) == 10
    assert data['environment']['qt'] == policy.VERSION
    assert len(data['layout']) == 5
    assert all(row['brand_advance'] <= row['brand_available'] for row in data['layout'])
    assert len(data['selector_focus']) == 3
    assert all(row['qt_accessible_focused'] for row in data['selector_focus'])
    assert data['basic_windows_uia'] == 'not measured by Qt interface probe'


def test_pre_fix_evidence_remains_intact_and_truthful():
    evidence = ROOT / 'docs/ui/evidence/issue-177-adoption'
    assert evidence.is_dir(), 'Committed adoption evidence must not disappear'
    index = json.loads((evidence / 'index.json').read_text())
    assert index['physical_windows10_delta'] == 'pending'
    assert index['adr_status'] == 'Proposed'
    assert index['p1_authorized'] is False
    required = {f'source-linux-py{v}.json' for v in ('310', '311', '312', '313', '314')}
    required |= {f'{kind}-{system}-py{v}.json' for system in ('linux', 'windows')
                 for v in ('310', '314') for kind in ('bundled', 'inventory')}
    required |= {f'{kind}-windows-py{v}.json' for v in ('310', '314') for kind in ('source', 'hosted-uia')}
    assert set(index['sha256']) == required
    expected_inputs = set(policy.provenance()['input_sha256'])
    for relative, expected in index['sha256'].items():
        path = evidence / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        report = json.loads(path.read_text(encoding='utf-8-sig'))
        record = report['provenance']
        assert record['input_tree_dirty'] is False
        assert len(record['revision']) == 40
        inputs = record['input_sha256']
        assert set(inputs) == expected_inputs
        assert record['input_digest'] == hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        # Authorized correction supersedes these inputs; the pre-fix archive
        # stays byte-identical and is never advertised as current execution.
        corrected = {'woff/p0_desktop/window.py', 'scripts/ui_adoption_probe.py',
                     'scripts/validate_ui_adoption_windows.ps1'}
        for name, digest in inputs.items():
            if name in corrected:
                continue
            data = (ROOT / name).read_bytes()
            candidates = [data]
            try:
                data.decode('utf-8')
            except UnicodeDecodeError:
                pass
            else:
                # Raw evidence retains native bytes; Git checkouts may use CRLF.
                canonical = data.replace(b'\r\n', b'\n')
                candidates.extend([canonical, canonical.replace(b'\n', b'\r\n')])
            assert digest in {hashlib.sha256(value).hexdigest() for value in candidates}, name
        if 'inventory' in relative:
            assert all(policy.allowed_qt_file(f['path']) for f in report['files'])
            assert report['provenance']['environment']['qt'] == policy.VERSION
        else:
            assert report['status'] == 'passed'
        if 'hosted-uia' in relative:
            assert report['physical_windows10'] is False
            assert len(report['controls']) == 10
            assert all(c['focusable'] for c in report['controls'])


@pytest.mark.skipif(policy.importlib.util.find_spec('PySide6') is None, reason='Optional UI extra unavailable')
def test_compact_rail_reserves_native_brand_metrics():
    # Deterministically exercise metrics wider than the original 120px slot,
    # including on hosts without the Windows Georgia font.
    code = """
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from woff.p0_desktop.window import P0Window
app = QApplication([])
w = P0Window()
w.show()
w.brand_name.setText('WoFF Mate WWWW')
w.resize(680, 520)
QTest.qWait(100)
advance = w.brand_name.fontMetrics().horizontalAdvance(w.brand_name.text())
assert advance > 120
assert w.brand_name.width() >= advance, (advance, w.brand_name.width())
assert w.brand_symbol.geometry().right() < w.brand_name.geometry().left()
w.close()
"""
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT,
                            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
