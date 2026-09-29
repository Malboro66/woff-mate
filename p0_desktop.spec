# Experimental Issue #140 bundle, separate from the Qt-free production build.spec.
from pathlib import Path

root = Path(SPECPATH)
assets = root / 'woff' / 'assets' / 'ui'

a = Analysis(
    ['p0_launcher.py'], pathex=[str(root)], binaries=[],
    datas=[
        (str(root / 'woff/tests/fixtures/ui_states/catalog.json'), 'woff/tests/fixtures/ui_states'),
        (str(assets / 'icons' / '*.svg'), 'woff/assets/ui/icons'),
        (str(assets / 'portraits' / '*.png'), 'woff/assets/ui/portraits'),
        (str(assets / 'portraits' / '*.svg'), 'woff/assets/ui/portraits'),
        (str(assets / 'branding' / 'woff_mate_app.ico'), 'woff/assets/ui/branding'),
        (str(assets / 'branding' / 'woff_mate_symbol_light.svg'), 'woff/assets/ui/branding'),
    ],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['sqlite3', '_sqlite3', 'watchdog', 'woff.database', 'woff.parsers',
              'woff.repositories', 'woff.woff_watchdog', 'requests'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='WoFFMateP0',
          console=False, icon=str(assets / 'branding' / 'woff_mate_app.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='WoFFMateP0')
