"""Replay bounded #82 evidence without importing Qt or production services."""
from pathlib import Path
import ast
import hashlib
import json

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/ui/evidence/issue-82-pyside6'


def read_json(name):
    return json.loads((EVIDENCE / name).read_text(encoding='utf-8-sig'))


def test_evidence_digest_and_synthetic_provenance():
    names = set()
    for line in (EVIDENCE / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        assert Path(name).name == name
        assert name not in names
        names.add(name)
        # .gitattributes preserves LF in the byte-sensitive textual archive.
        content = (EVIDENCE / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected, name
    assert names == {p.name for p in EVIDENCE.iterdir() if p.name != 'SHA256SUMS'}
    provenance = read_json('provenance.json')
    assert provenance['baseline'] == '0c8a3d3c8afd4a9addae1cd5902faa79aa4f7445'
    fixture = ROOT / 'woff/tests/fixtures/ui_states/catalog.json'
    assert hashlib.sha256(fixture.read_text(encoding='utf-8').encode()).hexdigest() == provenance['catalog_sha256']
    assert provenance['native_windows11_verified'] is False
    assert provenance['clean_machine_verified'] is False
    assert provenance['cold_boot_verified'] is False


@pytest.mark.parametrize('configuration', ['source310', 'source314', 'packaged310', 'packaged314'])
def test_recorded_runs_are_complete_and_bounded(configuration):
    for audit in [False, True]:
        rows = read_json(f'final-{configuration}' + ('-audit' if audit else '') + '.json')
        scales = [1, 1.25, 1.5, 2] if audit else [1]
        assert [(r['requested_scale'], r['repetition']) for r in rows] == [
            (scale, repeat) for scale in scales for repeat in [1, 2, 3]]
        for row in rows:
            assert row['cold_boot_verified'] is False
            assert row['exit_code'] == 0
            assert not row['stderr_nonempty'] and not row['qt_messages']
            result = row['result']
            assert result['qt'] == result['pyside'] == '6.11.2'
            assert result['platform_plugin'] == 'windows'
            assert result['os_build'] == 19045
            assert result['dpr'] == row['requested_scale']
            assert not result['forbidden_imports']
            assert row['launch_to_paint_seconds'] > 0
            assert result['rss_bytes'] > 0 and result['private_bytes'] > 0
            if audit:
                checks = result['checks']
                assert checks and all(c['passed'] for c in checks)
                assert {'tab_order', 'reverse_tab_order', 'navigation', 'keyboard_retry',
                        'geometry_and_semantics'} == {c['check'] for c in checks}
                assert {'ready', 'loading', 'empty', 'error'} == {
                    {'pilot-ready': 'ready', 'loading-selected': 'loading',
                     'empty-records': 'empty', 'error-query-selected': 'error'}[c['fixture']]
                    for c in checks if 'fixture' in c}
                assert {'Button', 'ComboBox', 'StaticText'} == {
                    c['role'] for c in checks if c['check'] == 'geometry_and_semantics'}


def test_wheel_matrix_covers_all_supported_pythons():
    rows = read_json('wheel-metadata.json')
    assert len(rows) == 20
    assert {r['python'] for r in rows} == {'3.10', '3.11', '3.12', '3.13', '3.14'}
    assert all(r['compatible_wheels'] for r in rows)
    for name in ['inventory10.json', 'inventory14.json']:
        assert read_json(name)['bindings'] == ['PySide6']


def test_shell_recipe_has_no_application_integration():
    tree = ast.parse((EVIDENCE / 'shell.py.txt').read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or '').split('.')[0])
    assert imported <= {'time', 'json', 'os', 'sys', 'pathlib', 'PySide6', 'psutil'}
    assert 'Status: Proposed' in (ROOT / 'docs/architecture/adr-ui-toolkit.md').read_text(encoding='utf-8')
    for name in ['pyproject.toml', 'requirements.txt']:
        content = (ROOT / name).read_text(encoding='utf-8').lower()
        assert 'pyside' not in content and 'pyqt' not in content


def test_packaging_evidence_preserves_distribution_blocker():
    builds = read_json('build-inventory.json')
    assert len(builds) == 2
    for build in builds:
        paths = [f['path'] for f in build['files']]
        assert not any('pyqt' in p.lower() or 'pyside2' in p.lower() for p in paths)
        assert any(p.endswith('/qwindows.dll') for p in paths)
        # Default hooks included a GPL/commercial module; never erase this evidence.
        assert any(p.endswith('/Qt6VirtualKeyboard.dll') for p in paths)
    isolation = read_json('production-isolation.json')
    assert isolation['qt_distributions'] == []
    assert isolation['forbidden_wheel_entries'] == []
    assert isolation['forbidden_executable_entries'] == []
    assert isolation['executable_help_exit_code'] == 0


def test_native_exposure_is_not_reported_as_speech():
    exposure = read_json('uia.json')
    assert exposure['window_found'] is True
    assert exposure['announcements_verified'] is False
    controls = {e['name']: e for e in exposure['elements']}
    for name in ['Operations', 'Pilot Dossier', 'Missions', 'Squadron',
                 'War Diary', 'Reports', 'Data & System Status', 'Retry view']:
        assert controls[name]['role'] == 'ControlType.Button'
        assert controls[name]['keyboard_focusable'] and not controls[name]['offscreen']
    assert controls['Synthetic fixture state']['role'] == 'ControlType.ComboBox'


def test_debug_logging_teardown_correction_is_verified():
    original = read_json('preliminary-plugin-discovery.json')
    assert len(original) == 2 and all(r['exit_code'] == 0xC0000005 for r in original)
    final = read_json('plugin-discovery.json')
    assert len(final) == 6
    assert all(r['exit_code'] == 0 and not r['warning_kinds'] for r in final)
    assert all('qwindows.dll' in r['loaded_dll_basenames'] for r in final)
