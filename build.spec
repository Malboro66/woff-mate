# -*- mode: python ; coding: utf-8 -*-
# build.spec

from pathlib import Path
import runpy


version_data = runpy.run_path(str(Path(SPECPATH) / "woff" / "version.py"))
__version__ = version_data["__version__"]


def windows_version_file(version):
    """Create PyInstaller metadata from the runtime's canonical version."""
    numeric = tuple(int(part) for part in version.split("."))
    file_version = numeric + (0,) * (4 - len(numeric))
    target = Path("build") / "woff-version-info.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "VSVersionInfo(ffi=FixedFileInfo(filevers={0}, prodvers={0}), "
        "kids=[StringFileInfo([StringTable('040904B0', ["
        "StringStruct('FileVersion', '{1}'), StringStruct('ProductVersion', '{1}'), "
        "StringStruct('ProductName', 'WoFF Mate')])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])"
        .format(file_version, version),
        encoding="utf-8",
    )
    return str(target)


version_file = windows_version_file(__version__)

block_cipher = None

# The application is now an installable package.  Keep the repository root on
# PyInstaller's path and refer to internal modules by their fully-qualified
# package names so no runtime sys.path manipulation is required.
a = Analysis(
    ['woff_watchdog_entry.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'watchdog.observers',
        'watchdog.events',
        'watchdog.utils.dirsnapshot',
        'woff.config',
        'woff.handler',
        'woff.database',
        'woff.discovery',
        'woff.medal_cataloger',
        'woff.squadron_cataloger',
        'woff.campaign_engine',
        'woff.models',
        'woff.normalization',
        'woff.maps',
        'woff.rpg_system',
        'woff.narrative_generator',
        'woff.win_registry',
        'woff.repositories',
        'woff.repositories.base',
        'woff.repositories.pilot',
        'woff.repositories.mission',
        'woff.repositories.rpg',
        'woff.repositories.wingman',
        'woff.parsers',
        'woff.parsers.xml_parser',
        'woff.parsers.mission_log_parser',
        'woff.parsers.pilot_data_parser',
        'woff.parsers.dossier_parser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide2', 'tkinter', 'matplotlib', 'numpy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WoFFWatchdog',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WoFFWatchdog',
)
