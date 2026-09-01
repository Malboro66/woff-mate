import assert from "node:assert/strict";
import test from "node:test";
import * as presentation from "../app/view-models.ts";

const identity = {
  careerId: "rfc-14a-08f2", careerReferenceLabel: "WoFF Pilot 1 · RFC-14A-08F2",
  displayName: "Arthur Bennett", rank: "Lt.", serviceOrNationLabel: "RFC",
  squadronLabel: "14 Squadron", careerStatus: "Active",
  aircraftLabel: "Sopwith Camel F.1", stationLabel: "Bailleul Aerodrome",
};
const statuses = [
  ["Active", "Active"], ["KIA", "Killed in Action (KIA)"],
  ["PoW", "Prisoner of War (PoW)"], ["MIA", "Missing in Action (MIA)"],
  ["Invalided Out", "Invalided Out"], ["Survived War", "Survived War"],
  ["Lightly Wounded", "Lightly Wounded"], ["Seriously Wounded", "Seriously Wounded"],
];

for (const [input, label] of statuses) test(`lossless status: ${input}`, () => {
  const field = presentation.createPilotDossierSnapshot({ ...identity, careerStatus: input }, "complete").data.careerStatus;
  assert.equal(field.value, input);
  assert.equal(field.display, label);
  assert.equal(field.state, "known");
});

for (const value of [null, "", "   "]) test(`absent status stays unknown: ${JSON.stringify(value)}`, () => {
  const field = presentation.createPilotDossierSnapshot({ ...identity, careerStatus: value }, "complete").data.careerStatus;
  assert.equal(field.display, "Unknown");
  assert.equal(field.value, null);
  assert.equal(field.state, "unknown");
});

test("future authoritative status is retained with an unsupported-mapping reason", () => {
  const field = presentation.createPilotDossierSnapshot({ ...identity, careerStatus: "Transferred (future)" }, "complete").data.careerStatus;
  assert.equal(field.display, "Transferred (future)");
  assert.equal(field.value, "Transferred (future)");
  assert.equal(field.reason, "pilot_status_mapping_unsupported");
});

const fields = ["missions", "flightMinutes", "claimsCount", "confirmedVictories", "skill", "reputation"];
test("empty collections do not manufacture zero career totals", () => {
  const empty = presentation.createPilotDossierSnapshot(identity, "empty");
  assert.equal(empty.state, "empty");
  assert.deepEqual(empty.data.recentServiceEvents, []);
  assert.deepEqual(empty.data.recentVictories, []);
  assert.deepEqual(empty.data.recentDecorations, []);
  assert.equal(empty.data.missions.value, 27);
});

test("zero, unknown and mixed partial fields remain distinct", () => {
  const zero = presentation.createPilotDossierSnapshot(identity, "zeroes").data;
  const unknown = presentation.createPilotDossierSnapshot(identity, "unknown").data;
  for (const name of fields) {
    assert.equal(zero[name].state, "known");
    assert.equal(zero[name].value, 0);
    assert.equal(unknown[name].state, "unknown");
    assert.equal(unknown[name].value, null);
    assert.equal(unknown[name].display, "Unknown");
  }
  const partial = presentation.createPilotDossierSnapshot(identity, "partial").data;
  assert.deepEqual(fields.map(name => partial[name].state), ["known", "unavailable", "unknown", "known", "invalid", "unavailable"]);
});

for (const state of ["loading", "no-career", "missing", "truncated", "unsupported", "unreadable", "error", "unavailable"]) {
  test(`${state} never borrows a complete snapshot`, () => {
    const snapshot = presentation.createPilotDossierSnapshot(identity, state);
    assert.equal(snapshot.data, null);
    assert.equal(snapshot.identityKey, state === "no-career" ? null : identity.careerId);
    assert.ok(snapshot.reason);
  });
}

test("stale retains a safely labelled snapshot and observation time", () => {
  const snapshot = presentation.createPilotDossierSnapshot(identity, "stale");
  assert.equal(snapshot.state, "stale");
  assert.equal(snapshot.meta.freshness, "stale");
  assert.equal(snapshot.meta.observedAt, "14 AUG 1917 · 23:41");
  assert.equal(snapshot.data.missions.value, 27);
  assert.ok(Object.isFrozen(snapshot.data));
});
