"""Inventory and fail-closed Qt disposition of the actual #177 collected bundle."""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

from .ui_adoption_support import PACKAGES, allowed_qt_file, check_bindings, sha256


def classify(name: str) -> tuple[str, str]:
    lower = name.lower()
    if 'pyside6' in lower or 'shiboken6' in lower or 'qt6' in lower:
        return 'LGPL-3.0 route plus upstream third-party terms', 'retain bounded dynamic Qt candidate; release notices/source obligations pending'
    if lower.endswith(('.dll', '.so', '.pyd')) or '.so.' in lower:
        if 'python' in lower or 'lib-dynload/' in lower:
            return 'PSF-2.0 plus stdlib third-party terms', 'retain interpreter runtime; exact release notices pending'
        return 'platform/transitive native library; component-specific terms', 'retain collected dependency; release attribution reconciliation pending'
    if 'woff/assets/' in lower or lower.startswith('notices/'):
        return 'repository/asset notices', 'retain notices and fixture-only assets'
    if lower.endswith(('.exe',)) or name == 'WoFFMateAdoption':
        return 'repository license; PyInstaller bootloader exception', 'private engineering executable; public release not authorized'
    return 'metadata/data/archive; component terms apply', 'engineering inventory; not public release SBOM'


def inventory(bundle: Path) -> dict:
    current = check_bindings()
    internal = bundle / '_internal'
    build = json.loads((internal / 'adoption-build.json').read_text(encoding='utf-8'))
    if build['environment']['versions'] != current['versions']:
        raise ValueError('Inventory environment does not match candidate package versions')
    if build['input_tree_dirty']:
        raise ValueError('Uncommitted candidate build inputs')
    collection = json.loads((internal / 'adoption-collection.json').read_text(encoding='utf-8'))
    files = []
    rejected = []
    for path in sorted(bundle.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(bundle).as_posix()
        name = relative.removeprefix('_internal/')
        if not allowed_qt_file(name):
            rejected.append(relative)
        license_route, disposition = classify(name)
        files.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': sha256(path),
                      'license_classification': license_route, 'disposition': disposition,
                      'collection_origin': collection['binary_origins'].get(name)})
    if rejected:
        raise ValueError(f'Forbidden Qt bundle components: {rejected}')
    paths = [f['path'] for f in files]
    if not any('/plugins/platforms/' in p for p in paths):
        raise ValueError('Missing candidate platform plugin')
    if not any('Qt6Widgets' in p for p in paths):
        raise ValueError('Missing candidate Qt Widgets library')
    packages = []
    for name in (*PACKAGES, 'pyinstaller', 'pyinstaller-hooks-contrib'):
        dist = metadata.distribution(name)
        canonical = dist.metadata['Name']
        records = {}
        for entry in dist.files or []:
            if entry.name in {'METADATA', 'RECORD', 'WHEEL'} and '.dist-info/' in str(entry):
                records[entry.name] = sha256(Path(str(dist.locate_file(entry))))
        packages.append({'name': canonical, 'version': dist.version,
                         'origin': f'https://pypi.org/project/{canonical}/{dist.version}/',
                         'license_metadata': dist.metadata['License-Expression'] if 'License-Expression' in dist.metadata else dist.metadata['License'] if 'License' in dist.metadata else None,
                         'metadata_sha256': records})
    return {'schema': 1, 'eval': 'EVAL-UI-ADOPTION-LICENSE-001',
            'scope': 'private engineering candidate, not public release SBOM/legal certification',
            'status': 'bounded Qt disposition passed; release obligations deferred',
            'provenance': build, 'packages': packages, 'file_count': len(files),
            'bundle_bytes': sum(f['bytes'] for f in files),
            'plugins': [p for p in paths if '/plugins/' in p],
            'qt_libraries': [p for p in paths if 'Qt6' in p and ('.dll' in p or '.so' in p)],
            'removed_by_policy': collection['removed'], 'files': files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = inventory(args.bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"Validated {result['file_count']} files; {result['bundle_bytes']} bytes")
    return 0


if __name__ == '__main__':
    sys.exit(main())
