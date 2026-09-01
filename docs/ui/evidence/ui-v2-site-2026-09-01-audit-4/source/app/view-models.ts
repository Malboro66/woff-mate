export type PrototypeFixtureState = "complete" | "loading" | "empty" | "partial" | "no-career" | "missing" | "truncated" | "unsupported" | "unreadable" | "error" | "stale" | "zeroes" | "unknown" | "unavailable";
export type SnapshotState = "loading" | "ready" | "empty" | "missing" | "stale" | "unavailable" | "error";
export type Freshness = "current" | "stale" | "unknown";
export type FieldState = "known" | "unknown" | "unavailable" | "invalid";

export type PresentationField<T> = Readonly<{
  state: FieldState;
  value: T | null;
  display: string;
  reason: string | null;
}>;

export type SnapshotMetadata = Readonly<{
  contract: string;
  version: string;
  authority: string;
  observedAt: string | null;
  freshness: Freshness;
  warnings: readonly string[];
  unavailableFields: readonly string[];
  safeSourceSummary: string;
}>;

export type SnapshotEnvelope<T> = Readonly<{
  identityKey: string | null;
  state: SnapshotState;
  reason: string | null;
  meta: SnapshotMetadata;
  data: T | null;
}>;

export type CareerIdentityInput = Readonly<{
  careerId: string;
  careerReferenceLabel: string;
  displayName: string;
  rank: string | null;
  serviceOrNationLabel: string | null;
  squadronLabel: string | null;
  careerStatus: string | null;
  aircraftLabel: string | null;
  stationLabel: string | null;
}>;

export type ServiceEventViewModel = Readonly<{
  id: string;
  occurredAt: string;
  title: string;
  detail: string;
}>;

export type VictoryPreviewViewModel = Readonly<{
  id: string;
  occurredAt: string;
  targetLabel: string;
  statusLabel: string;
}>;

export type PilotDossierViewModel = Readonly<{
  careerId: string;
  careerReferenceLabel: PresentationField<string>;
  displayName: string;
  rank: PresentationField<string>;
  serviceOrNationLabel: PresentationField<string>;
  squadronLabel: PresentationField<string>;
  careerStatus: PresentationField<string>;
  aircraftLabel: PresentationField<string>;
  stationLabel: PresentationField<string>;
  portraitAsset: PresentationField<string>;
  dataState: "complete" | "partial" | "empty" | "zeroes" | "unknown";
  missions: PresentationField<number>;
  flightMinutes: PresentationField<number>;
  claimsCount: PresentationField<number>;
  confirmedVictories: PresentationField<number>;
  skill: PresentationField<number>;
  reputation: PresentationField<number>;
  recentServiceEvents: readonly ServiceEventViewModel[];
  recentVictories: readonly VictoryPreviewViewModel[];
  recentDecorations: readonly string[];
  lastUpdatedLabel: PresentationField<string>;
  safeSourceSummary: string;
}>;

type DeepReadonly<T> = T extends (...args: never[]) => unknown
  ? T
  : T extends readonly (infer U)[]
    ? readonly DeepReadonly<U>[]
    : T extends object
      ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
      : T;

export function deepFreeze<T>(value: T): DeepReadonly<T> {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child);
    Object.freeze(value);
  }
  return value as DeepReadonly<T>;
}

function known<T extends string | number>(value: T, display = String(value)): PresentationField<T> {
  return Object.freeze({ state: "known" as const, value, display, reason: null });
}

function unknown<T>(reason: string): PresentationField<T> {
  return deepFreeze({ state: "unknown" as const, value: null, display: "Unknown", reason });
}

function unavailable<T>(reason: string): PresentationField<T> {
  return deepFreeze({ state: "unavailable" as const, value: null, display: "Not available", reason });
}

function invalid<T>(reason: string): PresentationField<T> {
  return deepFreeze({ state: "invalid" as const, value: null, display: "Invalid", reason });
}

function optionalIdentity(value: string | null, unknownToken: string, reason: string): PresentationField<string> {
  return !value || value === unknownToken ? unknown<string>(reason) : known(value);
}

const pilotStatusLabels: Readonly<Record<string, string>> = deepFreeze({
  Active: "Active",
  KIA: "Killed in Action (KIA)",
  PoW: "Prisoner of War (PoW)",
  MIA: "Missing in Action (MIA)",
  "Invalided Out": "Invalided Out",
  "Survived War": "Survived War",
  "Lightly Wounded": "Lightly Wounded",
  "Seriously Wounded": "Seriously Wounded",
});

export function presentPilotStatus(value: string | null): PresentationField<string> {
  if (!value?.trim() || value === "Unknown") return unknown("career_status_unknown");
  const label = Object.hasOwn(pilotStatusLabels, value) ? pilotStatusLabels[value] : null;
  return label ? known(value, label) : deepFreeze({
    state: "known" as const, value, display: value, reason: "pilot_status_mapping_unsupported",
  });
}

const envelopeStateByFixture: Readonly<Record<PrototypeFixtureState, SnapshotState>> = deepFreeze({
  complete: "ready",
  loading: "loading",
  empty: "empty",
  partial: "ready",
  "no-career": "missing",
  missing: "missing",
  truncated: "unavailable",
  unsupported: "unavailable",
  unreadable: "error",
  error: "error",
  stale: "stale",
  zeroes: "ready",
  unknown: "ready",
  unavailable: "unavailable",
});

const reasonByFixture: Readonly<Record<PrototypeFixtureState, string | null>> = deepFreeze({
  complete: null,
  loading: "fixture_loading",
  empty: "collection_empty",
  partial: "source_partial",
  "no-career": "career_not_selected",
  missing: "record_missing",
  truncated: "record_truncated",
  unsupported: "source_format_unsupported",
  unreadable: "source_unreadable",
  error: "query_error",
  stale: "snapshot_age_exceeded",
  zeroes: "authoritative_zero",
  unknown: "field_value_unknown",
  unavailable: "source_not_available",
});

function seedForCareer(careerId: string) {
  if (careerId === "raf-41b-22c1") return deepFreeze({ missions: 12, flightMinutes: 1268, claims: 5, victories: 3, skill: 64, reputation: 52 });
  if (careerId === "career-14b8") return deepFreeze({ missions: 4, flightMinutes: 337, claims: 0, victories: 0, skill: 41, reputation: 29 });
  return deepFreeze({ missions: 27, flightMinutes: 2778, claims: 11, victories: 8, skill: 73, reputation: 61 });
}

function contentFields(identity: CareerIdentityInput, fixtureState: PrototypeFixtureState) {
  const seed = seedForCareer(identity.careerId);
  if (fixtureState === "zeroes") return deepFreeze({
    missions: known(0, "0"), flightMinutes: known(0, "0.0 h"), claims: known(0, "0"), victories: known(0, "0"), skill: known(0, "0"), reputation: known(0, "0"),
  });
  if (fixtureState === "unknown") return deepFreeze({
    missions: unknown<number>("missions_unknown"), flightMinutes: unknown<number>("flight_time_unknown"), claims: unknown<number>("claims_unknown"), victories: unknown<number>("victories_unknown"), skill: unknown<number>("skill_unknown"), reputation: unknown<number>("reputation_unknown"),
  });
  if (fixtureState === "partial") return deepFreeze({
    missions: known(seed.missions), flightMinutes: unavailable<number>("flight_time_not_supplied"), claims: unknown<number>("claims_unknown"), victories: known(seed.victories), skill: invalid<number>("skill_out_of_range"), reputation: unavailable<number>("reputation_not_supplied"),
  });
  return deepFreeze({
    missions: known(seed.missions), flightMinutes: known(seed.flightMinutes, `${(seed.flightMinutes / 60).toFixed(1)} h`), claims: known(seed.claims), victories: known(seed.victories), skill: known(seed.skill), reputation: known(seed.reputation),
  });
}

export function createPilotDossierSnapshot(identity: CareerIdentityInput, fixtureState: PrototypeFixtureState): SnapshotEnvelope<PilotDossierViewModel> {
  const state = envelopeStateByFixture[fixtureState];
  const reason = reasonByFixture[fixtureState];
  const contentState = fixtureState === "partial" || fixtureState === "unknown" || fixtureState === "zeroes" || fixtureState === "empty" || fixtureState === "complete" || fixtureState === "stale";
  const freshness: Freshness = fixtureState === "stale" ? "stale" : fixtureState === "complete" || fixtureState === "empty" || fixtureState === "zeroes" ? "current" : "unknown";
  const observedAt = freshness === "stale" ? "14 AUG 1917 · 23:41" : freshness === "current" ? "15 AUG 1917 · 23:41" : null;
  const warnings = fixtureState === "partial" ? ["coverage_incomplete", "field_states_mixed"] : fixtureState === "unknown" ? ["field_values_unknown"] : [];

  if (!contentState) return deepFreeze({
    identityKey: fixtureState === "no-career" ? null : identity.careerId,
    state,
    reason,
    meta: {
      contract: "PilotDossierSnapshot",
      version: "pilot-dossier.v1",
      authority: "Sanitized fixture query service",
      observedAt,
      freshness,
      warnings: reason ? [reason] : [],
      unavailableFields: ["dossier"],
      safeSourceSummary: "Fixture-backed contract; no live database or file binding.",
    },
    data: null,
  });

  const fields = contentFields(identity, fixtureState);
  const emptyCollections = fixtureState === "empty" || fixtureState === "zeroes";
  const serviceEvents: readonly ServiceEventViewModel[] = emptyCollections ? [] : fixtureState === "partial" || fixtureState === "unknown" ? [
    { id: `${identity.careerId}-event-001`, occurredAt: "15 AUG 1917", title: "Line Patrol", detail: "Completed · confirmed event" },
  ] : [
    { id: `${identity.careerId}-event-001`, occurredAt: "15 AUG 1917", title: "Line Patrol", detail: "Completed · Sopwith Camel" },
    { id: `${identity.careerId}-event-002`, occurredAt: "14 AUG 1917", title: "Balloon Defense", detail: "Victory confirmed · 00:48" },
    { id: `${identity.careerId}-event-003`, occurredAt: "13 AUG 1917", title: "Offensive Patrol", detail: "Aircraft damaged · Returned safely" },
  ];
  const victoryRows: readonly VictoryPreviewViewModel[] = emptyCollections || fixtureState === "unknown" ? [] : fixtureState === "partial" ? [
    { id: `${identity.careerId}-victory-001`, occurredAt: "14 AUG", targetLabel: "Observation balloon", statusLabel: "Confirmed" },
  ] : [
    { id: `${identity.careerId}-victory-001`, occurredAt: "14 AUG", targetLabel: "Observation balloon", statusLabel: "Confirmed" },
    { id: `${identity.careerId}-victory-002`, occurredAt: "09 AUG", targetLabel: "Albatros D.V", statusLabel: "Confirmed" },
    { id: `${identity.careerId}-victory-003`, occurredAt: "02 AUG", targetLabel: "Pfalz D.III", statusLabel: "Claim filed" },
  ];
  const fieldMap = { missions: fields.missions, flightMinutes: fields.flightMinutes, claimsCount: fields.claims, confirmedVictories: fields.victories, skill: fields.skill, reputation: fields.reputation };
  const unavailableFields = Object.entries(fieldMap).filter(([, field]) => field.state !== "known").map(([name]) => name);
  const dataState = fixtureState === "partial" ? "partial" : fixtureState === "unknown" ? "unknown" : fixtureState === "zeroes" ? "zeroes" : fixtureState === "empty" ? "empty" : "complete";
  const portrait = identity.careerId === "rfc-14a-08f2" ? known("/pilot-portrait.png") : unavailable<string>("portrait_not_supplied");
  const data: PilotDossierViewModel = {
    careerId: identity.careerId,
    careerReferenceLabel: known(identity.careerReferenceLabel),
    displayName: identity.displayName,
    rank: identity.rank ? known(identity.rank) : unknown<string>("rank_unknown"),
    serviceOrNationLabel: optionalIdentity(identity.serviceOrNationLabel, "Service unknown", "service_unknown"),
    squadronLabel: optionalIdentity(identity.squadronLabel, "Squadron unknown", "squadron_unknown"),
    careerStatus: presentPilotStatus(identity.careerStatus),
    aircraftLabel: optionalIdentity(identity.aircraftLabel, "Aircraft unknown", "aircraft_unknown"),
    stationLabel: identity.stationLabel ? known(identity.stationLabel) : unavailable<string>("station_not_supplied"),
    portraitAsset: portrait,
    dataState,
    missions: fields.missions,
    flightMinutes: fields.flightMinutes,
    claimsCount: fields.claims,
    confirmedVictories: fields.victories,
    skill: fields.skill,
    reputation: fields.reputation,
    recentServiceEvents: serviceEvents,
    recentVictories: victoryRows,
    recentDecorations: emptyCollections ? [] : ["Sanitized decoration fixture"],
    lastUpdatedLabel: observedAt ? known(observedAt) : unknown<string>("observed_at_unknown"),
    safeSourceSummary: "Sanitized presentation snapshot; no SQL, parser payload, cursor or local path.",
  };
  return deepFreeze({
    identityKey: identity.careerId,
    state,
    reason,
    meta: {
      contract: "PilotDossierSnapshot",
      version: "pilot-dossier.v1",
      authority: "Sanitized fixture query service",
      observedAt,
      freshness,
      warnings,
      unavailableFields,
      safeSourceSummary: data.safeSourceSummary,
    },
    data,
  });
}
