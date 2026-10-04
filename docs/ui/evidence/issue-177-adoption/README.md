# Issue #177 — executed adoption-candidate evidence

Status: **partial; readiness not complete**. PR #178 remains Draft. The ADR remains
Proposed, historical first R2 remains HOLD, P1 remains unauthorized and Product
Gates A–D remain unapproved. No repeated R2 is performed here.

## Recorded execution

| Evidence | Actual environment / result |
|---|---|
| Source UI smoke | Linux Python 3.10.21, 3.11.16, 3.12.14, 3.13.15 and 3.14.7: passed |
| Local endpoint packages | Linux Python 3.10.21 and 3.14.7: actual bundle startup, key events, Qt accessibility and inventory passed |
| Hosted Windows endpoints | Python 3.10 and 3.14: source smoke, optional dependency isolation, package build/startup and bundle inventory passed |
| Native UIA | Hosted **Windows Server 2025**, not physical Windows 10/11: ten representative controls expose names/roles/focusability; button focus acquisition passed; two combo `SetFocus` requests did not acquire focus and remain explicitly recorded |
| Standard CI #324 | Passed on `b695c3e2b5eaad24565a2ba00e16f4931f7c6524` |
| Adoption workflow #5 | **Failed** on both Windows jobs at the preserved compact/200% historical P0 regression, after independent candidate evidence/artifacts were collected; five Linux jobs passed |
| Physical Windows 10 | **Pending**: bounded candidate launch, native UIA, visible keyboard focus and one targeted compact/200% check |

The compact finding is 135 pixels of Georgia brand text advance in a 120-pixel
label at 680×520 and `QT_SCALE_FACTOR=2`. Waiting for layout settlement did not
resolve it. No rendering correction or risk waiver is made in this evidence pass.
The failure remains an enforced workflow gate and an open #177 finding.

## Provenance and interpretation

Local reports were executed at `3326bec1a00c2653cbb7d37908d9c53258d7e005`.
Hosted reports were executed by workflow
[37192998653](https://github.com/Malboro66/woff-mate/actions/runs/37192998653)
on the PR merge checkout for head `b695c3e2b5eaad24565a2ba00e16f4931f7c6524`.
The raw `provenance.revision` preserves the actual checkout revision, including
GitHub's temporary merge commit; tests verify archived **input bytes**, not the
continued reachability of that temporary Git object after a future squash.

All candidate inputs remain identical across these observations apart from native
checkout line endings. Each report retains its actual raw input SHA-256 values;
the regression permits only Git checkout LF/CRLF differences for UTF-8 text and
requires exact binary bytes. Later documentation/test-only changes do not rebind
these executions to a newer commit or fabricate another run.

`index.json` hashes all 17 raw reports. Nested `.gitattributes` preserves their
bytes on every checkout, including the PowerShell-generated reports. The focused
test requires the entire matrix/report set, validates current input coverage and
hashes, and rejects forbidden Qt modules/plugins in the recorded inventories.

Inventories enumerate actual files, package versions/metadata hashes, Qt runtime
version, libraries/plugins, source identities, license classifications and removal
dispositions. Both Windows bundles retain Core/Gui/Widgets/Svg/Test and four
plugins: qwindows, qoffscreen, qico and qmodernwindowsstyle. Virtual Keyboard,
QML/Quick, PDF and unused plugins are removed. See the
[engineering licensing disposition](../../ui-adoption-licensing.md) for scope and
the explicit release obligations. These are not public release SBOMs or legal
certification.

Timing values are **in-process first-window construction**, not cold-process
startup certification. Successful packaged invocations separately prove launch
and clean exit. Bundle byte totals are the sum of inventoried paths (including
symlink targets on Linux), not compressed download or unique allocated disk size.

## Physical delta handoff

Use the matching Windows bundle and inventory from workflow #5 artifacts:

- `adoption-private-windows-py3.10` / `adoption-evidence-windows-latest-py3.10`;
- or the equivalent Python 3.14 pair.

The private bundles expire after seven days; the same candidate can be rebuilt
from the recorded source revision using the documented pinned tools. Do not mix
an inventory from one endpoint/build with another bundle. Archive JSON reports
here only after verifying their provenance; do not commit executables or logs.

Follow [the physical Windows 10 procedure](../../ui-adoption-readiness.md).
The maintainer must supply the physical attestation and visible-focus observation.
Hosted Server execution is not physical Windows 10 evidence. The combo UIA focus
limitation and compact-layout failure must remain visible to the later R2 review.
