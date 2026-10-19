# WoFF Mate — suggested GitHub repository profile

**Status:** proposal for maintainer review under Issue #213. These values have **not** been applied to the GitHub repository's About/settings fields by this documentation PR.

## Proposed About fields

**Repository description** (short; public):

> Local-first companion for Wings Over Flanders Fields: pilot careers, missions, squadrons and desktop UI development.

**Website/homepage:** **Leave empty for now.** The [published UI V2 site](https://woff-mate-ui-v2.pilotohans.chatgpt.site/) is a *design reference*, not an official released product website. It is linked prominently in the README instead. Do not silently use a design prototype as the product homepage.

**Suggested GitHub topics:**

`wings-over-flanders-fields`, `woff`, `flight-simulation`, `world-war-i`, `python`, `pyside6`, `sqlite`, `windows`, `desktop-companion`, `open-source`

## Implementation boundary

The GitHub repository description, About homepage and topics are repository metadata; unlike tracked files, they cannot be changed through a branch/PR diff. After the maintainer accepts this proposal, update them directly in the repository About settings, with the current README and governance checkpoint as the source of truth. The existing public README changes can be reviewed and merged independently of this manual settings change.

Do not claim publicly that WoFF Mate has a finished native desktop, live-data P1, a launcher, interactive social RPG, an approved Product Gate A–D, or an available public release. Preserve the historical R1 FAIL, first R2 HOLD, repeated R2 GO and subsequent explicit toolkit ADR acceptance as separate revision-bound decisions.

## Visual assets and public screenshots

- Use only the approved source-controlled WM branding under `woff/assets/ui/branding/` for the project's public identity. Do not treat the older root `icon.png` as the approved master.
- The two README screenshots in `docs/ui/evidence/issue-140-p0/` must remain explicitly labeled **synthetic, fixture-only P0**.
- The published UI V2 site is a **visual reference**; any future site capture must be verified, labeled, and reviewed before embedding. No new binary asset is proposed by #213.

## Maintainer review checklist

- [ ] README introductory claims align with the current integrated `main` and accepted governance decisions.
- [ ] All displayed images come from existing verified repository assets and are not presented as live WoFF data.
- [ ] Quick Start, compatibility, source-data safety, privacy, license and disclaimer remain unchanged in substance.
- [ ] Documentation links and the two fixture-only screenshot paths resolve.
- [ ] No source code, schema, dependency, CI, release, gate, or asset changes.
- [ ] Maintainer explicitly decides whether to merge Draft PR and whether to apply the suggested About metadata.
