import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { assertScale, assertState, assertSurface, assertTabSequence, acceptanceCases } from "./browser-acceptance.mjs";

// A real captured row seeds checker mutation tests. This replay is explicitly
// not a live browser test; live cases are driven by runAcceptanceCase(tab,...).
const observed = JSON.parse(await readFile(new URL("./fixtures/dossier-observation.json", import.meta.url), "utf8"));
const validate = sample => { assertSurface(sample); assertScale(sample, 100); assertState(sample, "complete"); };
test("the measured Dossier observation satisfies the checker", () => validate(observed));

for (const [name, mutate] of [
  ["unchanged scale canvas", s => { s.canvas.width = 960; }],
  ["unchanged rail", s => { s.rail.width = 272; }],
  ["wrong statistics columns", s => { s.statsColumns = 2; }],
  ["unmoved side column", s => { s.sideAfterLedger = true; }],
  ["small pointer width", s => { s.controls[10].rect.width = 31; }],
  ["small pointer height", s => { s.controls[10].rect.height = 31; }],
  ["small primary target", s => { s.controls[1].rect.height = 39; }],
  ["prohibited creation control", s => { s.controls[10].name = "Create career"; }],
  ["prohibited deletion control", s => { s.controls[10].name = "Delete pilot"; }],
  ["unreviewed intent", s => { s.controls[10].intent = "unknown"; }],
  ["missing heading focus", s => { s.headingFocused = false; }],
  ["false zero", s => { s.fields[0].display = "0"; }],
  ["private diagnostic", s => { s.mainText += " Traceback SELECT * FROM pilots"; }],
  ["small font despite empty failure list", s => { s.fonts.minimum = 8; }],
]) test(`rejects ${name}`, () => { const sample = structuredClone(observed); mutate(sample); assert.throws(() => validate(sample)); });

test("a sequence truncated at the fixture matrix is rejected", () => {
  const stops = observed.controls.slice(0, 10).map(c => ({ name: c.name, tag: c.tag, visibleFocus: true, inViewport: true, boxShadow: "0 0 0 3px #f7f2e6, 0 0 0 6px #7d5a18" }));
  assert.throws(() => assertTabSequence(observed, stops));
});
test("case manifest covers every required class", () => {
  assert.equal(acceptanceCases.filter(c => c.kind === "surface").length, 60);
  assert.equal(acceptanceCases.filter(c => c.kind === "state").length, 14);
  assert.equal(acceptanceCases.filter(c => c.kind === "status").length, 12);
  assert.equal(acceptanceCases.filter(c => c.kind === "keyboard").length, 28);
});
