# Physical Windows 10 delta — maintainer attestation

**Bounded UI Adoption Readiness evidence: complete.** Attestation recorded on
2026-10-04 from the maintainer's explicit report and four supplied raw JSON files.
The maintainer performed the physical executions and manual observations; the
agent verified and archived the evidence, without claiming to operate the machine.
No remaining requirement within the authorized readiness evidence scope is open.
Integration into main, the mandatory repeated R2 and the maintainer architecture
decision remain separate future steps.

## Candidate and provenance

- Tested PR head: **`f1346f99287df4202ad6495eae17acef520d4c34`**.
- Actual CI merge checkout embedded in the candidate and raw reports:
  **`c35fe885c7f8ffeabfd3d00c773042f2fa01845b`**. This is not the branch head.
- Candidate/inventory: [Adoption Readiness run #8](https://github.com/Malboro66/woff-mate/actions/runs/37215636055),
  `adoption-private-windows-py3.10` / `adoption-evidence-windows-latest-py3.10`.
- Physical environment: **Microsoft Windows 10 Pro, 10.0.19045, build 19045**.
- Packaged interpreter: **Python 3.10.11 AMD64**; **PySide6, Qt and shiboken6 6.11.2**.
  The recorded binding list contains exactly PySide6.
- Executable SHA-256:
  `5a471827ba26431fa77544ca1e9ebaabb55a69cea5c1118d02cbe577040a94fb`.
- Inventory SHA-256:
  `c143453e97615a32897e9b7d0ba6ffa323b133096a532f7bda7433cbcb4ca4d7`.

The run metadata maps the artifact to the tested PR head. The matching raw run #8
inventory is retained as `run-8-inventory.json`. Each physical report agrees with
its executable hash, inventory hash and complete clean input provenance. Input
hashes match the reviewed candidate, allowing only text LF/CRLF checkout
normalization. This completion pass changes documentation/evidence/governance and
focused tests only; candidate source, fixtures, contracts, dependencies and
packaging remain unchanged. Earlier fixture-boundary, binding and bundle checks
therefore remain applicable to the exact executable physically tested.

## Four executions and separate manual observation

The maintainer attests that Windows display scaling itself was set to each value
below. These are real physical Windows scaling conditions, not values inferred
from a filename, an environment-variable simulation or the JSON contents.

| Real Windows scale | Startup | Compact brand/layout, no clipping | Visible focus | Tab/Shift+Tab | Navigation | Career selector keys | Fixture-state selector keys | Regression observed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 100% | passed | passed | passed | passed | passed | passed | passed | none |
| 125% | passed | passed | passed | passed | passed | passed | passed | none |
| 150% | passed | passed | passed | passed | passed | passed | passed | none |
| 200% | passed | passed | passed | passed | passed | passed | passed | none |

At every scale, the PowerShell validator completed successfully. Raw evidence
records passed native UIA names/types/focusability, selector Tab/Shift+Tab,
observable keyboard focus and Down/Up value change/restoration. The compact-width
brand-rail correction showed no clipping during manual inspection. No additional
screenshot/state matrix was needed because no regression was observed.

## Unmodified raw evidence and interpretation

The original files are retained with their exact bytes (29,491 bytes each):

- `physical-windows10-100.json`
- `physical-windows10-125.json`
- `physical-windows10-150.json`
- `physical-windows10-200.json`

All four have SHA-256
`56441592b93c933fed2edc6cc3ae33859322db272a0d70cc083f4d6aa4d5f6f1`.
Their identity is expected: this validator does not encode active Windows display
scale or a per-execution timestamp. Filenames and the maintainer attestation
supply the scale distinction. Byte identity is not evidence of a failed run, and
no artificial differences have been introduced.

The raw `visible_focus_manual = pending maintainer observation` and
`physical_layout_delta = pending...` fields remain exactly as generated. The
separate manual attestation above resolves those observations. Neither the raw
files nor historical failures have been rewritten to claim different generated
results. `index.json` supplies hashes, the scale mapping and completion status.

The native Qt 6.11.2 ComboBox programmatic **UIA SetFocus limitation remains**.
Its warning and unsuccessful action flags are preserved. Actual keyboard focus
and selector values passed independently. This is the already investigated
native toolkit/platform characteristic, not a newly discovered application defect
or justification for an artificial runtime workaround. It remains disclosed for
future R2; this pass does not perform that review or accept all residual risk.

## Completion and governance

The physical delta closes the last known authorized Adoption Readiness evidence
gap. Matrix, candidate package/startup/basic accessibility and engineering bundle
licensing/disposition evidence are complete for the tested candidate. This is not
release certification, full accessibility/speech certification or ADR acceptance.

Issue #177's evidence scope is complete; its GitHub issue stays open pending
integration. PR #178 remains Draft. No merge, Ready transition or Codex Review
request. ADR remains **Proposed**, P1 unauthorized and Product Gates A–D unapproved.
Historical first R2 remains **HOLD / Conditional No-Go**. Required next sequence:
readiness completion → authorized integration into main → mandatory new
revision-bound R2 Full Application Review → explicit maintainer architecture
decision. No known readiness evidence blocker remains; applicable review/merge
controls and explicit integration authorization still apply.
