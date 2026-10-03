# ADR: desktop UI toolkit

Status: Proposed

Date: 2026-08-19

## Context and evidence boundary

Issue #56 records a direction for a future read-only desktop interface. It does
not approve adoption, add a runtime dependency, or claim that a production UI
exists. Compatibility evidence below was reviewed on **2026-08-19** against
official primary sources. Versions and platform policies can change and must be
checked again when adoption is proposed.

The application targets Python 3.10–3.14 and Windows 10/11. A UI must preserve
that compatibility intent, remain packageable, be testable without campaign
data, and expose accessible native-desktop semantics. The project's physically
validated reference platform for the current UI architecture decision is Windows
10. Windows 11 remains a target/upstream-compatible platform, but WoFF Mate has
not physically validated it and must not describe vendor support as project
runtime evidence. Absence of physical Windows 11 evidence does not block the
current toolkit-retention decision; future Windows 11 validation may be added if
resources become available.

Only **one Qt binding is permitted in a build environment**: PySide and PyQt
must never be installed or bundled together. Their overlapping Qt modules make
imports, plugins, packaging, and test selection ambiguous.

Qt's current official lifecycle states that Qt 6.12 is the final Qt release to
support Windows 10. Future adoption must therefore pin and validate a
Windows-10-compatible Qt line for the maintainer-validated reference platform,
or explicitly revise WoFF Mate's supported-Windows policy. This ADR does not
promote unperformed Windows 11 execution into project evidence.

## Candidates

| Candidate | Python and Windows | License and distribution | Tests, accessibility, ownership |
|---|---|---|---|
| **PySide6 + Qt Widgets** | Qt for Python publishes wheels for supported Python versions and documents Windows desktop support; adoption must verify wheel/smoke compatibility for Python 3.10–3.14 and physically validate the retained path on the maintainer's Windows 10 reference environment. Windows 11 vendor support is compatibility context, not WoFF Mate physical evidence. | Qt for Python is offered under LGPLv3/GPLv3 and commercial terms. An LGPL distribution review must cover notices, relinking/replacement rights, Qt plugins, and bundled libraries. PyInstaller has Qt/PySide hooks. Representative packaging is part of toolkit retention; clean-machine end-user validation remains a full-Q4/Gate-D distribution obligation. | `pytest-qt` supports PySide6. Widgets expose Qt accessibility interfaces and mature desktop controls. Qt Company maintains the official binding alongside Qt. |
| **PyQt6 + Qt Widgets** | Riverbank publishes current PyQt6 releases and Windows wheels; supported Python compatibility and the maintainer's physical reference environment would still require project evidence. | PyQt is GPLv3 or commercially licensed, not LGPL. That choice needs explicit project licensing approval. PyInstaller supports PyQt6 hooks; clean-machine end-user validation remains release/distribution evidence rather than a toolkit-selection prerequisite. | `pytest-qt` supports PyQt6; Qt Widgets accessibility is available. Riverbank owns the binding and SIP ecosystem rather than Qt Company. |
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
- [Qt Quick accessibility](https://doc.qt.io/qt-6/accessible-qtquick.html)

These sources establish vendor policy and toolkit capability, not WoFF Mate
runtime results. Before dependency adoption, the project must pin an eligible
release and record wheel availability for every supported Python version.

## Proposed direction

**PySide6 + Qt Widgets is the proposed direction.** It aligns the official Qt
binding with mature desktop widgets, `pytest-qt`, accessibility facilities, and
an LGPL option. This is a proposal, not an Accepted decision and not legal
advice; maintainers must approve the license and distribution obligations.

The [Issue #82 exploratory report](../ui/pyside6-spike-82.md) records local
Windows 10 measurements for PySide6/Qt 6.11.2 on Python 3.10 and 3.14, with
disposable fixture-only Widgets and PyInstaller artifacts. Its recommendation
is **Conditional Go for the architecture/product process**, not production adoption.
Warm starts, measured memory and artifact sizes meet the initial targets in
that bounded run. Uncontrolled initial starts exceeded the startup targets;
true cold starts, Windows 11, clean machines, Python 3.11 runtime smoke,
native DPI changes and screen-reader announcements remain unverified.
Default packaging also collected the GPLv3/commercial Qt Virtual Keyboard
module and omitted distribution notices. These are unresolved distribution
conditions, not an approved LGPL-only package. The report preserves raw
results and reproduction recipes; it does not satisfy the full adoption matrix
and does not claim observations that were not performed. The #81 immutable contracts are now
integrated through PR #166 and its graph prerequisite is satisfied. Historical
UIA/relocation authentication limits and the prior Linux production-isolation
regeneration at `0684805` remain recorded separately. Current native Windows 10
developer-host evidence at `1817414` adds source smoke on Python 3.12.8/3.13.1,
source/packaged execution on 3.10.11/3.14.7, corrected UIA exposure without
verified speech, authenticated same-host relocation and unchanged-spec native
production isolation. These results do not establish clean-machine, native DPI,
cold-start or licensing acceptance. Packaged 3.12/3.13 coverage remains pending
if required by the criterion; no historical measurement is promoted to current
platform validation. This ADR remains Proposed and Product Gates A/B unapproved.

## Feasibility disposition (2026-09-27)

The maintainer's current product decision does not require screen-reader speech
certification. Narrator/NVDA speech was not manually verified; UIA exposure and
Qt events do not prove announcements. Keyboard navigation, logical tab order,
visible focus, accessible names/roles, basic UIA exposure and scaling remain
applicable quality evidence. The [#82 final disposition](../ui/pyside6-spike-82.md#final-acceptance-disposition-maintainer-scope-decision-2026-09-27)
records Conditional Go without extending the spike into release certification.
Unperformed Windows 11, clean-machine, native DPI, true cold startup, remaining
Python execution and final distribution checks belong to later adoption/release
validation where applicable. This historical statement records the evidence
boundary of #82 and does not claim that those runs occurred.

## Post-spike P0 authorization (2026-09-28)

Integrated `main` revision used for this decision:
`20f742868a71e2092b8a82397304fef668638bed`, the squash merge of
[PR #165](https://github.com/Malboro66/woff-mate/pull/165).
[Issue #82](https://github.com/Malboro66/woff-mate/issues/82) is closed as
Completed, with the final **Conditional Go** feasibility disposition.

The maintainer explicitly approved this decision:

> Authorize PySide6 + Qt Widgets 6.11.2 for the experimental P0 fixture-backed
> desktop prototype in Issue #140.

This authorizes only the experimental P0 path. It does not authorize P1 or
retained production architecture; SQLite or live WoFF data access; parser,
repository, watchdog, launcher or session integration; campaign/configuration
mutation; mandatory Qt production dependencies outside the approved P0 boundary;
public distribution; Product Gate approval; or ADR acceptance.

The ADR remains **Proposed** until the post-P0 R2 review and the applicable
adoption gates are satisfied. P0 implementation/completion, R2, Product Gates
and later adoption/release validation remain pending. The completed #82 evidence
and this explicit decision satisfy #140's #82 prerequisite; no new requirement
or blocker is introduced, and P3 asset work is not a dependency of #140.

This decision does not authorize additional Narrator/NVDA, VM, Windows 11,
clean-machine, DPI or cold-start evidence work. Deferred adoption/release checks
remain deferred as described above; they are not new prerequisites for #140.
`docs/ui/evidence/issue-82-pyside6/evidence-status.json` and all historical #82
raw evidence, measurements, hashes and provenance remain unchanged. Completion
of the spike does not promote its observations into unperformed validation.

## Maintainer-available adoption scope (2026-10-03)

After the first post-P0 R2 review was integrated through PR #174, the maintainer
explicitly determined that a physical Windows 11 environment and a separate
clean-machine Windows environment are outside the project's currently available
physical and financial resources. Issue #175 re-scopes the future toolkit
retention decision so that unavailable evidence is recorded honestly rather
than fabricated or retained as a permanent impossible blocker.

For the current UI architecture decision:

- Windows 10 is the physically validated maintainer reference platform;
- Windows 11 remains a target/upstream-compatible platform but is **not**
  physically validated by WoFF Mate, and its absence does not block toolkit
  retention;
- clean-machine end-user execution remains required where full Q4, Product Gate
  D, an installer or public-distribution claims apply, but it is not a
  prerequisite for selecting the retained toolkit architecture;
- Narrator/NVDA speech certification is not required for toolkit retention;
  keyboard navigation, logical tab order, visible focus, accessible names/roles
  and basic UIA exposure remain applicable quality evidence; and
- Product Gates A and B remain authoritative for reliable data and viable
  launcher/live-product operation, but they are not evidence of toolkit
  suitability and are not prerequisites to the narrower PySide6 retention
  decision.

Accepting this ADR in a later decision would therefore select a production UI
architecture only. It would **not** authorize P1, live WoFF/SQLite integration,
launcher integration, or satisfy Product Gate A/B. Those capabilities remain
blocked by their own applicable conditions, including unresolved P1 findings
such as #96 and #142.

This re-scope does not change the historical first R2 HOLD record. Relevant
adoption-readiness changes must still be integrated and followed by a new
revision-bound R2 Full Application Review before the explicit maintainer ADR
decision.

## Adoption gates

This documentation change adds **no GUI runtime dependency or production UI
module**. Retaining PySide6 + Qt Widgets as the selected production UI
architecture remains gated by:

1. the existing #81/#82/#140 fixture-backed, contract and P0-demonstrability
   evidence plus the applicable adoption-readiness work;
2. an optional-dependency policy that preserves non-UI/headless installation and
   a clear production UI entry-point policy;
3. Python 3.10–3.14 compatibility evidence using an appropriate combination of
   CI and local/source smoke, with physical Windows 10 validation on the
   maintainer's available reference system;
4. representative production packaging and startup behavior in that available
   environment; physical Windows 11 and clean-machine end-user execution are not
   prerequisites to toolkit retention;
5. applicable accessibility quality: keyboard navigation, logical tab order,
   visible focus, accessible names/roles and basic UIA exposure, without a
   Narrator/NVDA speech-certification requirement;
6. a bundle/dependency inventory or SBOM sufficient to evaluate PySide6/Qt
   components, required notices, relinking/replacement obligations and bundled
   plugins, including explicit removal or licensing disposition of Qt Virtual
   Keyboard if present;
7. enforcement that each build environment contains exactly one Qt binding;
8. a new revision-bound R2 Full Application Review after relevant
   adoption-readiness changes are integrated; and
9. explicit maintainer acceptance of this ADR after that repeated R2.

Product Gate A (reliable data) and Product Gate B (viable launcher) remain
unapproved and fully authoritative for the capabilities they govern. They are
not toolkit-retention prerequisites. P1/live integration requires the retained
architecture decision **and** the applicable Gate A/B conditions; accepting the
toolkit alone cannot authorize live data, launcher behavior, or P1.

Clean-machine execution, supported installer behavior, installation/update/
rollback certification, signing/provenance and final public-distribution
approval remain full-Q4/release/Product-Gate-D work where applicable. Deferring
them from toolkit retention does not mark them complete or waive their later
requirements.

Issues #79 through #82 collect the completed design, fixture, contract, and
feasibility evidence. They do not accept this ADR, add a mandatory Qt
dependency, create a production UI, or approve Product Gate A or Product Gate B.

The near-term order is #81 -> #82 -> P0/#140 -> first R2 HOLD -> bounded UI
adoption-readiness -> repeated revision-bound R2 -> explicit toolkit ADR
decision. Only after the toolkit is retained **and** the applicable Product Gate
A/B conditions are satisfied may P1/live integration be authorized. Neither the
spike nor P0 silently accepts PySide6 or any other GUI toolkit, and this
governance change adds no dependency or permission to ship an experimental
artifact as production UI.