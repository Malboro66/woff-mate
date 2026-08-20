# ADR: desktop UI toolkit

Status: Proposed

Date: 2026-08-19

## Context and evidence boundary

Issue #56 records a direction for a future read-only desktop interface. It does
not approve adoption, add a runtime dependency, or claim that a production UI
exists. Compatibility evidence below was reviewed on **2026-08-19** against
official primary sources. Versions and platform policies can change and must be
checked again when adoption is proposed.

The application supports Python 3.10–3.14 and Windows 10/11. A UI must preserve
that range, remain packageable, be testable without campaign data, and expose
accessible native-desktop semantics. Only **one Qt binding is permitted in a
build environment**: PySide and PyQt must never be installed or bundled
together. Their overlapping Qt modules make imports, plugins, packaging, and
test selection ambiguous.

## Candidates

| Candidate | Python and Windows | License and distribution | Tests, accessibility, ownership |
|---|---|---|---|
| **PySide6 + Qt Widgets** | Qt for Python publishes wheels for supported Python versions and documents Windows desktop support; adoption must verify wheels and smoke Python 3.10–3.14 on Windows 10/11. | Qt for Python is offered under LGPLv3/GPLv3 and commercial terms. An LGPL distribution review must cover notices, relinking/replacement rights, Qt plugins, and bundled libraries. PyInstaller has Qt/PySide hooks, but a clean-machine packaging spike remains required. | `pytest-qt` supports PySide6. Widgets expose Qt accessibility interfaces and mature desktop controls. Qt Company maintains the official binding alongside Qt. |
| **PyQt6 + Qt Widgets** | Riverbank publishes current PyQt6 releases and Windows wheels; the complete supported Python/Windows matrix must still be smoke-tested. | PyQt is GPLv3 or commercially licensed, not LGPL. That choice needs explicit project licensing approval. PyInstaller supports PyQt6 hooks, with the same clean-machine spike requirement. | `pytest-qt` supports PyQt6; Qt Widgets accessibility is available. Riverbank owns the binding and SIP ecosystem rather than Qt Company. |
| **Qt Quick/QML with PySide6 or PyQt6** | Uses a viable Qt 6 binding, so binding compatibility is inherited; QML modules and graphics backends add another Windows validation surface. | Binding terms remain PySide6 LGPL/GPL/commercial or PyQt6 GPL/commercial. Packaging must collect QML imports and plugins. | `pytest-qt` can drive the Qt application, but QML-facing tests need additional seams. Qt Quick has accessibility APIs, while custom controls demand deliberate accessible names, roles, focus, and keyboard behavior. It offers richer composition at greater architecture and packaging cost than this read-only shell needs. |
| **Legacy Qt 5 bindings (PySide2/PyQt5)** | Rejected/deferred for new work: they do not provide a credible full Python 3.10–3.14 foundation, and Qt 5 is outside the intended current Qt line. | They retain binding-specific LGPL/GPL/commercial obligations and legacy packaging concerns. | Existing ecosystems are mature, but selecting a legacy binding would create avoidable maintenance and migration ownership. |

Official evidence:

- [Qt for Python getting started and supported Python versions](https://doc.qt.io/qtforpython-6/gettingstarted.html)
- [Qt 6 supported platforms, including Windows](https://doc.qt.io/qt-6/supported-platforms.html)
- [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html)
- [Qt licensing obligations](https://www.qt.io/licensing/open-source-lgpl-obligations)
- [Riverbank PyQt licensing](https://www.riverbankcomputing.com/commercial/license-faq)
- [PyInstaller Qt hooks](https://pyinstaller.org/en/stable/hooks-config.html#qt)
- [`pytest-qt` supported bindings](https://pytest-qt.readthedocs.io/en/latest/intro.html#pytest-qt)
- [Qt accessibility overview](https://doc.qt.io/qt-6/accessible.html)
- [Qt Quick accessibility](https://doc.qt.io/qt-6/qml-qtquick-accessibility.html)

These sources establish vendor policy and toolkit capability, not WoFF Mate
runtime results. Before dependency adoption, the project must pin an eligible
release and record wheel availability for every supported Python version.

## Proposed direction

**PySide6 + Qt Widgets is the proposed direction.** It aligns the official Qt
binding with mature desktop widgets, `pytest-qt`, accessibility facilities, and
an LGPL option. This is a proposal, not an Accepted decision and not legal
advice; maintainers must approve the license and distribution obligations.

No startup performance has been measured. Import time, first-window time,
memory, plugin discovery, and packaged executable size are uncertain. A future
spike must measure cold and warm startup on representative Windows 10/11
machines across the supported Python range, using a documented harness and
fixture-backed shell. Results must be compared to an agreed budget before
adoption; estimates or upstream anecdotes are not acceptance evidence.

## Adoption gates

This documentation PR adds **no GUI runtime dependency or production UI
module**. Adoption remains gated by:

1. explicit acceptance of this ADR;
2. applicable Product Gate A (reliable data) and Gate B (viable launcher)
   decisions—neither is approved here;
3. an optional-dependency policy that preserves non-UI installation;
4. Windows 10/11 and Python 3.10–3.14 smoke coverage;
5. a PyInstaller clean-machine packaging and licensing spike;
6. sanitized, non-personal fixtures and accessibility/test plans; and
7. enforcement that each build environment contains exactly one Qt binding.
