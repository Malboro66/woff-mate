"""Replay bounded #82 evidence without importing Qt or production services."""
from pathlib import Path
import ast
import hashlib
import json
import runpy
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/ui/evidence/issue-82-pyside6'


def read_json(name):
    return json.loads((EVIDENCE / name).read_text(encoding='utf-8-sig'))


def load_recipe_functions(name, *function_names):
    path = EVIDENCE / name
    tree = ast.parse(path.read_text(encoding='utf-8'))
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)) or (
                isinstance(node, ast.FunctionDef) and node.name in function_names):
            selected.append(node)
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


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
    isolation = read_json('production-isolation-current.json')
    evidence_contract()['validate_production_result'](isolation)


def test_production_recipe_removes_stale_wheels_and_fails_closed(tmp_path):
    recipe = (EVIDENCE / 'production_check.py.txt').read_text(encoding='utf-8')
    assert "wheel_output = recreate_output_directory(root / 'production-wheel', root)" in recipe
    assert 'wheel = select_single_wheel(wheel_output)' in recipe
    assert "contract['validate_production_result'](result)" in recipe
    helpers = load_recipe_functions(
        'production_check.py.txt', 'recreate_output_directory', 'select_single_wheel')
    root = tmp_path / 'issue82'
    root.mkdir()
    output = root / 'production-wheel'
    output.mkdir()
    (output / 'stale.whl').write_bytes(b'stale')

    recreated = helpers['recreate_output_directory'](output, root)
    assert list(recreated.iterdir()) == []
    current = recreated / 'current.whl'
    current.write_bytes(b'current')
    assert helpers['select_single_wheel'](recreated) == current
    (recreated / 'ambiguous.whl').write_bytes(b'ambiguous')
    with pytest.raises(AssertionError):
        helpers['select_single_wheel'](recreated)


def test_relocation_recipe_binds_artifact_inventory_and_historical_results(tmp_path):
    recipe = (EVIDENCE / 'relocate.py.txt').read_text(encoding='utf-8')
    assert 'destination = copy_and_verify(' in recipe
    assert 'completed = subprocess.run(command, cwd=observation_root, timeout=120)' in recipe
    assert "assert completed.returncode == 0 and local_result.is_file()" in recipe
    helpers = load_recipe_functions(
        'relocate.py.txt', 'inventory', 'inventory_sha256', 'json_sha256', 'copy_and_verify')
    builds = {build['python']: build for build in read_json('build-inventory.json')}
    provenance = read_json('relocation-provenance.json')
    assert [record['python'] for record in provenance] == ['310', '314']
    for record in provenance:
        build = builds[record['python']]
        assert record['source_artifact'] == f"dist{record['python']}/Issue82"
        assert record['relocated_artifact'] == f"relocation with spaces/package{record['python']}"
        assert record['source_sha256'] == build['source_sha256']
        assert record['artifact_inventory_sha256'] == helpers['inventory_sha256'](build['files'])
        assert record['artifact_files'] == len(build['files'])
        assert record['artifact_bytes'] == build['total_bytes']
        assert record['result_json_sha256'] == helpers['json_sha256'](EVIDENCE / record['result'])
        rows = read_json(record['result'])
        assert [(row['configuration'], row['repetition']) for row in rows] == [
            (f"relocated{record['python']}", repeat) for repeat in [1, 2, 3]]
        assert all(row['exit_code'] == 0 and not row['stderr_nonempty'] and
                   not row['qt_messages'] for row in rows)

    source = tmp_path / 'source'
    source.mkdir()
    (source / 'Issue82.exe').write_bytes(b'executable')
    expected = helpers['inventory'](source)
    relocation_root = tmp_path / 'relocation with spaces'
    relocation_root.mkdir()
    destination = helpers['copy_and_verify'](
        source, relocation_root / 'package310', expected, relocation_root)
    assert helpers['inventory'](destination) == expected


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
    recipe = (EVIDENCE / 'uia.ps1.txt').read_text(encoding='utf-8')
    assert "@('uia-local-stdout.txt', 'uia-local-stderr.txt', 'uia.json')" in recipe
    assert 'Start-Process -FilePath $env:ComSpec' in recipe
    assert '$spikeProcess.Refresh()' in recipe
    assert '-not $spikeResult.window_found' in recipe
    assert '$spikeResult.exit_code -ne 0' in recipe


def test_debug_logging_teardown_correction_is_verified():
    original = read_json('preliminary-plugin-discovery.json')
    assert len(original) == 2 and all(r['exit_code'] == 0xC0000005 for r in original)
    final = read_json('plugin-discovery.json')
    assert len(final) == 6
    assert all(r['exit_code'] == 0 and not r['warning_kinds'] and
               (not r['stderr_nonempty'] or r['stderr_only_library_unload']) for r in final)
    assert all('qwindows.dll' in r['loaded_dll_basenames'] for r in final)


@pytest.mark.parametrize(('stderr', 'accepted'), [
    ('', True),
    ('qt.core.library: "C:/temp/qwindows.dll" unloaded library\n', True),
    ('unexpected loader diagnostic\n', False),
    ('qt.core.library: "C:/temp/qwindows.dll" unloaded library\nunexpected\n', False),
])
def test_plugin_probe_stderr_contract(stderr, accepted):
    recipe = (EVIDENCE / 'plugin_probe.py.txt').read_text(encoding='utf-8')
    assert 'stderr_accepted = stderr_is_accepted(result.stderr)' in recipe
    assert "'validate_plugin_results'](results)" in recipe
    helpers = load_recipe_functions('plugin_probe.py.txt', 'stderr_is_accepted')
    assert helpers['stderr_is_accepted'](stderr) is accepted


def test_summary_recipe_names_exact_final_inputs():
    recipe = (EVIDENCE / 'summarize.py.txt').read_text(encoding='utf-8')
    assert "glob('final-*-audit.json')" not in recipe
    assert "['source310', 'source314', 'packaged310', 'packaged314']" in recipe


def evidence_contract():
    return runpy.run_path(str(EVIDENCE / 'evidence_contract.py.txt'))


def test_uia_recipe_collects_diagnostics_before_acceptance():
    recipe = (EVIDENCE / 'uia.ps1.txt').read_text(encoding='utf-8')
    assert '--uia-result' in recipe and '--stderr' in recipe and '--stdout' in recipe
    assert '$LASTEXITCODE -ne 0' in recipe


@pytest.mark.parametrize('stderr', [None, True, 0, 1, '', 'false', [], {}])
def test_production_stderr_evidence_fails_closed(stderr):
    result = read_json('production-isolation.json')
    if stderr is not None:
        result['executable_help_stderr_nonempty'] = stderr
    with pytest.raises(ValueError, match='stderr'):
        evidence_contract()['validate_production_result'](result)


def test_archived_production_result_requires_explicit_clean_stderr():
    # The original Windows result is preserved, but is not current proof.
    with pytest.raises(ValueError, match='stderr'):
        evidence_contract()['validate_production_result'](read_json('production-isolation.json'))
    result = read_json('production-isolation-current.json')
    assert result['executable_help_stderr_nonempty'] is False
    evidence_contract()['validate_production_result'](result)


@pytest.mark.parametrize('path', [
    'Qt6Core.dll', '_internal/Qt6Widgets.dll', 'vendor\\Qt6Network.DLL',
    './vendor/Qt6Gui.dll', 'plugins/platforms/qwindows.dll',
    '_internal\\plugins\\platforms\\qwindows.dll', 'lib/libQt6Core.so.6.11.2',
    'lib/QtCore.framework/Versions/A/QtCore', 'lib/libQt6Gui.6.dylib',
    'plugins/imageformats/qjpeg.dll', 'platforms/libqxcb.so',
    'PySide6/QtCore.pyd', 'PySide6_Essentials-6.11.2.dist-info/METADATA',
    'PyQt6/Qt6/bin/Qt6Core.dll', 'shiboken6/Shiboken.pyd', 'bin/qtpaths6.exe',
    'bin/qmake.exe', 'plugins/platforms/',
])
def test_raw_qt_artifact_is_detected(path):
    assert evidence_contract()['is_forbidden_entry'](path)


@pytest.mark.parametrize('path', [
    'woff/ui_contracts.py', 'acquireQt6Core.dll.txt', 'docs-of-third-party.txt',
    'vendor/notqt6core.dll', 'plugins/platforms_notes.txt', 'my_pyside_notes.txt',
    'lib/equator.so', 'tools/qmake_notes.md', 'Qt6Core.dll.backup.txt',
    'application/platforms/windows.py', 'photos/qwindows.png',
])
def test_unrelated_artifact_names_are_allowed(path):
    assert not evidence_contract()['is_forbidden_entry'](path)


def test_retained_relocation_mismatch_is_preserved(tmp_path):
    helpers = load_recipe_functions('relocate.py.txt', 'inventory', 'copy_and_verify')
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'Issue82.exe').write_bytes(b'current')
    root = tmp_path / 'relocation with spaces'
    root.mkdir()
    retained = root / 'package310'
    retained.mkdir()
    (retained / 'Issue82.exe').write_bytes(b'historical-unverified')
    before = helpers['inventory'](retained)
    with pytest.raises((AssertionError, ValueError), match='retained'):
        helpers['copy_and_verify'](source, retained, helpers['inventory'](source), root)
    assert helpers['inventory'](retained) == before


def test_verified_retained_relocation_is_not_replaced(tmp_path, monkeypatch):
    helpers = load_recipe_functions('relocate.py.txt', 'inventory', 'copy_and_verify')
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'Issue82.exe').write_bytes(b'verified')
    root = tmp_path / 'relocation with spaces'
    root.mkdir()
    expected = helpers['inventory'](source)
    destination = helpers['copy_and_verify'](source, root / 'package310', expected, root)
    def forbid_delete(*args, **kwargs):
        pytest.fail('authenticated retained bundle must not be destroyed')
    monkeypatch.setattr(helpers['shutil'], 'rmtree', forbid_delete)
    assert helpers['copy_and_verify'](source, destination, expected, root) == destination
    assert helpers['inventory'](destination) == expected


def uia_observation():
    return {'window_found': True, 'elements': [{'name': 'Retry view',
            'role': 'ControlType.Button', 'keyboard_focusable': True, 'offscreen': False}],
            'exit_code': 0, 'announcements_verified': False, 'stderr_nonempty': False,
            'stdout_unexpected': False, 'qt_message_count': 0}


@pytest.mark.parametrize('field', ['stderr_nonempty', 'stdout_unexpected', 'qt_message_count', 'exit_code'])
@pytest.mark.parametrize('value', [None, True, 'false', '', [], {}, 1])
def test_uia_missing_or_malformed_diagnostics_fail(field, value):
    result = uia_observation()
    if value is None:
        del result[field]
    else:
        result[field] = value
    with pytest.raises(ValueError):
        evidence_contract()['validate_uia_result'](result)


def test_uia_clean_observation_passes():
    evidence_contract()['validate_uia_result'](uia_observation())


@pytest.mark.parametrize(('stderr', 'exit_code'), [('', 0), ('Qt plugin warning\n', 1)])
def test_uia_collector_reads_redirected_stderr(tmp_path, stderr, exit_code):
    result = tmp_path / 'uia.json'
    result.write_text(json.dumps(uia_observation()), encoding='utf-8')
    err = tmp_path / 'stderr.txt'
    err.write_text(stderr, encoding='utf-8')
    out = tmp_path / 'stdout.txt'
    events = [{'event': 'window'}, {'event': 'first_paint'},
              {'event': 'result', 'result': {'messages': [], 'forbidden_imports': []}}]
    out.write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')
    completed = subprocess.run([sys.executable, str(EVIDENCE / 'evidence_contract.py.txt'),
                               '--uia-result', str(result), '--stderr', str(err),
                               '--stdout', str(out)], capture_output=True)
    assert completed.returncode == exit_code
    recorded = json.loads(result.read_text(encoding='utf-8'))
    assert recorded['stderr_nonempty'] is bool(stderr)
    assert stderr.strip() not in recorded.values() if stderr else True


@pytest.mark.parametrize('failure', ['missing_stderr', 'invalid_utf8', 'missing_messages',
                                    'qt_warning', 'unexpected_stdout', 'duplicate_event'])
def test_uia_collector_rejects_incomplete_or_unexpected_diagnostics(tmp_path, failure):
    err, out = tmp_path / 'stderr.txt', tmp_path / 'stdout.txt'
    if failure != 'missing_stderr':
        err.write_bytes(b'\xff' if failure == 'invalid_utf8' else b'')
    payload = {'messages': [], 'forbidden_imports': []}
    if failure == 'missing_messages':
        del payload['messages']
    if failure == 'qt_warning':
        payload['messages'] = [{'kind': 'QtWarningMsg', 'message': 'local diagnostic'}]
    events = [{'event': 'window'}, {'event': 'first_paint'}, {'event': 'result', 'result': payload}]
    if failure == 'duplicate_event':
        events.append(events[-1])
    out.write_text('\n'.join(json.dumps(e) for e in events) +
                   ('\nunexpected loader output' if failure == 'unexpected_stdout' else ''), encoding='utf-8')
    helper = evidence_contract()
    with pytest.raises((ValueError, OSError, UnicodeError)):
        result = helper['collect_uia_diagnostics'](uia_observation(), err, out)
        helper['validate_uia_result'](result)


def test_explicit_false_production_stderr_passes_other_valid_invariants():
    result = read_json('production-isolation.json')
    result['executable_help_stderr_nonempty'] = False
    evidence_contract()['validate_production_result'](result)


@pytest.mark.parametrize('kind', ['wheel', 'executable'])
@pytest.mark.parametrize('path', ['Qt6Core.dll', 'plugins\\platforms\\qwindows.dll'])
def test_production_replay_recomputes_qt_inventory(kind, path):
    result = read_json('production-isolation.json')
    result['executable_help_stderr_nonempty'] = False
    result[kind + '_entries'].append(path)
    with pytest.raises(ValueError, match='classification'):
        evidence_contract()['validate_production_result'](result)


@pytest.mark.parametrize('field,value', [('stderr_nonempty', None), ('stderr_nonempty', 0),
    ('exit_code', False), ('launch_to_paint_seconds', None), ('launch_to_paint_seconds', float('nan')),
    ('qt_messages', None), ('stdout_unexpected', None), ('stdout_unexpected', True)])
def test_measurement_replay_rejects_incomplete_observations(field, value):
    rows = read_json('final-source310.json')
    for row in rows:
        row['stdout_unexpected'] = False
    rows[0][field] = value
    with pytest.raises(ValueError):
        evidence_contract()['validate_measurements'](rows, 'final-source310', [1])


@pytest.mark.parametrize('configuration', ['source310', 'source314', 'packaged310', 'packaged314'])
def test_historical_measurements_require_explicit_limited_replay(configuration):
    helper = evidence_contract()
    for audit in (False, True):
        label = 'final-' + configuration + ('-audit' if audit else '')
        rows = read_json(label + '.json')
        scales = [1, 1.25, 1.5, 2] if audit else [1]
        with pytest.raises(ValueError, match='stdout'):
            helper['validate_measurements'](rows, label, scales)
        helper['validate_measurements'](rows, label, scales, historical=True)


def test_relocation_rejects_links_and_preserves_outside_target(tmp_path):
    helpers = load_recipe_functions('relocate.py.txt', 'inventory', 'copy_and_verify')
    source, root, outside = tmp_path / 'source', tmp_path / 'relocation with spaces', tmp_path / 'outside'
    for path in (source, root, outside):
        path.mkdir()
    (source / 'Issue82.exe').write_bytes(b'current')
    (outside / 'keep').write_bytes(b'untouched')
    destination = root / 'package310'
    try:
        destination.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Creating symbolic links is not permitted on this Windows environment')
    with pytest.raises(ValueError, match='unsafe'):
        helpers['copy_and_verify'](source, destination, helpers['inventory'](source), root)
    assert (outside / 'keep').read_bytes() == b'untouched'


@pytest.mark.parametrize('name', ['plugin-discovery.json', 'source-plugin-discovery.json'])
def test_plugin_replay_requires_explicit_historical_limit(name):
    helpers = evidence_contract()
    rows = read_json(name)
    with pytest.raises(ValueError, match='stdout|contradictory'):
        helpers['validate_plugin_results'](rows)
    helpers['validate_plugin_results'](rows, historical=True)


@pytest.mark.parametrize('field', ['stderr_nonempty', 'stderr_only_library_unload'])
@pytest.mark.parametrize('value', [None, 'false', 0, 1, [], {}])
def test_plugin_replay_rejects_missing_or_malformed_stderr(field, value):
    rows = read_json('plugin-discovery.json')
    rows[0][field] = value
    with pytest.raises(ValueError, match='stderr'):
        evidence_contract()['validate_plugin_results'](rows, historical=True)


def test_historical_observations_and_provenance_are_not_rewritten():
    status = read_json('evidence-status.json')
    for name, digest in status['historical_payload_sha256'].items():
        assert hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest() == digest, name
    assert status['issue_82_complete'] is False
    assert status['recommendation'] == 'Conditional Go'
    assert 'superseded' in status['limited_evidence']['relocation-provenance.json'].lower()
    with pytest.raises(ValueError):
        evidence_contract()['validate_uia_result'](read_json('uia.json'))


def test_regenerated_production_evidence_matches_current_build_inputs():
    result = read_json('production-isolation-current.json')
    assert result['evidence_kind'] == 'regenerated production isolation'
    assert result['platform'] in {'Linux', 'Windows'}
    assert result['build_exit_codes'] == [0, 0]
    for source_name, key in [('production_check.py.txt', 'observer_sha256'),
                             ('evidence_contract.py.txt', 'contract_sha256')]:
        assert hashlib.sha256((EVIDENCE / source_name).read_bytes()).hexdigest() == result[key]
    for entry in result['build_inputs']:
        # The observer builds committed bytes, independent of Windows checkout EOL.
        data = subprocess.check_output(['git', 'show', 'HEAD:' + entry['path']], cwd=ROOT)
        assert len(data) == entry['bytes']
        assert hashlib.sha256(data).hexdigest() == entry['sha256'], entry['path']
    payload = json.dumps(result['build_inputs'], sort_keys=True, separators=(',', ':')).encode()
    assert hashlib.sha256(payload).hexdigest() == result['build_inputs_sha256']
    assert [entry['path'] for entry in result['wheel_inventory']] == result['wheel_entries']
    assert sorted({e['path'] for e in result['executable_inventory']} | set(result['executable_directories']) |
                  {'embedded/' + n for n in result['embedded_entries']}) == result['executable_entries']
    evidence_contract()['validate_production_result'](result)


def test_linux_observer_adjusts_only_the_executable_filename():
    helper = load_recipe_functions('production_check.py.txt', 'observer_spec')
    original = (ROOT / 'build.spec').read_text(encoding='utf-8')
    assert helper['observer_spec'](original, False) == original
    adjusted = helper['observer_spec'](original, True)
    assert adjusted.replace("name='WoFFWatchdog.exe',", "name='WoFFWatchdog',", 1) == original
    assert adjusted.count("name='WoFFWatchdog.exe',") == 1
    assert adjusted.count("name='WoFFWatchdog',") == 1
    with pytest.raises(ValueError, match='spec layout'):
        helper['observer_spec']('unrecognized spec', True)


def test_executable_inventory_includes_empty_qt_plugin_directories(tmp_path):
    (tmp_path / 'plugins/platforms').mkdir(parents=True)
    (tmp_path / 'unrelated').mkdir()
    (tmp_path / 'unrelated/notice.txt').write_text('ordinary data', encoding='utf-8')
    helper = load_recipe_functions('production_check.py.txt', 'artifact_entries')
    entries = helper['artifact_entries'](tmp_path)
    assert 'plugins/platforms/' in entries
    assert [p for p in entries if evidence_contract()['is_forbidden_entry'](p)] == ['plugins/platforms/']
