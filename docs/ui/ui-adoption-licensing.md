# Issue #177 — candidate engineering licensing disposition

This is a private engineering candidate, not public release authorization or legal
certification. Inventory is generated from the **actual collected bundle**, not
from everything present in the build environment. No toolkit ADR decision is made.

## Selected route and bundle scope

The candidate uses the community PySide6/shiboken6 6.11.2 distributions with the
LGPL-3.0 route for the retained Qt modules (Core, Gui, Widgets, Svg, Test and Linux
DBus when required indirectly by Gui). QtTest is retained solely to execute the
candidate keyboard probe. Qt plugins are restricted to Windows/offscreen platform,
ICO image decoding and the Windows widget style. PNG is built into QtGui; SVG
rendering uses the explicit QtSvg API. The Linux candidate is offscreen engineering
evidence, not a supported Linux desktop distribution.

Qt Virtual Keyboard, QML/Quick, PDF, WebEngine, network/TLS plugins and unused
platform/image plugins are removed. No GPL-only Virtual Keyboard route is selected.
The spec filters collection; inventory validation fails on a forbidden or unknown
Qt module/plugin. An unexpected component requires a reviewed policy change.

The PySide6 extra necessarily installs Essentials and Addons upstream wheels.
Installed Addons metadata is not evidence that all Addons modules were bundled.
The inventory distinguishes distribution identity from collected binary contents.

## Obligations and disposition

| Component | Engineering disposition | Before public distribution |
|---|---|---|
| PySide6, shiboken6 and retained Qt modules/plugins | LGPL-3.0 route; dynamically linked, unmodified libraries in a one-directory bundle | Complete corresponding-source availability, copyright/license/third-party notices, replacement/relinking instructions and LGPL user rights; do not prohibit reverse engineering needed to debug modifications |
| Qt third-party code (including compiled-in code) | Upstream module attributions remain applicable; inventory is not proof that embedded third-party code is absent | Complete per-version upstream source/SBOM attribution reconciliation under release work |
| Python and stdlib extensions | PSF license plus per-module third-party terms | Include exact interpreter notices and upstream third-party notices |
| Windows Python hashlib crypto library | OpenSSL 1.1 lineage uses OpenSSL/SSLeay terms; OpenSSL 3 lineage uses Apache-2.0; exact collected file identity is inventoried | Include the notices matching the actual interpreter build; this is hashing support, not a network runtime feature |
| Windows VC/UCRT/API-set libraries | Microsoft runtime redistributable terms, collected with Python/Qt; versions/hashes remain bundle-specific | Verify applicable redistribution terms and notices before public distribution |
| PyInstaller bootloader | GPL with bootloader exception; build tool identity recorded | Preserve applicable exception and notices; no claim that the whole application becomes GPL |
| System/transitive native libraries | Actual filenames, hashes and collection source identifiers retained; platform-specific attribution review recorded separately | Complete native-library license/source reconciliation for the release platform |
| WoFF Mate and committed UI assets | Repository LICENSE and asset-specific notices govern | Retain the included project/asset notices; synthetic assets do not supply campaign facts |

The one-directory mechanism leaves Qt shared libraries replaceable; it does not
certify end-user replacement, installer behavior, signing or legal compliance.
No public distribution is authorized while those release obligations are pending.
Engineering retention suitability is bounded to this explicit candidate scope.

## Primary references (checked 2026-10-04)

- https://doc.qt.io/qt-6.11/licensing.html
- https://doc.qt.io/qt-6.11/qtvirtualkeyboard-index.html
- https://doc.qt.io/qtforpython-6/licenses.html
- https://www.qt.io/development/open-source-lgpl-obligations
- https://pyinstaller.org/en/stable/license.html

Exact installed wheel METADATA/RECORD hashes and upstream package URLs are recorded
in the inventory. This engineering inventory is not the final public release SBOM.
For Linux host libraries the collection record also preserves Debian package
identity/version and copyright hash, with machine-readable package-declared license
contexts where available. These package-wide identifiers are attribution evidence,
not a claim that every license applies to every binary byte. Windows native files
are classified separately as interpreter, OpenSSL or Microsoft runtime components.
