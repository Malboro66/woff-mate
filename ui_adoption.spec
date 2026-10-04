# #177 retention candidate; preserves the historical P0 and headless specs.
import json
import sys
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH)
sys.path.insert(0, str(root))
from scripts.ui_adoption_support import (
    PACKAGES, allowed_qt_file, binary_origin, check_bindings, environment, provenance,
)

check_bindings()
assets = root / 'woff/assets/ui'
record = provenance()
if record['input_tree_dirty']:
    raise RuntimeError('Commit candidate inputs before producing revision-bound packaging evidence')
record['environment'] = environment()
record_path = root / 'build/adoption-build.json'
record_path.parent.mkdir(parents=True, exist_ok=True)
record_path.write_text(json.dumps(record, indent=2), encoding='utf-8')
datas = [(str(record_path), '.'), (str(root / 'LICENSE'), 'notices'),
         (str(root / 'docs/ui/ui-adoption-licensing.md'), 'notices'),
         (str(root / 'woff/tests/fixtures/ui_states/catalog.json'), 'woff/tests/fixtures/ui_states')]
for folder, patterns in {'icons': ['*.svg', '*.md', 'LICENSES/*.txt'],
                         'portraits': ['*.png', '*.svg', '*.md'],
                         'branding': ['*.ico', '*.svg', '*.md']}.items():
    for pattern in patterns:
        for path in (assets / folder).glob(pattern):
            datas.append((str(path), str(path.parent.relative_to(root))))
for package in PACKAGES:
    datas += copy_metadata(package)

a = Analysis(['ui_adoption_launcher.py'], pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['sqlite3', '_sqlite3', 'watchdog', 'woff.database', 'woff.parsers',
              'woff.repositories', 'woff.woff_watchdog', 'requests', 'PyQt5', 'PyQt6',
              'PySide2', 'PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick'],
    noarchive=False)
# PyInstaller's broad QtGui hooks collect image/platform plugins the fixture shell
# never uses. Filter both TOCs and validate the resulting actual bundle separately.
removed = [entry[0] for entry in a.binaries + a.datas if not allowed_qt_file(entry[0])]
a.binaries = [entry for entry in a.binaries if allowed_qt_file(entry[0])]
a.datas = [entry for entry in a.datas if allowed_qt_file(entry[0])]
origins = {entry[0]: binary_origin(Path(entry[1]))
           for entry in a.binaries if Path(entry[1]).is_file()}
policy_path = root / 'build/adoption-collection.json'
policy_path.write_text(json.dumps({'removed': sorted(removed), 'binary_origins': origins}, indent=2), encoding='utf-8')
a.datas.append(('adoption-collection.json', str(policy_path), 'DATA'))
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='WoFFMateAdoption',
          console=False, icon=str(assets / 'branding/woff_mate_app.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='WoFFMateAdoption')
