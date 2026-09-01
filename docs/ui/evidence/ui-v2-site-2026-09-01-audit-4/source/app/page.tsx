"use client";

import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type RefObject } from "react";
import { createPilotDossierSnapshot, deepFreeze, presentPilotStatus, type PilotDossierViewModel, type PresentationField, type PrototypeFixtureState, type SnapshotEnvelope } from "./view-models";

type RenderState = "complete" | "partial" | "zeroes" | "unavailable";
type FixtureState = PrototypeFixtureState;
type FixtureViewport = "desktop-100" | "desktop-125" | "desktop-150" | "desktop-200";
type Screen = "app-shell" | "career-selector" | "dashboard" | "pilot" | "career-record" | "victories-claims" | "decorations" | "missions" | "mission-report" | "diary" | "reports" | "report-viewer" | "squadron" | "aircrew-profile" | "system";
type MissionFilter = "all" | "completed" | "victory" | "damaged";
type SquadronFilter = "all" | "a-flight" | "b-flight" | "unavailable";
type DiaryFilter = "all" | "sortie" | "combat" | "squadron";
type ReportFilter = "all" | "career" | "missions" | "unit";
type SystemHealth = "healthy" | "attention" | "stale" | "unavailable";
type SystemFilter = "all" | SystemHealth;

type Career = {
  readonly id: string;
  readonly rank: string;
  readonly name: string;
  readonly squadron: string;
  readonly service: string;
  readonly aircraft: string;
  readonly station: string | null;
  readonly status: string | null;
  readonly reference: string;
  readonly slotLabel: string;
};

type Mission = {
  careerId: string;
  id: string;
  date: string;
  title: string;
  aircraft: string;
  result: string;
  duration: string;
  tone: "normal" | "good" | "danger";
  filter: Exclude<MissionFilter, "all">;
  squadron: string;
  aerodrome: string;
  area: string;
  objective: string;
  narrative: string;
  claims: number;
  victories: number;
  crew: string[];
  weather: string;
  formation: string;
};

type Aircrew = {
  id: string;
  rank: string;
  name: string;
  initials: string;
  role: string;
  flight: "Headquarters" | "A Flight" | "B Flight";
  aircraft: string;
  status: "In service" | "Wounded" | "On leave";
  tone: "good" | "danger" | "warning";
  missions: number;
  victories: number;
  claims: number;
  flightTime: string;
  joined: string;
  lastSortie: string;
  reference: string;
  serviceNote: string;
};

type DiaryEntry = {
  readonly id: string;
  readonly careerId: string;
  readonly missionId: string;
  readonly date: string;
  readonly time: string;
  readonly title: string;
  readonly category: Exclude<DiaryFilter, "all">;
  readonly categoryLabel: string;
  readonly location: string;
  readonly narrative: string;
  readonly provenance: string;
};

type ReportSection = {
  readonly title: string;
  readonly body: string;
  readonly rows: readonly {
    readonly label: string;
    readonly value: string;
    readonly detail: string;
  }[];
};

type ReportRecord = {
  readonly id: string;
  readonly careerId: string;
  readonly code: string;
  readonly title: string;
  readonly category: Exclude<ReportFilter, "all">;
  readonly categoryLabel: string;
  readonly description: string;
  readonly period: string;
  readonly observedAt: string;
  readonly coverage: string;
  readonly sheets: number;
  readonly contract: string;
  readonly sections: readonly ReportSection[];
};

type SystemCheck = {
  readonly id: string;
  readonly area: string;
  readonly title: string;
  readonly status: SystemHealth;
  readonly statusLabel: string;
  readonly summary: string;
  readonly observedAt: string;
  readonly authority: string;
  readonly reason: string;
};

const careers: readonly Career[] = deepFreeze([
  { id: "rfc-14a-08f2", rank: "Lt.", name: "Arthur Bennett", squadron: "14 Squadron", service: "RFC", aircraft: "Sopwith Camel F.1", station: "Bailleul Aerodrome", status: "Active", reference: "RFC-14A-08F2", slotLabel: "WoFF Pilot 1" },
  { id: "raf-41b-22c1", rank: "Lt.", name: "Arthur Bennett", squadron: "41 Squadron", service: "RAF", aircraft: "S.E.5a", station: "Bertangles Aerodrome", status: "Lightly Wounded", reference: "RAF-41B-22C1", slotLabel: "WoFF Pilot 2" },
  { id: "career-14b8", rank: "Lt.", name: "Ana Morel", squadron: "Squadron unknown", service: "Service unknown", aircraft: "Aircraft unknown", station: null, status: null, reference: "CAREER-14B8", slotLabel: "WoFF Pilot 3" },
]);

const navItems = ["Operations", "Pilot Dossier", "Missions", "Squadron", "War Diary", "Reports"];

type FixtureScenario = {
  readonly id: FixtureState;
  readonly label: string;
  readonly group: string;
  readonly badge: string;
  readonly meaning: string;
  readonly reason: string;
  readonly renderState: RenderState;
  readonly mode: "content" | "loading" | "source";
  readonly tone: "ready" | "waiting" | "attention" | "failure" | "neutral";
};

type FixtureSurface = {
  readonly screen: Screen;
  readonly id: string;
  readonly label: string;
};

type FixtureViewportProfile = {
  readonly id: FixtureViewport;
  readonly label: string;
  readonly shortLabel: string;
  readonly canvas: string;
  readonly width: number;
  readonly height: number;
};

const fixtureScenarios: readonly FixtureScenario[] = [
  { id: "complete", label: "Complete", group: "Ready", badge: "COMPLETE RECORD", meaning: "All authoritative regions supplied by the sanitized fixture are available.", reason: "fixture_complete", renderState: "complete", mode: "content", tone: "ready" },
  { id: "loading", label: "Loading", group: "Transition", badge: "LOADING FIXTURE", meaning: "The desktop shell and view geometry remain stable while no prior-career data is reused.", reason: "fixture_loading", renderState: "unavailable", mode: "loading", tone: "waiting" },
  { id: "empty", label: "Empty", group: "Valid empty", badge: "NONE RECORDED", meaning: "The collection was read successfully and contains no records.", reason: "collection_empty", renderState: "zeroes", mode: "content", tone: "neutral" },
  { id: "partial", label: "Partial", group: "Degraded", badge: "PARTIAL RECORD", meaning: "Confirmed identity remains visible; unavailable fields are identified individually.", reason: "source_partial", renderState: "partial", mode: "content", tone: "attention" },
  { id: "no-career", label: "No career", group: "Context", badge: "NO CAREER SELECTED", meaning: "The persistent desktop shell remains available without borrowing another career's data.", reason: "career_not_selected", renderState: "unavailable", mode: "source", tone: "neutral" },
  { id: "missing", label: "Missing", group: "Absent", badge: "RECORD MISSING", meaning: "The expected record was not supplied by the current source contract.", reason: "record_missing", renderState: "unavailable", mode: "source", tone: "attention" },
  { id: "truncated", label: "Truncated", group: "Degraded", badge: "TRUNCATED RECORD", meaning: "Only an incomplete record was observed; unvalidated values stay hidden.", reason: "record_truncated", renderState: "unavailable", mode: "source", tone: "attention" },
  { id: "unsupported", label: "Unsupported", group: "Format", badge: "UNSUPPORTED FORMAT", meaning: "The source format is not recognized by the approved presentation contract.", reason: "source_format_unsupported", renderState: "unavailable", mode: "source", tone: "attention" },
  { id: "unreadable", label: "Unreadable", group: "Failure", badge: "UNREADABLE SOURCE", meaning: "The record could not be read; raw payloads and local paths remain concealed.", reason: "source_unreadable", renderState: "unavailable", mode: "source", tone: "failure" },
  { id: "error", label: "Error", group: "Failure", badge: "QUERY ERROR", meaning: "A temporary query failure preserves the selected screen and career context.", reason: "query_error", renderState: "unavailable", mode: "source", tone: "failure" },
  { id: "stale", label: "Stale", group: "Freshness", badge: "STALE SNAPSHOT", meaning: "Safe snapshot observed 14 AUG 1917 · 23:41. This older snapshot is not current data.", reason: "snapshot_age_exceeded", renderState: "complete", mode: "content", tone: "attention" },
  { id: "zeroes", label: "Authoritative zeroes", group: "Valid value", badge: "AUTHORITATIVE ZEROES", meaning: "Every displayed zero is an explicit authoritative value, never a placeholder.", reason: "authoritative_zero", renderState: "zeroes", mode: "content", tone: "ready" },
  { id: "unknown", label: "Unknown values", group: "Field state", badge: "UNKNOWN VALUES", meaning: "The field exists conceptually, but its value is not known and is never coerced to zero.", reason: "field_value_unknown", renderState: "partial", mode: "content", tone: "neutral" },
  { id: "unavailable", label: "Not available", group: "Absent", badge: "SOURCE UNAVAILABLE", meaning: "The current source contract does not offer this view or field.", reason: "source_not_available", renderState: "unavailable", mode: "source", tone: "neutral" },
];

const fixtureSurfaces: readonly FixtureSurface[] = [
  { screen: "app-shell", id: "APP-00", label: "Application Shell" },
  { screen: "career-selector", id: "SEL-01", label: "Career Selector" },
  { screen: "dashboard", id: "OPR-01", label: "Operations Board" },
  { screen: "pilot", id: "DOS-01", label: "Pilot Dossier" },
  { screen: "career-record", id: "DOS-02", label: "Career Record" },
  { screen: "victories-claims", id: "DOS-03", label: "Victories & Claims" },
  { screen: "decorations", id: "DOS-04", label: "Decorations" },
  { screen: "missions", id: "MIS-01", label: "Mission Log" },
  { screen: "mission-report", id: "MIS-02", label: "Mission Report" },
  { screen: "squadron", id: "SQD-01", label: "Squadron Roster" },
  { screen: "aircrew-profile", id: "SQD-02", label: "Aircrew Profile" },
  { screen: "diary", id: "JRN-01", label: "War Diary" },
  { screen: "reports", id: "RPT-01", label: "Reports Library" },
  { screen: "report-viewer", id: "RPT-02", label: "Report Viewer" },
  { screen: "system", id: "SYS-01", label: "System Status" },
];

const fixtureViewports: readonly FixtureViewportProfile[] = [
  { id: "desktop-100", label: "Desktop 100%", shortLabel: "100%", canvas: "1440 × 1024 logical canvas", width: 1440, height: 1024 },
  { id: "desktop-125", label: "Desktop 125%", shortLabel: "125%", canvas: "1152 × 819 logical canvas", width: 1152, height: 819 },
  { id: "desktop-150", label: "Desktop 150%", shortLabel: "150%", canvas: "960 × 683 logical canvas", width: 960, height: 683 },
  { id: "desktop-200", label: "Desktop 200%", shortLabel: "200%", canvas: "720 × 512 logical canvas", width: 720, height: 512 },
];

const pilotStatusFixtures = [
  { id: "career", label: "From selected career", value: null },
  ...["Active", "KIA", "PoW", "MIA", "Invalided Out", "Survived War", "Lightly Wounded", "Seriously Wounded"].map(value => ({ id: value, label: value, value })),
  { id: "missing", label: "Missing status", value: null },
  { id: "blank", label: "Blank status", value: "" },
  { id: "unavailable", label: "Unavailable status", value: null },
  { id: "future", label: "Future authoritative status", value: "Transferred (future)" },
] as const;

function dossierIdentityFromCareer(career: Career) {
  return deepFreeze({
    careerId: career.id,
    careerReferenceLabel: `${career.slotLabel} · ${career.reference}`,
    displayName: career.name,
    rank: career.rank,
    serviceOrNationLabel: career.service,
    squadronLabel: career.squadron,
    careerStatus: career.status,
    aircraftLabel: career.aircraft,
    stationLabel: career.station,
  });
}

const missionRecords: Mission[] = [
  {
    careerId: "rfc-14a-08f2", id: "MIS-1917-08-15-027", date: "15 AUG 1917", title: "Line Patrol", aircraft: "Sopwith Camel F.1", result: "Completed", duration: "01:12", tone: "normal", filter: "completed", squadron: "14 Squadron RFC", aerodrome: "Bailleul", area: "Armentières sector", objective: "Patrol the assigned line and report enemy air activity.", narrative: "The flight crossed the lines at 0614 hrs and completed two circuits of the assigned sector. Enemy activity remained light. The formation returned together after scattered ground fire east of Armentières.", claims: 0, victories: 0, crew: ["Capt. Edward Collins · Flight Lead", "Lt. Arthur Bennett · No. 2", "Lt. René Fournier · No. 3"], weather: "Broken cloud · good visibility", formation: "Vee · three aircraft",
  },
  {
    careerId: "rfc-14a-08f2", id: "MIS-1917-08-14-026", date: "14 AUG 1917", title: "Balloon Defense", aircraft: "Sopwith Camel F.1", result: "Victory", duration: "00:48", tone: "good", filter: "victory", squadron: "14 Squadron RFC", aerodrome: "Bailleul", area: "Nieppe sector", objective: "Protect the observation balloon during the morning artillery programme.", narrative: "Two hostile scouts approached from the east shortly after 0740 hrs. The patrol intercepted before they reached the balloon. One enemy aircraft was observed descending out of control; confirmation was entered after the flight returned.", claims: 1, victories: 1, crew: ["Lt. Arthur Bennett · Flight Lead", "Lt. René Fournier · Wingman"], weather: "Clear below 8,000 ft", formation: "Line abreast · two aircraft",
  },
  {
    careerId: "rfc-14a-08f2", id: "MIS-1917-08-13-025", date: "13 AUG 1917", title: "Offensive Patrol", aircraft: "Sopwith Camel F.1", result: "Damaged", duration: "01:26", tone: "danger", filter: "damaged", squadron: "14 Squadron RFC", aerodrome: "Bailleul", area: "Lille approaches", objective: "Sweep the northern approach and challenge hostile reconnaissance flights.", narrative: "The patrol met a mixed enemy formation west of Lille. Bennett's aircraft sustained damage to the upper plane during the engagement. The pilot disengaged and returned to Bailleul without further loss.", claims: 1, victories: 0, crew: ["Capt. Edward Collins · Flight Lead", "Lt. Arthur Bennett · No. 2", "2Lt. James Clarke · No. 3"], weather: "High haze · moderate wind", formation: "Vee · three aircraft",
  },
  {
    careerId: "rfc-14a-08f2", id: "MIS-1917-08-08-024", date: "08 AUG 1917", title: "Escort Duty", aircraft: "Sopwith Camel F.1", result: "Completed", duration: "01:34", tone: "normal", filter: "completed", squadron: "14 Squadron RFC", aerodrome: "Bailleul", area: "Ypres salient", objective: "Escort a photographic reconnaissance flight across the assigned route.", narrative: "The reconnaissance aircraft completed its photographic run. No hostile aircraft closed within engagement distance and all machines returned to their home stations.", claims: 0, victories: 0, crew: ["Capt. Edward Collins · Flight Lead", "Lt. Arthur Bennett · Escort", "Lt. René Fournier · Escort"], weather: "Cloud at 6,500 ft", formation: "Close escort · three aircraft",
  },
  {
    careerId: "rfc-14a-08f2", id: "MIS-1917-08-04-023", date: "04 AUG 1917", title: "Airfield Defense", aircraft: "Sopwith Camel F.1", result: "Completed", duration: "00:39", tone: "normal", filter: "completed", squadron: "14 Squadron RFC", aerodrome: "Bailleul", area: "Bailleul perimeter", objective: "Maintain readiness and intercept aircraft approaching the station.", narrative: "The alarm was raised after unidentified aircraft were reported south of the field. The contact turned west before interception and the patrol landed without incident.", claims: 0, victories: 0, crew: ["Lt. Arthur Bennett · Patrol Lead", "2Lt. James Clarke · Wingman"], weather: "Overcast · light rain", formation: "Pair",
  },
  {
    careerId: "raf-41b-22c1", id: "MIS-1918-06-04-012", date: "04 JUN 1918", title: "High Patrol", aircraft: "S.E.5a", result: "Completed", duration: "01:05", tone: "normal", filter: "completed", squadron: "41 Squadron RAF", aerodrome: "Bertangles", area: "Albert sector", objective: "Patrol the assigned altitude above the Albert sector.", narrative: "The flight completed the assigned patrol and returned to Bertangles without an engagement. This is a separate synthetic fixture for the selected RAF career.", claims: 0, victories: 0, crew: ["Lt. Arthur Bennett · No. 2", "Capt. Thomas Grey · Flight Lead"], weather: "Scattered cloud · clear horizon", formation: "Line astern · two aircraft",
  },
  {
    careerId: "raf-41b-22c1", id: "MIS-1918-06-02-011", date: "02 JUN 1918", title: "Offensive Sweep", aircraft: "S.E.5a", result: "Victory", duration: "00:57", tone: "good", filter: "victory", squadron: "41 Squadron RAF", aerodrome: "Bertangles", area: "Bray approaches", objective: "Sweep the eastern approaches and challenge hostile scouts.", narrative: "The patrol engaged hostile scouts east of Bray. One claim was confirmed in the sanitized RAF fixture after the flight returned.", claims: 1, victories: 1, crew: ["Capt. Thomas Grey · Flight Lead", "Lt. Arthur Bennett · No. 2"], weather: "Fine · light westerly wind", formation: "Vee · two aircraft",
  },
];

const diaryRecords: readonly DiaryEntry[] = [
  {
    id: "JRN-RFC14A-19170815-027",
    careerId: "rfc-14a-08f2",
    missionId: "MIS-1917-08-15-027",
    date: "15 AUG 1917",
    time: "0835 HRS",
    title: "Two quiet circuits over the line",
    category: "sortie",
    categoryLabel: "Sortie record",
    location: "Bailleul",
    narrative: "We crossed the lines shortly after six and made two circuits of the Armentières sector. The formation held together through scattered ground fire and returned without loss.",
    provenance: "Mission summary · diary contract v1",
  },
  {
    id: "JRN-RFC14A-19170814-026",
    careerId: "rfc-14a-08f2",
    missionId: "MIS-1917-08-14-026",
    date: "14 AUG 1917",
    time: "0910 HRS",
    title: "The balloon remained aloft",
    category: "combat",
    categoryLabel: "Combat entry",
    location: "Nieppe sector",
    narrative: "Two hostile scouts came in from the east during the morning programme. We met them before they reached the balloon; one was later entered as confirmed after the flight returned.",
    provenance: "Confirmed mission narrative · diary contract v1",
  },
  {
    id: "JRN-RFC14A-19170813-025",
    careerId: "rfc-14a-08f2",
    missionId: "MIS-1917-08-13-025",
    date: "13 AUG 1917",
    time: "1745 HRS",
    title: "Home with a wounded machine",
    category: "combat",
    categoryLabel: "Combat entry",
    location: "Lille approaches",
    narrative: "A mixed enemy formation found us west of Lille. The upper plane took damage in the engagement, so I broke away and brought the Camel back to Bailleul.",
    provenance: "Mission summary · diary contract v1",
  },
  {
    id: "JRN-RFC14A-19170808-024",
    careerId: "rfc-14a-08f2",
    missionId: "MIS-1917-08-08-024",
    date: "08 AUG 1917",
    time: "1215 HRS",
    title: "Photographic flight returned intact",
    category: "squadron",
    categoryLabel: "Squadron record",
    location: "Ypres salient",
    narrative: "The reconnaissance machine completed its photographic run while we held close escort. No hostile aircraft came within engagement distance and every machine returned.",
    provenance: "Squadron mission record · diary contract v1",
  },
  {
    id: "JRN-RFC14A-19170804-023",
    careerId: "rfc-14a-08f2",
    missionId: "MIS-1917-08-04-023",
    date: "04 AUG 1917",
    time: "1640 HRS",
    title: "Alarm over the aerodrome",
    category: "sortie",
    categoryLabel: "Sortie record",
    location: "Bailleul perimeter",
    narrative: "The alarm sounded after aircraft were reported south of the field. The contact turned west before we could intercept, and the patrol landed again without incident.",
    provenance: "Mission summary · diary contract v1",
  },
];

const reportRecords: readonly ReportRecord[] = [
  {
    id: "RPT-RFC14A-19170815-CAREER",
    careerId: "rfc-14a-08f2",
    code: "CR-08/17",
    title: "Career summary",
    category: "career",
    categoryLabel: "Career record",
    description: "Confirmed service totals and the current recorded position of the selected pilot career.",
    period: "22 JUN — 15 AUG 1917",
    observedAt: "15 AUG 1917 · 23:41",
    coverage: "Complete snapshot",
    sheets: 2,
    contract: "Career report v1",
    sections: [
      {
        title: "Recorded career position",
        body: "This field copy presents authoritative values supplied by the career snapshot. No totals are recalculated by the viewer.",
        rows: [
          { label: "Operational sorties", value: "27", detail: "Recorded career total" },
          { label: "Flight time", value: "46 h 18 min", detail: "Authoritative duration" },
          { label: "Confirmed victories", value: "8", detail: "Confirmed record" },
          { label: "Claims filed", value: "11", detail: "Filed record" },
        ],
      },
      {
        title: "Service assignment",
        body: "The assignment below reflects only the observed record and does not predict promotion, transfer, recovery or the next sortie.",
        rows: [
          { label: "Unit", value: "14 Squadron RFC", detail: "Selected career scope" },
          { label: "Aircraft", value: "Sopwith Camel F.1", detail: "Recorded type" },
          { label: "Station", value: "Bailleul Aerodrome", detail: "Observed assignment" },
          { label: "Status", value: "In service", detail: "Recorded state" },
        ],
      },
    ],
  },
  {
    id: "RPT-RFC14A-19170815-SORTIES",
    careerId: "rfc-14a-08f2",
    code: "SD-08/17",
    title: "Sortie digest",
    category: "missions",
    categoryLabel: "Mission record",
    description: "A chronological digest of the readable mission reports associated with this career snapshot.",
    period: "04 — 15 AUG 1917",
    observedAt: "15 AUG 1917 · 23:41",
    coverage: "5 readable reports",
    sheets: 3,
    contract: "Mission digest v1",
    sections: [
      {
        title: "Operational digest",
        body: "Five sanitized mission reports are present in this field copy. Each entry retains its stable mission identity.",
        rows: [
          { label: "Latest sortie", value: "Line Patrol", detail: "MIS-1917-08-15-027" },
          { label: "Confirmed victory", value: "Balloon Defense", detail: "MIS-1917-08-14-026" },
          { label: "Aircraft damaged", value: "Offensive Patrol", detail: "MIS-1917-08-13-025" },
          { label: "Readable reports", value: "5", detail: "Fixture snapshot" },
        ],
      },
      {
        title: "Recent operational sequence",
        body: "The sequence is ordered from the latest readable report. Outcomes are presented as recorded, without reinterpretation.",
        rows: [
          { label: "15 AUG", value: "Completed", detail: "Line Patrol · 01:12" },
          { label: "14 AUG", value: "Victory", detail: "Balloon Defense · 00:48" },
          { label: "13 AUG", value: "Damaged", detail: "Offensive Patrol · 01:26" },
          { label: "08 AUG", value: "Completed", detail: "Escort Duty · 01:34" },
        ],
      },
    ],
  },
  {
    id: "RPT-RFC14A-19170815-CLAIMS",
    careerId: "rfc-14a-08f2",
    code: "CL-08/17",
    title: "Claims register",
    category: "career",
    categoryLabel: "Combat record",
    description: "Filed claims and confirmed victories kept distinct under the selected career identity.",
    period: "Career to 15 AUG 1917",
    observedAt: "15 AUG 1917 · 23:41",
    coverage: "Complete snapshot",
    sheets: 2,
    contract: "Claims register v1",
    sections: [
      {
        title: "Combat totals",
        body: "Claims and confirmed victories remain separate record classes. The viewer does not promote a claim to a victory.",
        rows: [
          { label: "Claims filed", value: "11", detail: "Career total" },
          { label: "Victories confirmed", value: "8", detail: "Career total" },
          { label: "Latest confirmation", value: "14 AUG 1917", detail: "Balloon Defense" },
          { label: "Latest mission claim", value: "1", detail: "MIS-1917-08-14-026" },
        ],
      },
      {
        title: "Record distinction",
        body: "This report preserves the authority of the supplied combat record and exposes no witness payload or adjudication detail.",
        rows: [
          { label: "Confirmation state", value: "Recorded", detail: "No UI inference" },
          { label: "Presentation", value: "Sanitized", detail: "Private detail omitted" },
          { label: "Career reference", value: "RFC-14A-08F2", detail: "Stable identity" },
        ],
      },
    ],
  },
  {
    id: "RPT-RFC14A-19170815-UNIT",
    careerId: "rfc-14a-08f2",
    code: "UB-14/17",
    title: "Squadron operations brief",
    category: "unit",
    categoryLabel: "Unit record",
    description: "Recorded strength, availability and assignment context for the pilot's current squadron.",
    period: "Observed 15 AUG 1917",
    observedAt: "15 AUG 1917 · 23:41",
    coverage: "11 roster entries",
    sheets: 2,
    contract: "Unit brief v1",
    sections: [
      {
        title: "Recorded unit strength",
        body: "The following values reflect the roster snapshot associated with the selected career and observation time.",
        rows: [
          { label: "Roster entries", value: "11", detail: "Current snapshot" },
          { label: "In service", value: "8", detail: "Recorded availability" },
          { label: "Wounded", value: "2", detail: "Recorded state" },
          { label: "On leave", value: "1", detail: "Recorded state" },
        ],
      },
      {
        title: "Command context",
        body: "Personnel states are presented without predicted recovery, return, reassignment or next operational duty.",
        rows: [
          { label: "Commanding officer", value: "Maj. William Harcourt", detail: "Headquarters" },
          { label: "Primary aircraft", value: "Sopwith Camel F.1", detail: "Recorded type" },
          { label: "Station", value: "Bailleul Aerodrome", detail: "Current snapshot" },
          { label: "Service", value: "Royal Flying Corps", detail: "Unit record" },
        ],
      },
    ],
  },
];

const systemChecks: readonly SystemCheck[] = [
  {
    id: "SYS-CONFIG-01",
    area: "Configuration",
    title: "Configuration contract",
    status: "healthy",
    statusLabel: "Healthy",
    summary: "The sanitized configuration snapshot matches the expected contract revision.",
    observedAt: "15 AUG 1917 · 23:41",
    authority: "Configuration contract v1",
    reason: "validated",
  },
  {
    id: "SYS-DATABASE-01",
    area: "Database",
    title: "Read-only database snapshot",
    status: "healthy",
    statusLabel: "Healthy",
    summary: "The demonstration snapshot is readable and its stable identity is retained.",
    observedAt: "15 AUG 1917 · 23:41",
    authority: "Database health summary v1",
    reason: "snapshot_readable",
  },
  {
    id: "SYS-DOSSIER-01",
    area: "Source",
    title: "Pilot dossier source",
    status: "attention",
    statusLabel: "Attention",
    summary: "Required identity fields are readable, while optional service fields remain unavailable.",
    observedAt: "15 AUG 1917 · 23:36",
    authority: "Pilot dossier snapshot v1",
    reason: "field_coverage_incomplete",
  },
  {
    id: "SYS-MISSIONS-01",
    area: "Source",
    title: "Mission source freshness",
    status: "stale",
    statusLabel: "Stale",
    summary: "The last readable mission snapshot is retained but is explicitly marked as not current.",
    observedAt: "15 AUG 1917 · 22:58",
    authority: "Mission snapshot v1",
    reason: "snapshot_age_exceeded",
  },
  {
    id: "SYS-DIARY-01",
    area: "Source",
    title: "War diary authority",
    status: "attention",
    statusLabel: "Attention",
    summary: "Two sanitized authorities disagree on one optional narrative field; no winner is inferred.",
    observedAt: "15 AUG 1917 · 23:34",
    authority: "Diary authority comparison v1",
    reason: "authority_conflict",
  },
  {
    id: "SYS-PROCESSING-01",
    area: "Processing",
    title: "Processing snapshot",
    status: "unavailable",
    statusLabel: "Unavailable",
    summary: "No current processing snapshot is available, so activity and completion are not inferred.",
    observedAt: "Observation unavailable",
    authority: "Processing status contract v1",
    reason: "processing_snapshot_missing",
  },
];

const aircrewRecords: Aircrew[] = [
  { id: "AC-14-HQ-001", rank: "Maj.", name: "William Harcourt", initials: "WH", role: "Commanding Officer", flight: "Headquarters", aircraft: "Sopwith Camel F.1", status: "In service", tone: "good", missions: 63, victories: 9, claims: 13, flightTime: "112 h 44 min", joined: "03 MAY 1917", lastSortie: "12 AUG 1917", reference: "RFC-14-HQ-001", serviceNote: "Squadron command and operational planning." },
  { id: "AC-14-A-002", rank: "Capt.", name: "Edward Collins", initials: "EC", role: "Flight Commander", flight: "A Flight", aircraft: "Sopwith Camel F.1", status: "In service", tone: "good", missions: 54, victories: 12, claims: 16, flightTime: "97 h 18 min", joined: "18 MAY 1917", lastSortie: "15 AUG 1917", reference: "RFC-14-A-002", serviceNote: "Commands A Flight and leads offensive patrols." },
  { id: "AC-14-A-003", rank: "Lt.", name: "Arthur Bennett", initials: "AB", role: "Pilot", flight: "A Flight", aircraft: "Sopwith Camel F.1", status: "In service", tone: "good", missions: 27, victories: 8, claims: 11, flightTime: "46 h 18 min", joined: "22 JUN 1917", lastSortie: "15 AUG 1917", reference: "RFC-14A-08F2", serviceNote: "Active campaign pilot; current career selected in the global context." },
  { id: "AC-14-A-004", rank: "Lt.", name: "René Fournier", initials: "RF", role: "Wingman", flight: "A Flight", aircraft: "Sopwith Camel F.1", status: "In service", tone: "good", missions: 31, victories: 4, claims: 7, flightTime: "51 h 06 min", joined: "27 JUN 1917", lastSortie: "15 AUG 1917", reference: "RFC-14-A-004", serviceNote: "Regular wingman on line patrol and balloon defense sorties." },
  { id: "AC-14-A-005", rank: "2Lt.", name: "James Clarke", initials: "JC", role: "Pilot", flight: "A Flight", aircraft: "Sopwith Camel F.1", status: "Wounded", tone: "danger", missions: 18, victories: 2, claims: 3, flightTime: "29 h 41 min", joined: "02 JUL 1917", lastSortie: "13 AUG 1917", reference: "RFC-14-A-005", serviceNote: "Listed as wounded; no recovery date is inferred by this view." },
  { id: "AC-14-A-006", rank: "Lt.", name: "Harold Mitchell", initials: "HM", role: "Pilot", flight: "A Flight", aircraft: "Sopwith Camel F.1", status: "In service", tone: "good", missions: 22, victories: 3, claims: 5, flightTime: "38 h 12 min", joined: "09 JUL 1917", lastSortie: "14 AUG 1917", reference: "RFC-14-A-006", serviceNote: "Assigned to patrol and escort duties." },
  { id: "AC-14-B-007", rank: "Capt.", name: "Charles Mercer", initials: "CM", role: "Flight Commander", flight: "B Flight", aircraft: "Sopwith Camel F.1", status: "In service", tone: "good", missions: 49, victories: 7, claims: 10, flightTime: "88 h 09 min", joined: "12 MAY 1917", lastSortie: "15 AUG 1917", reference: "RFC-14-B-007", serviceNote: "Commands B Flight and defensive patrol assignments." },
  { id: "AC-14-B-008", rank: "Lt.", name: "Thomas Reed", initials: "TR", role: "Pilot", flight: "B Flight", aircraft: "Sopwith Camel F.1", status: "In service", tone: "good", missions: 25, victories: 5, claims: 6, flightTime: "43 h 27 min", joined: "21 JUN 1917", lastSortie: "15 AUG 1917", reference: "RFC-14-B-008", serviceNote: "Assigned to airfield defense and escort duties." },
  { id: "AC-14-B-009", rank: "2Lt.", name: "Albert Walker", initials: "AW", role: "Pilot", flight: "B Flight", aircraft: "Sopwith Camel F.1", status: "In service", tone: "good", missions: 14, victories: 1, claims: 2, flightTime: "22 h 53 min", joined: "17 JUL 1917", lastSortie: "12 AUG 1917", reference: "RFC-14-B-009", serviceNote: "Recently assigned pilot; confirmed records only." },
  { id: "AC-14-B-010", rank: "Lt.", name: "George Hale", initials: "GH", role: "Pilot", flight: "B Flight", aircraft: "Sopwith Camel F.1", status: "Wounded", tone: "danger", missions: 33, victories: 6, claims: 8, flightTime: "58 h 31 min", joined: "29 MAY 1917", lastSortie: "10 AUG 1917", reference: "RFC-14-B-010", serviceNote: "Listed as wounded; medical details are not available to this view." },
  { id: "AC-14-B-011", rank: "2Lt.", name: "Peter Lang", initials: "PL", role: "Pilot", flight: "B Flight", aircraft: "Sopwith Camel F.1", status: "On leave", tone: "warning", missions: 19, victories: 2, claims: 4, flightTime: "31 h 22 min", joined: "04 JUL 1917", lastSortie: "08 AUG 1917", reference: "RFC-14-B-011", serviceNote: "Current roster state is on leave; return date not recorded." },
];

const squadron = [aircrewRecords[1], aircrewRecords[3], aircrewRecords[4]].map((member) => ({ id: member.id, rank: member.rank, name: member.name, role: member.role, state: member.status, tone: member.tone }));

function StatusMark({ tone, label }: { tone: "normal" | "good" | "danger" | "warning"; label: string }) {
  const mark = tone === "danger" ? "!" : tone === "warning" ? "◷" : "✓";
  return <><span className="status-mark" aria-hidden="true">{mark}</span>{label}</>;
}

function PilotStatus({ value }: { value: string | null }) {
  const field = presentPilotStatus(value);
  const tone = field.state !== "known" || field.reason ? "warning" : value === "Active" || value === "Survived War" ? "good" : "danger";
  return <span className="pilot-status" data-status-input={value ?? ""}>
    <em data-tone={tone} role="status" aria-label={field.display}><StatusMark tone={tone} label={field.display} /></em>
    {field.reason === "pilot_status_mapping_unsupported" && <small className="status-mapping-notice">Unsupported status mapping · authoritative value retained</small>}
  </span>;
}

function ApplicationShellReference({ career }: { career: Career }) {
  const regions = [
    ["Navigation rail", "Six approved read-only destinations in fixed order."],
    ["Career context", `${career.rank} ${career.name} · ${career.slotLabel} · ${career.reference}`],
    ["Page header", "One destination heading and honest coverage summary."],
    ["Content region", "One career-scoped view; no previous-career content."],
    ["System footer", "Data & System Status remains separate and globally available."],
  ];
  return (
    <div className="shell-reference-grid">
      <section className="paper-card shell-reference-file" aria-labelledby="shell-reference-title">
        <p className="panel-label">APP-00 · Persistent desktop shell</p>
        <h2 id="shell-reference-title">Application shell anatomy</h2>
        <p>The shell preserves orientation while stable career identity, presentation state and destination change independently.</p>
        <div className="field-stamp">READ ONLY · DESKTOP</div>
      </section>
      <section className="dark-panel riveted shell-region-list" aria-labelledby="shell-regions-title">
        <div className="panel-heading"><div><h2 id="shell-regions-title">Persistent regions</h2><p>Normative visual coverage</p></div><span>5 regions</span></div>
        <div>{regions.map(([label, detail], index) => <article key={label}><i>{String(index + 1).padStart(2, "0")}</i><span><strong>{label}</strong><small>{detail}</small></span></article>)}</div>
      </section>
      <aside className="squadron-panel riveted shell-contract" aria-labelledby="shell-contract-title">
        <div className="panel-heading"><div><h2 id="shell-contract-title">Identity boundary</h2><p>Source slot is not career identity</p></div></div>
        <p><strong>{career.slotLabel}</strong> is a persistent simulator slot label. <strong>{career.reference}</strong> identifies this sanitized fixture career.</p>
        <div className="provenance-note"><strong>Slot contract</strong><span>Pilot numbers are never renumbered when an earlier campaign is deleted.</span><small>Slots remain persistent and may be sparse.</small></div>
      </aside>
    </div>
  );
}

function CareerSelectorReference({ activeCareer, onSelect }: { activeCareer: Career; onSelect: (career: Career) => void }) {
  const sparseCareers = careers.filter((career) => career.slotLabel !== "WoFF Pilot 1");
  return (
    <section className="selector-reference riveted" aria-labelledby="selector-reference-title">
      <header><div><p className="panel-label">SEL-01 · Sparse source-slot regression</p><h2 id="selector-reference-title">Choose a pilot career</h2><p>Same-name careers stay distinct. This deterministic fixture has no Pilot1 campaign; Pilot2 and Pilot3 retain their source-slot labels.</p></div><span>READ ONLY<br />SYNTHETIC</span></header>
      <div className="sparse-slot-notice" id="sparse-slot-description"><strong>Pilot1 vacant</strong><span>Observed source slots: Pilot2 and Pilot3. The selected value remains career_id, never list position.</span></div>
      <div className="selector-reference-options" data-fixture="sparse-slots-2-3" role="listbox" aria-label="Sparse career selector fixture" aria-describedby="sparse-slot-description">{sparseCareers.map((career) => <button key={career.id} role="option" aria-selected={career.id === activeCareer.id} onClick={() => onSelect(career)}><span><small>{career.slotLabel}</small><strong>{career.rank} {career.name}</strong><em>{career.squadron} · {career.service} · {presentPilotStatus(career.status).display}</em></span><code>{career.reference}</code></button>)}</div>
      <footer><strong>Persistent-slot rule</strong><span>Deleting Pilot1 never renumbers Pilot2 or Pilot3. A later Pilot1 is a new career_id.</span></footer>
    </section>
  );
}

function Header({ career, state, fixtureBadge, hasCareerContext = true, screen, viewReference, careerOpen, careerButtonRef, headingRef, onCareerClick }: { career: Career; state: RenderState; fixtureBadge?: string; hasCareerContext?: boolean; screen: Screen; viewReference?: string; careerOpen: boolean; careerButtonRef: RefObject<HTMLButtonElement | null>; headingRef: RefObject<HTMLHeadingElement | null>; onCareerClick: () => void }) {
  const view = screen === "dashboard"
    ? { title: "Operations Board", subtitle: "Campaign overview", badge: `${career.slotLabel} · ${career.reference}` }
    : screen === "app-shell"
      ? { title: "Application Shell", subtitle: "Persistent desktop frame", badge: "APP-00 · SHELL REFERENCE" }
      : screen === "career-selector"
        ? { title: "Career Selector", subtitle: "Stable identity selection", badge: "SEL-01 · CAREER_ID" }
    : screen === "pilot"
      ? { title: "Pilot Dossier", subtitle: "Career record", badge: `CAREER · ${career.reference}` }
      : screen === "career-record"
        ? { title: "Career Record", subtitle: "Confirmed service events", badge: "DOS-02 · READ ONLY" }
        : screen === "victories-claims"
          ? { title: "Victories & Claims", subtitle: "Combat record", badge: "DOS-03 · READ ONLY" }
          : screen === "decorations"
            ? { title: "Decorations", subtitle: "Confirmed awards", badge: "DOS-04 · READ ONLY" }
      : screen === "missions"
        ? { title: "Mission Log", subtitle: "Chronological sorties", badge: `MIS-01 · ${career.slotLabel}` }
        : screen === "mission-report"
          ? { title: "Mission Report", subtitle: "Selected sortie record", badge: viewReference ?? "MIS-02 · FIELD COPY" }
          : screen === "squadron"
            ? { title: "Squadron Roster", subtitle: "Aircrew and flight status", badge: `SQD-01 · ${career.squadron} ${career.service === "Service unknown" ? "" : career.service}` }
            : screen === "diary"
              ? { title: "War Diary", subtitle: "Campaign chronicle", badge: viewReference ?? "JRN-01 · CAMPAIGN RECORD" }
              : screen === "reports"
                ? { title: "Reports Library", subtitle: "Produced career reports", badge: viewReference ?? "RPT-01 · REPORT INDEX" }
                : screen === "report-viewer"
                  ? { title: "Report Viewer", subtitle: "Selected field report", badge: viewReference ?? "RPT-02 · FIELD COPY" }
                  : screen === "system"
                    ? { title: "System Status", subtitle: "Configuration · Database · Sources · Processing", badge: viewReference ?? "SYS-01 · MIXED HEALTH" }
                    : { title: "Aircrew Profile", subtitle: "Selected personnel record", badge: viewReference ?? "SQD-02 · FIELD COPY" };
  const contextPath = screen === "career-record" || screen === "victories-claims" || screen === "decorations" ? "Pilot Dossier / Record" : screen === "diary" ? "Operations / War Diary" : screen === "reports" ? "Operations / Reports" : screen === "report-viewer" ? "Reports / Viewer" : screen === "system" ? "System / Data & status" : null;
  const badge = fixtureBadge ?? (state === "complete" ? view.badge : state === "partial" ? "PARTIAL RECORD · 15 AUG 1917" : state === "zeroes" ? "AUTHORITATIVE ZEROES" : "SOURCE UNAVAILABLE");
  return (
    <header className="board-header">
      <div className="title-block">
        {contextPath && <small className="context-path">{contextPath}</small>}
        <h1 ref={headingRef} id="screen-title" tabIndex={-1}>{view.title}</h1>
        <p>{view.subtitle}{screen !== "system" && hasCareerContext && <> <span>·</span> {career.squadron} {career.service === "Service unknown" ? "" : career.service}</>}</p>
      </div>
      <div className="campaign-badge">{badge}</div>
      <div className="header-facts">
        <button ref={careerButtonRef} className="pilot-fact" onClick={onCareerClick} aria-label={hasCareerContext ? "Change active career" : "Select active career"} aria-expanded={careerOpen} aria-controls="career-selector" aria-haspopup="listbox">
          <small>Active pilot</small>
          <strong>{hasCareerContext ? `${career.rank} ${career.name}` : "No career selected"}</strong>
        </button>
        <div><small>Last sync</small><strong>{fixtureBadge === "STALE SNAPSHOT" ? "14 AUG 1917 · 23:41 (stale)" : state === "unavailable" ? "—" : "23:41"}</strong></div>
        <div><small>Monitoring</small><strong className={state === "unavailable" ? "monitor warning" : "monitor"}><StatusMark tone={state === "unavailable" ? "warning" : "good"} label={state === "unavailable" ? "Attention" : "Active"} /></strong></div>
      </div>
    </header>
  );
}

function CareerRecord({ career, state }: { career: Career; state: RenderState }) {
  const completeByCareer: Readonly<Record<string, readonly string[]>> = {
    "rfc-14a-08f2": ["27", "46.3 h", "8", "11"],
    "raf-41b-22c1": ["12", "21.1 h", "3", "5"],
    "career-14b8": ["4", "5.6 h", "0", "0"],
  };
  const completeValues = completeByCareer[career.id] ?? ["—", "—", "—", "—"];
  const values = state === "zeroes" ? ["0", "0.0 h", "0", "0"] : state === "partial" ? [completeValues[0], "—", completeValues[2], "—"] : completeValues;
  const labels = ["Missions", "Flight Time", "Victories", "Claims"];
  return (
    <section className="paper-card career-record" aria-labelledby="career-record-title">
      <p className="panel-label" id="career-record-title">Career record</p>
      <div className="record-grid">
        {values.map((value, index) => <div key={labels[index]}><strong>{value}</strong><span>{labels[index]}</span>{value === "—" && <small>Unknown</small>}</div>)}
      </div>
    </section>
  );
}

function Condition({ career, state }: { career: Career; state: RenderState }) {
  const completeByCareer: Readonly<Record<string, readonly [number | null, number | null, number | null]>> = {
    "rfc-14a-08f2": [42, 76, 31],
    "raf-41b-22c1": [58, 62, 45],
    "career-14b8": [null, null, null],
  };
  const complete = completeByCareer[career.id] ?? [null, null, null];
  const values = state === "zeroes" ? [0, 0, 0] : state === "partial" ? [complete[0], complete[1], null] : complete;
  const rows = [["Fatigue", values[0], "amber"], ["Morale", values[1], "green"], ["Stress", values[2], "red"]] as const;
  return (
    <section className="dark-panel riveted condition" aria-labelledby="condition-title">
      <p className="panel-label" id="condition-title">Pilot condition</p>
      <div className="gauges">
        {rows.map(([label, value, tone]) => <div className="gauge" key={label}><div><span>{label}</span><strong>{value === null ? "Unknown" : `${value} / 100`}</strong></div><div className="track"><i className={tone} style={{ width: value === null ? "0%" : `${value}%` }} /></div></div>)}
      </div>
    </section>
  );
}

function Operations({ career, state, onOpenMission, onOpenAircrew }: { career: Career; state: RenderState; onOpenMission: (mission: Mission) => void; onOpenAircrew: (member: Aircrew) => void }) {
  if (state === "unavailable") {
    return <section className="source-state riveted"><p className="panel-label">Data status</p><h2>Campaign source unavailable</h2><p>The active career remains selected, but operational data could not be read. No paths, raw records or inferred values are displayed.</p><div><span>Career retained</span><strong>{career.rank} {career.name} · {career.reference}</strong></div></section>;
  }
  const careerMissions = missionRecords.filter((mission) => mission.careerId === career.id);
  const sorties = careerMissions.slice(0, 3).map((mission) => ({ id: mission.id, date: mission.date, mission: mission.title, aircraft: mission.aircraft.replace(" F.1", ""), result: mission.result, duration: mission.duration, tone: mission.tone }));
  const visibleSorties = state === "zeroes" ? [] : state === "partial" ? sorties.slice(0, 1) : sorties;
  const rosterAvailable = career.id === "rfc-14a-08f2";
  const visibleRoster = !rosterAvailable || state === "zeroes" ? [] : state === "partial" ? squadron.slice(0, 2) : squadron;
  return (
    <div className="operations-grid">
      <section className="paper-card active-pilot" aria-labelledby="active-pilot-title">
        <p className="panel-label" id="active-pilot-title">Active pilot</p>
        <div className="pilot-card-body">
          <div className="service-block" aria-label={`${career.service} service marker`}>{career.service === "Service unknown" ? "—" : career.service}</div>
          <div className="pilot-copy"><h2>{career.rank} {career.name}</h2><strong>{career.squadron} {career.service === "Service unknown" ? "" : career.service}</strong><span>{career.aircraft}</span><small>{career.station ?? "Station not available"} · {career.slotLabel}</small><PilotStatus value={career.status} /></div>
        </div>
        <div className="field-stamp">{career.service === "Service unknown" ? "CAREER RECORD · FIELD COPY" : `${career.service} · FORM 14A · FIELD COPY`}</div>
      </section>

      <CareerRecord career={career} state={state} />
      <Condition career={career} state={state} />

      <section className="dark-panel riveted sorties" aria-labelledby="sorties-title">
        <div className="panel-heading"><div><h2 id="sorties-title">Recent sorties</h2><p>Operational record</p></div><span>Mission board</span></div>
        {visibleSorties.length ? <div className="table-wrap"><table><thead><tr><th>Date</th><th>Mission</th><th>Aircraft</th><th>Result</th><th>Duration</th></tr></thead><tbody>{visibleSorties.map((sortie) => <tr key={`${sortie.date}-${sortie.mission}`}><td>{sortie.date}</td><td><button className="mission-inline-link" onClick={() => { const mission = missionRecords.find((record) => record.id === sortie.id); if (mission) onOpenMission(mission); }}>{sortie.mission}</button></td><td>{sortie.aircraft}</td><td className={sortie.tone}><StatusMark tone={sortie.tone} label={sortie.result} /></td><td>{sortie.duration}</td></tr>)}</tbody></table></div> : <div className="legitimate-empty"><strong>No recorded sorties</strong><span>The collection was read successfully and is validly empty.</span></div>}
      </section>

      <section className="squadron-panel riveted" aria-labelledby="squadron-title">
        <div className="panel-heading"><div><h2 id="squadron-title">{career.squadron}</h2><p>Flight status</p></div></div>
        {visibleRoster.length ? <div className="roster">{visibleRoster.map((member) => <div key={member.name}><button className="roster-profile-link" onClick={() => { const record = aircrewRecords.find((entry) => entry.id === member.id); if (record) onOpenAircrew(record); }}><strong>{member.rank} {member.name}</strong></button><span>{member.role} <em className={member.tone}><StatusMark tone={member.tone} label={member.state} /></em></span></div>)}</div> : <div className="legitimate-empty compact"><strong>{rosterAvailable ? "No roster entries recorded" : "Roster snapshot not supplied"}</strong><span>{rosterAvailable ? "0 active aircrew is authoritative." : "No personnel from another career is substituted."}</span></div>}
        <p className="roster-summary">{!rosterAvailable ? `${career.reference} · selected career only` : state === "zeroes" ? "0 pilots active · 0 wounded · 0 unavailable" : state === "partial" ? "Roster partial · 2 confirmed entries" : "8 pilots active · 2 wounded · 1 unavailable"}</p>
      </section>
    </div>
  );
}

function PilotDossier({ snapshot, onOpenContext }: { snapshot: SnapshotEnvelope<PilotDossierViewModel>; onOpenContext: (screen: "career-record" | "victories-claims" | "decorations") => void }) {
  if (!snapshot.data) {
    return <section className="source-state riveted"><p className="panel-label">DOS-01 · {snapshot.state}</p><h2>Pilot dossier {snapshot.state}</h2><p>The immutable snapshot contains no presentation data for this state. Career context is retained only when its stable identity is available.</p><div><span>Stable reason</span><code>{snapshot.reason ?? "snapshot_not_ready"}</code></div></section>;
  }

  const dossier = snapshot.data;
  const stats: Array<[string, PresentationField<number>, string]> = [
    ["Missions", dossier.missions, "Operational sorties"],
    ["Flight time", dossier.flightMinutes, "Recorded minutes"],
    ["Victories", dossier.confirmedVictories, "Confirmed"],
    ["Claims", dossier.claimsCount, "Filed"],
    ["Skill", dossier.skill, "Recorded rating"],
    ["Reputation", dossier.reputation, "Recorded rating"],
  ];
  const stateNote = (field: PresentationField<number>, knownNote: string) => field.state === "known" ? knownNote : `${field.state} · ${field.reason}`;
  const dataTone = (field: PresentationField<number>) => field.state === "known" && field.value === 0 ? "zero" : field.state;
  const partial = dossier.dataState === "partial" || dossier.dataState === "unknown";
  const initials = dossier.displayName.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="dossier-grid">
      <section className="paper-card dossier-identity" aria-labelledby="dossier-identity-title">
        <p className="panel-label" id="dossier-identity-title">DOS-01 · Career identity · immutable snapshot</p>
        <div className="dossier-identity-body">
          <div className="portrait-frame">{dossier.portraitAsset.state === "known" && dossier.portraitAsset.value ? <img src={dossier.portraitAsset.value} alt="Sanitized demonstration portrait of the selected pilot" /> : <div className="dossier-portrait-fallback" aria-label="Neutral portrait fallback"><strong>{initials}</strong><small>Portrait not supplied</small></div>}</div>
          <div className="identity-copy">
            <span className="service-kicker">{dossier.serviceOrNationLabel.state === "known" ? `${dossier.serviceOrNationLabel.display} personnel file` : "Service not recorded"}</span>
            <h2>{dossier.rank.state === "known" ? `${dossier.rank.display} ` : ""}{dossier.displayName}</h2>
            <p>{dossier.squadronLabel.display}{dossier.serviceOrNationLabel.state === "known" ? ` · ${dossier.serviceOrNationLabel.display}` : ""}</p>
            <dl>
              <div><dt>Aircraft</dt><dd>{dossier.aircraftLabel.display}</dd></div>
              <div><dt>Station</dt><dd>{dossier.stationLabel.display}</dd></div>
              <div><dt>Status</dt><dd><PilotStatus value={dossier.careerStatus.value} /></dd></div>
            </dl>
          </div>
        </div>
        <div className="field-stamp dossier-stamp">CAREER_ID · {dossier.careerId} · READ ONLY</div>
      </section>

      <section className="paper-card dossier-stat-file" aria-labelledby="dossier-stats-title">
        <p className="panel-label" id="dossier-stats-title">Career totals · explicit field states</p>
        <div className="dossier-stats">
          {stats.map(([label, field, note]) => <div key={label} data-state={dataTone(field)}><span>{label}</span><strong>{field.display}</strong><small>{stateNote(field, note)}</small></div>)}
        </div>
        <div className="dossier-context-links" aria-label="Pilot Dossier records">
          <button onClick={() => onOpenContext("career-record")}>Open Career Record <span aria-hidden="true">→</span></button>
          <button onClick={() => onOpenContext("victories-claims")}>Open Victories &amp; Claims <span aria-hidden="true">→</span></button>
          <button onClick={() => onOpenContext("decorations")}>Open Decorations <span aria-hidden="true">→</span></button>
        </div>
      </section>

      <section className="dark-panel riveted service-ledger" aria-labelledby="service-ledger-title">
        <div className="panel-heading"><div><h2 id="service-ledger-title">Service ledger</h2><p>Chronological career record</p></div><span>{partial ? "Field states mixed" : snapshot.state === "empty" ? "Valid empty set" : "Snapshot copy"}</span></div>
        {dossier.recentServiceEvents.length ? <div className="ledger-list">{dossier.recentServiceEvents.map((event, index) => <div key={event.id}><time>{event.occurredAt}</time><i>{String(index + 1).padStart(2, "0")}</i><span><strong>{event.title}</strong><small>{event.detail}</small></span></div>)}</div> : <div className="legitimate-empty"><strong>No missions recorded</strong><span>The collection was read successfully and is validly empty; no record is inferred.</span></div>}
      </section>

      <section className="squadron-panel riveted dossier-side" aria-labelledby="victories-title">
        <div className="panel-heading"><div><h2 id="victories-title">Victories &amp; claims</h2><p>Combat record</p></div></div>
        {dossier.recentVictories.length ? <div className="victory-list">{dossier.recentVictories.map((victory) => <div key={victory.id}><time>{victory.occurredAt}</time><span><strong>{victory.targetLabel}</strong><small>{victory.statusLabel}</small></span></div>)}</div> : dossier.dataState === "unknown" ? <div className="collection-unavailable"><strong>Victories unknown</strong><span>The source did not supply this collection; no empty set or zero is inferred.</span></div> : <div className="legitimate-empty compact"><strong>No victories recorded</strong><span>{dossier.confirmedVictories.state === "known" && dossier.confirmedVictories.value === 0 ? "0 is an authoritative total." : "The collection was read successfully and is validly empty."}</span></div>}
        <div className="provenance-note"><strong>Snapshot provenance</strong><span>{snapshot.meta.authority} · {snapshot.meta.version}</span><small>{snapshot.meta.freshness} · {snapshot.meta.observedAt ?? "Observation time unknown"}</small><code>{snapshot.meta.unavailableFields.length ? snapshot.meta.unavailableFields.join(" · ") : "all_fields_available"}</code></div>
      </section>
    </div>
  );
}

function DossierContextView({ screen, snapshot, onBack }: { screen: "career-record" | "victories-claims" | "decorations"; snapshot: SnapshotEnvelope<PilotDossierViewModel>; onBack: () => void }) {
  const id = screen === "career-record" ? "DOS-02" : screen === "victories-claims" ? "DOS-03" : "DOS-04";
  const title = screen === "career-record" ? "Career Record" : screen === "victories-claims" ? "Victories & Claims" : "Decorations";
  const dossier = snapshot.data;
  if (!dossier) {
    return <div className="dossier-context-flow"><button className="back-to-log" onClick={onBack}>← Return to Pilot Dossier</button><section className="source-state riveted"><p className="panel-label">{id} · Data status</p><h2>{title} unavailable</h2><p>No previous-career record is reused while this snapshot is unavailable.</p></section></div>;
  }

  return (
    <div className="dossier-context-flow">
      <button className="back-to-log" onClick={onBack}>← Return to Pilot Dossier</button>
      <div className="dossier-context-grid">
        <section className="paper-card dossier-context-file" aria-labelledby={`${id}-title`}>
          <p className="panel-label">{id} · Read-only contextual record</p>
          <h2 id={`${id}-title`}>{title}</h2>
          <p>{dossier.rank.display} {dossier.displayName} · {dossier.careerReferenceLabel.display}</p>
          <div className="field-stamp">{id} · CAREER_ID · {dossier.careerId}</div>
        </section>

        {screen === "career-record" ? (
          <section className="dark-panel riveted dossier-context-ledger" aria-labelledby="career-history-title">
            <div className="panel-heading"><div><h2 id="career-history-title">Confirmed service events</h2><p>Chronological career record</p></div><span>{dossier.recentServiceEvents.length} recorded</span></div>
            {dossier.recentServiceEvents.length ? <div className="ledger-list">{dossier.recentServiceEvents.map((event, index) => <div key={event.id}><time>{event.occurredAt}</time><i>{String(index + 1).padStart(2, "0")}</i><span><strong>{event.title}</strong><small>{event.detail}</small></span></div>)}</div> : <div className="legitimate-empty"><strong>No career events recorded</strong><span>The collection is validly empty.</span></div>}
          </section>
        ) : screen === "victories-claims" ? (
          <section className="dark-panel riveted dossier-context-ledger" aria-labelledby="claims-ledger-title">
            <div className="panel-heading"><div><h2 id="claims-ledger-title">Claims ledger</h2><p>Claims remain distinct from confirmed victories</p></div><span>READ ONLY</span></div>
            <div className="context-stat-row"><div><span>Claims filed</span><strong>{dossier.claimsCount.display}</strong><small>{dossier.claimsCount.state}</small></div><div><span>Confirmed victories</span><strong>{dossier.confirmedVictories.display}</strong><small>{dossier.confirmedVictories.state}</small></div></div>
            {dossier.recentVictories.length ? <div className="victory-list">{dossier.recentVictories.map((victory) => <div key={victory.id}><time>{victory.occurredAt}</time><span><strong>{victory.targetLabel}</strong><small>{victory.statusLabel}</small></span></div>)}</div> : <div className="legitimate-empty"><strong>No victories recorded</strong><span>No claim is promoted to confirmed status.</span></div>}
          </section>
        ) : (
          <section className="dark-panel riveted dossier-context-ledger" aria-labelledby="decorations-ledger-title">
            <div className="panel-heading"><div><h2 id="decorations-ledger-title">Confirmed decorations</h2><p>No medal or citation is inferred</p></div><span>READ ONLY</span></div>
            {dossier.recentDecorations.length ? <div className="decoration-list">{dossier.recentDecorations.map((decoration) => <div key={decoration}><strong>{decoration}</strong><span>Synthetic demonstration record · citation not supplied</span></div>)}</div> : <div className="legitimate-empty"><strong>No decorations recorded</strong><span>The collection is validly empty; no award is inferred.</span></div>}
          </section>
        )}

        <aside className="squadron-panel riveted dossier-context-meta" aria-labelledby="dossier-context-meta-title">
          <div className="panel-heading"><div><h2 id="dossier-context-meta-title">Record scope</h2><p>Stable career isolation</p></div></div>
          <dl><div><dt>Career ID</dt><dd>{dossier.careerId}</dd></div><div><dt>Current source slot</dt><dd>{dossier.careerReferenceLabel.display.split(" · ")[0]}</dd></div><div><dt>Coverage</dt><dd>{dossier.dataState}</dd></div><div><dt>Authority</dt><dd>{snapshot.meta.authority}</dd></div></dl>
          <div className="provenance-note"><strong>Identity rule</strong><span>The slot label locates the current WoFF source; career_id remains the immutable identity.</span><small>Slots remain persistent and may be sparse.</small></div>
        </aside>
      </div>
    </div>
  );
}

function MissionLog({ career, state, onSelect }: { career: Career; state: RenderState; onSelect: (mission: Mission) => void }) {
  const [filter, setFilter] = useState<MissionFilter>("all");
  if (state === "unavailable") {
    return <section className="source-state riveted"><p className="panel-label">MIS-01 · Data status</p><h2>Mission log unavailable</h2><p>The selected career remains visible, but its mission collection could not be read. No previous career data or inferred sorties are substituted.</p><div><span>Career retained</span><strong>{career.rank} {career.name} · {career.reference}</strong></div></section>;
  }

  const careerRecords = missionRecords.filter((mission) => mission.careerId === career.id);
  const sourceRecords = state === "zeroes" ? [] : state === "partial" ? careerRecords.slice(0, 2) : careerRecords;
  const visibleRecords = filter === "all" ? sourceRecords : sourceRecords.filter((mission) => mission.filter === filter);
  const careerTotals: Readonly<Record<string, readonly [string, string, string]>> = {
    "rfc-14a-08f2": ["27", "8", "46 h 18 min"],
    "raf-41b-22c1": ["12", "3", "21 h 08 min"],
    "career-14b8": ["4", "0", "5 h 37 min"],
  };
  const [missionTotal, victoryTotal, flightTimeTotal] = careerTotals[career.id] ?? ["—", "—", "—"];
  const totals = state === "zeroes"
    ? [["Career missions", "0", "Authoritative"], ["Displayed", "0", "None recorded"], ["Victories", "0", "Confirmed"], ["Flight time", "0 h 00 min", "Recorded"]]
    : state === "partial"
      ? [["Career missions", missionTotal, "Known total"], ["Displayed", String(sourceRecords.length), "Readable entries"], ["Victories", "—", "Unknown"], ["Flight time", "—", "Unknown"]]
      : [["Career missions", missionTotal, "Operational sorties"], ["Displayed", String(sourceRecords.length), "Recent records"], ["Victories", victoryTotal, "Confirmed"], ["Flight time", flightTimeTotal, "Recorded"]];
  const filterLabels: Array<[MissionFilter, string]> = [["all", "All sorties"], ["completed", "Completed"], ["victory", "Victories"], ["damaged", "Damaged"]];

  return (
    <div className="mission-log-grid">
      <section className="paper-card mission-register" aria-labelledby="mission-register-title">
        <div className="mission-register-heading"><div><p className="panel-label">MIS-01 · Sortie index</p><h2 id="mission-register-title">Operational mission register</h2><span>{state === "partial" ? "Partial record · confirmed entries only" : `Field copy · ${career.slotLabel} · chronological order`}</span></div><div className="register-stamp">{career.squadron.replace("Squadron", "SQN").toUpperCase()} · {career.service === "Service unknown" ? "SERVICE UNKNOWN" : career.service}<br />{sourceRecords[0]?.date.slice(-4) ?? "PERIOD UNKNOWN"}</div></div>
        <div className="mission-totals">{totals.map(([label, value, note]) => <div key={label} data-state={value === "—" ? "unknown" : value === "0" || value === "0 h 00 min" ? "zero" : "known"}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>)}</div>
      </section>

      <section className="dark-panel riveted mission-list" aria-labelledby="mission-list-title">
        <div className="panel-heading mission-list-heading"><div><h2 id="mission-list-title">Mission log</h2><p>Select a sortie to open its read-only field report</p></div><span>{visibleRecords.length} shown</span></div>
        <div className="mission-filters" aria-label="Filter mission log">{filterLabels.map(([value, label]) => <button key={value} className={filter === value ? "active" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
        {visibleRecords.length ? <div className="mission-rows"><div className="mission-row mission-row-head" aria-hidden="true"><span>Date</span><span>Sortie</span><span>Aircraft</span><span>Result</span><span>Duration</span><span /></div>{visibleRecords.map((mission) => <button className="mission-row" key={mission.id} onClick={() => onSelect(mission)} aria-label={`Open report for ${mission.title}, ${mission.date}`}><time>{mission.date}</time><span><strong>{mission.title}</strong><small>{mission.area}</small></span><span>{mission.aircraft.replace(" F.1", "")}</span><em className={mission.tone}><StatusMark tone={mission.tone} label={mission.result} /></em><span>{mission.duration}</span><b aria-hidden="true">›</b></button>)}</div> : <div className="legitimate-empty mission-empty"><strong>{sourceRecords.length ? "No sorties match this filter" : "No missions recorded"}</strong><span>{sourceRecords.length ? "Choose another operational category." : "The collection was read successfully and is validly empty."}</span></div>}
      </section>

      <aside className="squadron-panel riveted mission-context" aria-labelledby="mission-context-title">
        <div className="panel-heading"><div><h2 id="mission-context-title">Campaign context</h2><p>Active career scope</p></div></div>
        <dl><div><dt>Pilot</dt><dd>{career.rank} {career.name}</dd></div><div><dt>Unit</dt><dd>{career.squadron} {career.service === "Service unknown" ? "" : career.service}</dd></div><div><dt>Station</dt><dd>{state === "partial" ? "Unknown" : career.station ?? "Not available"}</dd></div><div><dt>Source slot</dt><dd>{career.slotLabel}</dd></div></dl>
        <div className="mission-key"><strong>Record key</strong><span><i className="good" aria-hidden="true" /> Victory confirmed</span><span><i className="danger" aria-hidden="true" /> Aircraft damaged</span><span><i aria-hidden="true" /> Completed sortie</span></div>
        <div className="provenance-note"><strong>Source provenance</strong><span>{state === "partial" ? "Readable mission entries only" : "Sanitized fixture · chronological records"}</span><small>No mission is recalculated by this view</small></div>
      </aside>
    </div>
  );
}

function MissionReport({ mission, state, onBack }: { mission: Mission; state: RenderState; onBack: () => void }) {
  if (state === "unavailable" || state === "zeroes") {
    return <div className="mission-report-flow"><button className="back-to-log" onClick={onBack}>← Return to Mission Log</button><section className="source-state riveted"><p className="panel-label">MIS-02 · Data status</p><h2>{state === "zeroes" ? "No mission report recorded" : "Mission report unavailable"}</h2><p>{state === "zeroes" ? "The mission collection is validly empty, so there is no report to display." : "The selected report could not be read. No cached narrative or inferred outcome is shown."}</p></section></div>;
  }

  const partial = state === "partial";
  return (
    <div className="mission-report-flow">
      <button className="back-to-log" onClick={onBack}>← Return to Mission Log</button>
      <div className="mission-report-grid">
        <section className="paper-card mission-order" aria-labelledby="mission-order-title">
          <p className="panel-label">MIS-02 · Mission report</p>
          <div className="mission-order-heading"><div><span>{mission.date}</span><h2 id="mission-order-title">{mission.title}</h2><p>{mission.id}</p></div><em className={mission.tone}><StatusMark tone={mission.tone} label={mission.result} /></em></div>
          <dl className="mission-order-meta"><div><dt>Aircraft</dt><dd>{mission.aircraft}</dd></div><div><dt>Squadron</dt><dd>{mission.squadron}</dd></div><div><dt>Aerodrome</dt><dd>{partial ? "— · Unknown" : mission.aerodrome}</dd></div><div><dt>Operational area</dt><dd>{partial ? "— · Unknown" : mission.area}</dd></div><div><dt>Duration</dt><dd>{mission.duration}</dd></div><div><dt>Formation</dt><dd>{partial ? "— · Unknown" : mission.formation}</dd></div></dl>
          <div className="field-stamp mission-report-stamp">OPERATIONS COPY · READ ONLY</div>
        </section>

        <section className="dark-panel riveted mission-narrative" aria-labelledby="mission-narrative-title">
          <div className="panel-heading"><div><h2 id="mission-narrative-title">Combat report</h2><p>Recorded narrative</p></div><span>{partial ? "Partial entry" : "Filed"}</span></div>
          <div className="objective"><strong>Orders</strong><p>{mission.objective}</p></div>
          <blockquote>{partial ? "A readable report summary was not provided for this entry. The known mission metadata remains available above." : mission.narrative}</blockquote>
          <div className="weather-line"><span>Weather</span><strong>{partial ? "— · Unknown" : mission.weather}</strong></div>
        </section>

        <section className="squadron-panel riveted mission-outcome" aria-labelledby="mission-outcome-title">
          <div className="panel-heading"><div><h2 id="mission-outcome-title">Recorded outcome</h2><p>No derived combat totals</p></div></div>
          <div className="outcome-stats"><div><span>Claims</span><strong>{partial ? "—" : mission.claims}</strong><small>{partial ? "Unknown" : "Filed with report"}</small></div><div><span>Confirmed victories</span><strong>{partial ? "—" : mission.victories}</strong><small>{partial ? "Unknown" : "Authoritative"}</small></div><div><span>Aircraft state</span><strong className={mission.tone}><StatusMark tone={mission.tone} label={mission.result === "Damaged" ? "Damaged" : "Returned"} /></strong><small>Recorded result</small></div></div>
        </section>

        <section className="paper-card crew-manifest" aria-labelledby="crew-manifest-title">
          <div className="panel-heading paper-heading"><div><h2 id="crew-manifest-title">Flight manifest</h2><p>Confirmed personnel on report</p></div><span>{partial ? "Incomplete" : `${mission.crew.length} aircrew`}</span></div>
          {partial ? <div className="legitimate-empty compact paper-empty"><strong>Manifest not available</strong><span>The current source does not provide the crew list.</span></div> : <div className="crew-list">{mission.crew.map((member, index) => <div key={member}><i>{String(index + 1).padStart(2, "0")}</i><strong>{member}</strong><span>Recorded</span></div>)}</div>}
        </section>

        <section className="dark-panel riveted report-provenance" aria-labelledby="report-provenance-title">
          <div className="panel-heading"><div><h2 id="report-provenance-title">Report provenance</h2><p>Safe presentation contract</p></div></div>
          <dl><div><dt>Coverage</dt><dd>{partial ? "Partial record" : "Complete record"}</dd></div><div><dt>Identity</dt><dd>{mission.id}</dd></div><div><dt>Presentation</dt><dd>Sanitized fixture</dd></div></dl>
          <p>No game paths, raw payloads, witness details or recalculated outcomes are exposed.</p>
        </section>
      </div>
    </div>
  );
}

function WarDiary({ career, state, onOpenMission }: { career: Career; state: RenderState; onOpenMission: (mission: Mission) => void }) {
  const [filter, setFilter] = useState<DiaryFilter>("all");
  if (state === "unavailable") {
    return <section className="source-state riveted"><p className="panel-label">JRN-01 · Data status</p><h2>War diary unavailable</h2><p>The active career remains selected, but its narrative collection could not be read. No cached entry, previous-career diary or inferred text is substituted.</p><div><span>Career retained</span><strong>{career.rank} {career.name} · {career.reference}</strong></div></section>;
  }

  const careerEntries = diaryRecords.filter((entry) => entry.careerId === career.id);
  const sourceEntries = state === "zeroes" ? [] : state === "partial" ? careerEntries.slice(0, 2) : careerEntries;
  const visibleEntries = filter === "all" ? sourceEntries : sourceEntries.filter((entry) => entry.category === filter);
  const linkedMissionCount = sourceEntries.filter((entry) => missionRecords.some((mission) => mission.id === entry.missionId)).length;
  const filterLabels: Array<[DiaryFilter, string]> = [["all", "All entries"], ["sortie", "Sorties"], ["combat", "Combat"], ["squadron", "Squadron"]];
  const period = sourceEntries.length ? `${sourceEntries.at(-1)?.date} — ${sourceEntries[0].date}` : "No recorded period";
  const coverage = state === "partial" ? `${sourceEntries.length} / ${careerEntries.length || "—"}` : "Complete";

  return (
    <div className="diary-grid">
      <section className="paper-card diary-register" aria-labelledby="diary-register-title">
        <div className="diary-register-heading">
          <div><p className="panel-label">JRN-01 · Campaign chronicle</p><h2 id="diary-register-title">War diary of {career.rank} {career.name}</h2><span>Ordered narrative summaries · active career {career.reference}</span></div>
          <div className="diary-stamp">READ ONLY<br />FIELD COPY</div>
        </div>
        <div className="diary-totals">
          <div data-state={sourceEntries.length ? "known" : "zero"}><span>Diary entries</span><strong>{sourceEntries.length}</strong><small>{sourceEntries.length ? "In selected view" : "Authoritative"}</small></div>
          <div data-state={linkedMissionCount ? "known" : "zero"}><span>Linked missions</span><strong>{linkedMissionCount}</strong><small>Stable mission IDs</small></div>
          <div data-state={state === "partial" ? "unknown" : "known"}><span>Coverage</span><strong>{coverage}</strong><small>{state === "partial" ? "Readable entries" : "Source snapshot"}</small></div>
          <div data-state={sourceEntries.length ? "known" : "zero"}><span>Recorded period</span><strong>{period}</strong><small>Chronological scope</small></div>
        </div>
      </section>

      <section className="dark-panel riveted diary-ledger" aria-labelledby="diary-ledger-title">
        <div className="panel-heading"><div><h2 id="diary-ledger-title">Narrative timeline</h2><p>Immutable entries associated with the selected career</p></div><span>{visibleEntries.length} shown</span></div>
        <div className="diary-filters" aria-label="Filter war diary">{filterLabels.map(([value, label]) => <button key={value} className={filter === value ? "active" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
        {state === "partial" && <div className="diary-warning"><strong>Partial diary snapshot</strong><span>Only readable entries are shown. Missing narrative is not reconstructed.</span></div>}
        {visibleEntries.length ? <ol className="diary-timeline">{visibleEntries.map((entry, index) => {
          const mission = missionRecords.find((record) => record.id === entry.missionId);
          const narrativeUnavailable = state === "partial" && index === visibleEntries.length - 1;
          return <li key={entry.id}>
            <div className="diary-date"><time>{entry.date}</time><span>{entry.time}</span></div>
            <i className={`diary-marker ${entry.category}`} aria-hidden="true" />
            <article className="paper-card diary-entry-card" aria-labelledby={`${entry.id}-title`}>
              <div className="diary-entry-meta"><span className={entry.category}>{entry.categoryLabel}</span><code>{entry.id}</code></div>
              <h3 id={`${entry.id}-title`}>{entry.title}</h3>
              <p>{narrativeUnavailable ? "The entry identity and timestamp are readable, but its narrative body is unavailable in this snapshot." : entry.narrative}</p>
              <dl><div><dt>Location</dt><dd>{narrativeUnavailable ? "Unknown" : entry.location}</dd></div><div><dt>Mission ID</dt><dd>{entry.missionId}</dd></div><div><dt>Provenance</dt><dd>{narrativeUnavailable ? "Partial entry · reason recorded" : entry.provenance}</dd></div></dl>
              {mission && <button className="diary-mission-link" onClick={() => onOpenMission(mission)}>Open linked mission report <span aria-hidden="true">→</span></button>}
            </article>
          </li>;
        })}</ol> : <div className="legitimate-empty diary-empty"><strong>{sourceEntries.length ? "No diary entries match this filter" : "War diary is empty"}</strong><span>{sourceEntries.length ? "Choose another narrative category." : "The collection was read successfully and contains 0 entries for this career."}</span></div>}
      </section>

      <aside className="squadron-panel riveted diary-context" aria-labelledby="diary-context-title">
        <div className="panel-heading"><div><h2 id="diary-context-title">Record context</h2><p>Authority and freshness</p></div></div>
        <dl><div><dt>Career identity</dt><dd>{career.reference}</dd></div><div><dt>Source authority</dt><dd>Sanitized diary summary</dd></div><div><dt>Contract</dt><dd>Diary snapshot v1</dd></div><div><dt>Observed</dt><dd>{state === "partial" ? "Observation time unknown" : "15 AUG 1917 · 23:41"}</dd></div><div><dt>Freshness</dt><dd>{state === "partial" ? "Coverage incomplete" : "Current fixture snapshot"}</dd></div></dl>
        <div className="diary-key"><strong>Entry key</strong><span><i className="sortie" /> Sortie record</span><span><i className="combat" /> Combat entry</span><span><i className="squadron" /> Squadron record</span></div>
        <div className="provenance-note"><strong>Read-only contract</strong><span>No create, edit, delete, save or regeneration commands are exposed.</span><small>No game paths, SQL, raw payloads or previous-career entries are displayed.</small></div>
      </aside>
    </div>
  );
}

function ReportsLibrary({ career, state, onSelect }: { career: Career; state: RenderState; onSelect: (report: ReportRecord) => void }) {
  const [filter, setFilter] = useState<ReportFilter>("all");
  if (state === "unavailable") {
    return <section className="source-state riveted"><p className="panel-label">RPT-01 · Data status</p><h2>Reports library unavailable</h2><p>The active career remains selected, but its produced-report index could not be read. No cached document, previous-career report or inferred summary is substituted.</p><div><span>Career retained</span><strong>{career.rank} {career.name} · {career.reference}</strong></div></section>;
  }

  const careerReports = reportRecords.filter((report) => report.careerId === career.id);
  const sourceReports = state === "zeroes" ? [] : state === "partial" ? careerReports.slice(0, 2) : careerReports;
  const visibleReports = filter === "all" ? sourceReports : sourceReports.filter((report) => report.category === filter);
  const sheetCount = sourceReports.reduce((total, report) => total + report.sheets, 0);
  const filterLabels: Array<[ReportFilter, string]> = [["all", "All reports"], ["career", "Career"], ["missions", "Missions"], ["unit", "Unit"]];

  return (
    <div className="reports-grid">
      <section className="paper-card reports-register" aria-labelledby="reports-register-title">
        <div className="reports-register-heading">
          <div><p className="panel-label">RPT-01 · Produced reports</p><h2 id="reports-register-title">Field report library</h2><span>{career.rank} {career.name} · career {career.reference}</span></div>
          <div className="reports-stamp">INDEX COPY<br />READ ONLY</div>
        </div>
        <div className="reports-totals">
          <div data-state={sourceReports.length ? "known" : "zero"}><span>Available reports</span><strong>{sourceReports.length}</strong><small>{sourceReports.length ? "Readable documents" : "Authoritative"}</small></div>
          <div data-state={sheetCount ? "known" : "zero"}><span>Document sheets</span><strong>{sheetCount}</strong><small>Indexed field copies</small></div>
          <div data-state={state === "partial" ? "unknown" : "known"}><span>Library coverage</span><strong>{state === "partial" ? `${sourceReports.length} / ${careerReports.length || "—"}` : "Complete"}</strong><small>{state === "partial" ? "Readable reports" : "Source snapshot"}</small></div>
          <div data-state={sourceReports.length ? "known" : "zero"}><span>Observed</span><strong>{sourceReports.length ? "15 AUG 1917 · 23:41" : "No report date"}</strong><small>Snapshot freshness</small></div>
        </div>
      </section>

      <section className="dark-panel riveted reports-library" aria-labelledby="reports-library-title">
        <div className="panel-heading"><div><h2 id="reports-library-title">Report index</h2><p>Select a produced document to open its read-only field copy</p></div><span>{visibleReports.length} shown</span></div>
        <div className="reports-filters" aria-label="Filter reports library">{filterLabels.map(([value, label]) => <button key={value} className={filter === value ? "active" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
        {state === "partial" && <div className="reports-warning"><strong>Partial report index</strong><span>Only readable documents are listed. Missing reports are not reconstructed.</span></div>}
        {visibleReports.length ? <div className="report-cards">{visibleReports.map((report) => <article className="paper-card report-card" key={report.id}>
          <div className="report-card-top"><span className={`report-category ${report.category}`}>{report.categoryLabel}</span><span className="report-status"><i aria-hidden="true" />{state === "partial" ? "Readable" : "Ready"}</span></div>
          <div className="report-code" aria-hidden="true">{report.code}</div>
          <h3>{report.title}</h3>
          <p>{report.description}</p>
          <dl><div><dt>Period</dt><dd>{report.period}</dd></div><div><dt>Coverage</dt><dd>{state === "partial" ? "Partial index" : report.coverage}</dd></div><div><dt>Identity</dt><dd>{report.id}</dd></div></dl>
          <button className="open-report" onClick={() => onSelect(report)}>Open field report <span aria-hidden="true">→</span></button>
        </article>)}</div> : <div className="legitimate-empty reports-empty"><strong>{sourceReports.length ? "No reports match this filter" : "Reports library is empty"}</strong><span>{sourceReports.length ? "Choose another report category." : "The index was read successfully and contains 0 reports for this career."}</span></div>}
      </section>

      <aside className="squadron-panel riveted reports-context" aria-labelledby="reports-context-title">
        <div className="panel-heading"><div><h2 id="reports-context-title">Library context</h2><p>Scope and presentation</p></div></div>
        <dl><div><dt>Career identity</dt><dd>{career.reference}</dd></div><div><dt>Authority</dt><dd>Produced report index</dd></div><div><dt>Presentation</dt><dd>Sanitized fixtures</dd></div><div><dt>Freshness</dt><dd>{state === "partial" ? "Coverage incomplete" : "Current fixture snapshot"}</dd></div></dl>
        <div className="reports-key"><strong>Document key</strong><span><i className="career" /> Career record</span><span><i className="missions" /> Mission record</span><span><i className="unit" /> Unit record</span><span><b aria-hidden="true">✓</b> Ready or readable</span></div>
        <div className="provenance-note"><strong>Read-only library</strong><span>Reports can be opened for inspection only.</span><small>No generation, export, import, editing, deletion or repair action is available.</small></div>
      </aside>
    </div>
  );
}

function ReportViewer({ report, career, state, onBack }: { report: ReportRecord; career: Career; state: RenderState; onBack: () => void }) {
  if (report.careerId !== career.id) {
    return <div className="report-viewer-flow"><button className="back-to-log" onClick={onBack}>← Return to Reports Library</button><section className="source-state riveted"><p className="panel-label">RPT-02 · Career scope</p><h2>Report not available for this career</h2><p>The selected document belongs to a different career identity and will not be reused. Return to the library to inspect reports associated with {career.reference}.</p></section></div>;
  }
  if (state === "unavailable" || state === "zeroes") {
    return <div className="report-viewer-flow"><button className="back-to-log" onClick={onBack}>← Return to Reports Library</button><section className="source-state riveted"><p className="panel-label">RPT-02 · Data status</p><h2>{state === "zeroes" ? "No report recorded" : "Report unavailable"}</h2><p>{state === "zeroes" ? "The report index is validly empty, so there is no document to display." : "The selected field report could not be read. No cached document body or inferred section is shown."}</p></section></div>;
  }

  const partial = state === "partial";
  return (
    <div className="report-viewer-flow">
      <button className="back-to-log" onClick={onBack}>← Return to Reports Library</button>
      <div className="report-viewer-grid">
        <article className="paper-card report-document" aria-labelledby="report-document-title">
          <header className="report-document-header"><div><p className="panel-label">RPT-02 · Report viewer</p><span>{report.categoryLabel} · {report.code}</span><h2 id="report-document-title">{report.title}</h2><p>{report.description}</p></div><div className="report-document-stamp">FIELD COPY<br />READ ONLY</div></header>
          <dl className="report-document-meta"><div><dt>Report identity</dt><dd>{report.id}</dd></div><div><dt>Career</dt><dd>{career.reference}</dd></div><div><dt>Period</dt><dd>{report.period}</dd></div><div><dt>Coverage</dt><dd>{partial ? "Partial document" : report.coverage}</dd></div></dl>
          {partial && <div className="report-partial-banner"><strong>Partial report snapshot</strong><span>Unavailable sections remain identified and are not reconstructed.</span></div>}
          <div className="report-sections">{report.sections.map((section, index) => {
            const sectionUnavailable = partial && index > 0;
            return <section key={section.title} aria-labelledby={`${report.id}-section-${index}`}>
              <header><span>Section {String(index + 1).padStart(2, "0")}</span><h3 id={`${report.id}-section-${index}`}>{section.title}</h3></header>
              {sectionUnavailable ? <div className="report-section-unavailable"><strong>Section unavailable</strong><p>This section is identified by the report contract, but its body is not readable in the current snapshot.</p></div> : <><p>{section.body}</p><div className="report-data-rows">{section.rows.map((row) => <div key={`${section.title}-${row.label}`}><span>{row.label}</span><strong>{row.value}</strong><small>{row.detail}</small></div>)}</div></>}
            </section>;
          })}</div>
          <footer className="report-document-footer"><span>{report.contract}</span><strong>END OF FIELD COPY</strong><span>{report.sheets} indexed sheets</span></footer>
        </article>

        <aside className="dark-panel riveted report-inspector" aria-labelledby="report-inspector-title">
          <div className="panel-heading"><div><h2 id="report-inspector-title">Document record</h2><p>Authority and freshness</p></div></div>
          <dl><div><dt>Status</dt><dd><span className="viewer-status"><i aria-hidden="true" />{partial ? "Partial" : "Ready"}</span></dd></div><div><dt>Observed</dt><dd>{partial ? "Observation time unavailable" : report.observedAt}</dd></div><div><dt>Contract</dt><dd>{report.contract}</dd></div><div><dt>Stable identity</dt><dd>{report.id}</dd></div><div><dt>Career scope</dt><dd>{career.reference}</dd></div></dl>
          <div className="report-index"><strong>Document contents</strong>{report.sections.map((section, index) => <span key={section.title}><i>{String(index + 1).padStart(2, "0")}</i>{section.title}<small>{partial && index > 0 ? "Unavailable" : "Readable"}</small></span>)}</div>
          <div className="report-viewer-notice"><strong>Safe presentation contract</strong><p>The viewer does not generate, export, edit, recalculate or repair reports.</p><small>No local paths, SQL, raw payloads or other-career documents are exposed.</small></div>
        </aside>
      </div>
    </div>
  );
}

function SystemStatus({ state }: { state: RenderState }) {
  const [filter, setFilter] = useState<SystemFilter>("all");
  if (state === "unavailable") {
    return <section className="source-state riveted"><p className="panel-label">SYS-01 · Data status</p><h2>System health snapshot unavailable</h2><p>The global view could not read its sanitized health contract. No cached diagnostic, inferred process state or previous observation is substituted.</p><div><span>Presentation boundary</span><strong>Global context retained · details withheld</strong></div></section>;
  }

  const sourceChecks = state === "zeroes" ? [] : state === "partial" ? systemChecks.slice(0, 4) : systemChecks;
  const visibleChecks = filter === "all" ? sourceChecks : sourceChecks.filter((check) => check.status === filter);
  const counts = sourceChecks.reduce<Record<SystemHealth, number>>((total, check) => ({ ...total, [check.status]: total[check.status] + 1 }), { healthy: 0, attention: 0, stale: 0, unavailable: 0 });
  const filterLabels: Array<[SystemFilter, string]> = [["all", "All checks"], ["healthy", "Healthy"], ["attention", "Attention"], ["stale", "Stale"], ["unavailable", "Unavailable"]];
  const statusMarks: Record<SystemHealth, string> = { healthy: "✓", attention: "!", stale: "◷", unavailable: "—" };
  const attentionCount = counts.attention + counts.stale + counts.unavailable;

  return (
    <div className="system-grid">
      <section className="paper-card system-summary" aria-labelledby="system-summary-title">
        <div className="system-summary-heading">
          <div><p className="panel-label">SYS-01 · Mixed health</p><h2 id="system-summary-title">System observation board</h2><span>Global read-only snapshot · sanitized fixtures</span></div>
          <div className="system-stamp">STATUS COPY<br />READ ONLY</div>
        </div>
        <div className="system-totals">
          {(["healthy", "attention", "stale", "unavailable"] as SystemHealth[]).map((health) => <div key={health} data-state={health}><span>{health}</span><strong>{counts[health]}</strong><small>{health === "healthy" ? "Checks ready" : health === "attention" ? "Review advised" : health === "stale" ? "Not current" : "No observation"}</small></div>)}
        </div>
      </section>

      <section className="dark-panel riveted system-check-board" aria-labelledby="system-check-board-title">
        <div className="panel-heading"><div><h2 id="system-check-board-title">Health checks</h2><p>Configuration, database, sources and processing</p></div><span>{sourceChecks.length ? `${sourceChecks.length} observed` : "Valid empty set"}</span></div>
        <div className="system-filters" aria-label="Filter system health checks">{filterLabels.map(([value, label]) => <button key={value} className={filter === value ? "active" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
        {state === "partial" && <div className="system-warning"><strong>Partial health snapshot</strong><span>Only readable checks are shown. Missing checks are not reconstructed.</span></div>}
        {visibleChecks.length ? <div className="system-checks">{visibleChecks.map((check) => <article className="system-check" key={check.id}>
          <div className="system-check-heading"><span className={`system-state ${check.status}`}><i aria-hidden="true">{statusMarks[check.status]}</i>{check.statusLabel}</span><code>{check.id}</code></div>
          <span className="system-area">{check.area}</span><h3>{check.title}</h3><p>{check.summary}</p>
          <dl><div><dt>Observed</dt><dd>{check.observedAt}</dd></div><div><dt>Authority</dt><dd>{check.authority}</dd></div><div><dt>Stable reason</dt><dd>{check.reason}</dd></div></dl>
        </article>)}</div> : <div className="legitimate-empty system-empty"><strong>{sourceChecks.length ? "No checks match this filter" : "No status observations recorded"}</strong><span>{sourceChecks.length ? "Choose another health state." : "The health collection was read successfully and contains 0 authoritative observations."}</span></div>}
      </section>

      <aside className="squadron-panel riveted system-context" aria-labelledby="system-context-title">
        <div className="panel-heading"><div><h2 id="system-context-title">Snapshot contract</h2><p>Authority and interpretation</p></div></div>
        <dl><div><dt>Scope</dt><dd>Global application status</dd></div><div><dt>Contract</dt><dd>System health summary v1</dd></div><div><dt>Observed</dt><dd>{state === "partial" ? "Observation coverage incomplete" : sourceChecks.length ? "15 AUG 1917 · 23:41" : "No observations"}</dd></div><div><dt>Needs review</dt><dd>{attentionCount} of {sourceChecks.length} checks</dd></div></dl>
        <div className="system-key"><strong>Status key</strong>{(["healthy", "attention", "stale", "unavailable"] as SystemHealth[]).map((health) => <span key={health}><i className={health} aria-hidden="true">{statusMarks[health]}</i><b>{health}</b>{health === "healthy" ? "Readable and current" : health === "attention" ? "Warning recorded" : health === "stale" ? "Readable, not current" : "No current observation"}</span>)}</div>
        <div className="system-readonly-note"><strong>Safe system boundary</strong><p>No edit, repair, reset, auto-detect, process control or live-session command is available.</p><small>No local paths, SQL, cursors or raw payloads are displayed.</small></div>
      </aside>

      <section className="paper-card system-observations" aria-labelledby="system-observations-title">
        <div className="panel-heading paper-heading"><div><h2 id="system-observations-title">Observation ledger</h2><p>Sanitized summaries · not a live log</p></div><span>{sourceChecks.length} records</span></div>
        {sourceChecks.length ? <div className="system-observation-rows">{sourceChecks.slice(0, 4).map((check) => <div key={`observation-${check.id}`}><time>{check.observedAt}</time><span className={`system-state ${check.status}`}><i aria-hidden="true">{statusMarks[check.status]}</i>{check.statusLabel}</span><strong>{check.title}</strong><small>{check.reason}</small></div>)}</div> : <div className="legitimate-empty system-ledger-empty"><strong>Observation ledger is empty</strong><span>Zero is authoritative for this fixture; no historical event is invented.</span></div>}
      </section>
    </div>
  );
}

function SquadronRoster({ career, state, onSelect }: { career: Career; state: RenderState; onSelect: (member: Aircrew) => void }) {
  const [filter, setFilter] = useState<SquadronFilter>("all");
  if (career.id !== "rfc-14a-08f2") {
    return <section className="source-state riveted"><p className="panel-label">SQD-01 · Career-scoped fixture</p><h2>Squadron roster not supplied</h2><p>No roster fixture is available for {career.rank} {career.name}, {career.reference}. Personnel from another career are never substituted.</p><div><span>Selected source</span><strong>{career.slotLabel} · {career.squadron} · {career.service}</strong></div></section>;
  }
  if (state === "unavailable") {
    return <section className="source-state riveted"><p className="panel-label">SQD-01 · Data status</p><h2>Squadron roster unavailable</h2><p>The unit context remains visible, but the aircrew roster could not be read. No cached personnel or inferred availability is substituted.</p><div><span>Unit retained</span><strong>14 Squadron · Royal Flying Corps</strong></div></section>;
  }

  const sourceRecords = state === "zeroes" ? [] : state === "partial" ? aircrewRecords.slice(0, 4) : aircrewRecords;
  const visibleRecords = filter === "all"
    ? sourceRecords
    : filter === "a-flight"
      ? sourceRecords.filter((member) => member.flight === "A Flight")
      : filter === "b-flight"
        ? sourceRecords.filter((member) => member.flight === "B Flight")
        : sourceRecords.filter((member) => member.status !== "In service");
  const totals = state === "zeroes"
    ? [["Roster entries", "0", "None recorded"], ["In service", "0", "Authoritative"], ["Wounded", "0", "Authoritative"], ["Unavailable", "0", "Authoritative"]]
    : state === "partial"
      ? [["Roster entries", "4", "Readable entries"], ["In service", "4", "Confirmed"], ["Wounded", "—", "Unknown"], ["Unavailable", "—", "Unknown"]]
      : [["Roster entries", "11", "Current strength"], ["In service", "8", "Available"], ["Wounded", "2", "Recorded"], ["Unavailable", "1", "On leave"]];
  const filters: Array<[SquadronFilter, string]> = [["all", "All aircrew"], ["a-flight", "A Flight"], ["b-flight", "B Flight"], ["unavailable", "Unavailable"]];

  return (
    <div className="squadron-grid">
      <section className="paper-card squadron-register" aria-labelledby="squadron-register-title">
        <div className="squadron-register-heading"><div><p className="panel-label">SQD-01 · Unit strength</p><h2 id="squadron-register-title">14 Squadron · Royal Flying Corps</h2><span>{state === "partial" ? "Partial roster · confirmed entries only" : "Bailleul Aerodrome · 15 AUG 1917"}</span></div><div className="squadron-roundel" aria-hidden="true"><i>14</i></div></div>
        <div className="squadron-totals">{totals.map(([label, value, note]) => <div key={label} data-state={value === "—" ? "unknown" : value === "0" ? "zero" : "known"}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>)}</div>
      </section>

      <section className="dark-panel riveted squadron-roster" aria-labelledby="full-roster-title">
        <div className="panel-heading"><div><h2 id="full-roster-title">Aircrew roster</h2><p>Select a confirmed member to inspect the personnel record</p></div><span>{visibleRecords.length} shown</span></div>
        <div className="squadron-filters" aria-label="Filter squadron roster">{filters.map(([value, label]) => <button key={value} className={filter === value ? "active" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
        {visibleRecords.length ? <div className="aircrew-rows"><div className="aircrew-row aircrew-row-head" aria-hidden="true"><span>Flight</span><span>Aircrew</span><span>Role</span><span>Aircraft</span><span>Status</span><span>Missions</span><span /></div>{visibleRecords.map((member) => <button className="aircrew-row" key={member.id} onClick={() => onSelect(member)} aria-label={`Open aircrew profile for ${member.rank} ${member.name}`}><span>{member.flight}</span><span className="aircrew-name"><i aria-hidden="true">{member.initials}</i><b><strong>{member.rank} {member.name}</strong><small>{member.reference}</small></b></span><span>{member.role}</span><span>{member.aircraft.replace(" F.1", "")}</span><em className={member.tone}><StatusMark tone={member.tone} label={member.status} /></em><span>{member.missions}</span><b className="row-arrow" aria-hidden="true">›</b></button>)}</div> : <div className="legitimate-empty squadron-empty"><strong>{sourceRecords.length ? "No aircrew match this filter" : "No roster entries recorded"}</strong><span>{sourceRecords.length ? "Choose another flight or availability category." : "The roster was read successfully and is validly empty."}</span></div>}
      </section>

      <aside className="squadron-panel riveted command-board" aria-labelledby="command-board-title">
        <div className="panel-heading"><div><h2 id="command-board-title">Command &amp; readiness</h2><p>Recorded unit context</p></div></div>
        <dl><div><dt>Commanding officer</dt><dd>{state === "partial" ? "Maj. William Harcourt" : "Maj. William Harcourt"}</dd></div><div><dt>Station</dt><dd>{state === "partial" ? "Unknown" : "Bailleul Aerodrome"}</dd></div><div><dt>Primary aircraft</dt><dd>Sopwith Camel F.1</dd></div><div><dt>Service</dt><dd>Royal Flying Corps</dd></div></dl>
        <div className="readiness"><div><span>Pilot availability</span><strong>{state === "partial" ? "Unknown" : state === "zeroes" ? "0 / 0" : "8 / 11"}</strong><i><b style={{ width: state === "partial" || state === "zeroes" ? "0%" : "73%" }} /></i></div><div><span>Serviceable aircraft</span><strong>{state === "partial" ? "Unknown" : state === "zeroes" ? "0 / 0" : "10 / 12"}</strong><i><b style={{ width: state === "partial" || state === "zeroes" ? "0%" : "83%" }} /></i></div></div>
        <div className="provenance-note"><strong>Roster provenance</strong><span>{state === "partial" ? "Readable personnel entries only" : "Sanitized fixture · current unit state"}</span><small>No rank, recovery date or assignment is inferred</small></div>
      </aside>
    </div>
  );
}

function AircrewProfile({ member, state, onBack }: { member: Aircrew; state: RenderState; onBack: () => void }) {
  if (state === "unavailable" || state === "zeroes") {
    return <div className="aircrew-profile-flow"><button className="back-to-log" onClick={onBack}>← Return to Squadron Roster</button><section className="source-state riveted"><p className="panel-label">SQD-02 · Data status</p><h2>{state === "zeroes" ? "No aircrew profile recorded" : "Aircrew profile unavailable"}</h2><p>{state === "zeroes" ? "The roster is validly empty, so there is no personnel record to display." : "The selected personnel record could not be read. No cached service history is shown."}</p></section></div>;
  }

  const partial = state === "partial";
  const stats = [["Missions", String(member.missions), "Recorded"], ["Flight time", partial ? "—" : member.flightTime, partial ? "Unknown" : "Career total"], ["Victories", partial ? "—" : String(member.victories), partial ? "Unknown" : "Confirmed"], ["Claims", partial ? "—" : String(member.claims), partial ? "Unknown" : "Filed"], ["Joined unit", partial ? "—" : member.joined, partial ? "Unknown" : "Recorded date"], ["Last sortie", partial ? "—" : member.lastSortie, partial ? "Unknown" : "Recorded date"]];
  const events = partial ? [["CURRENT", `${member.flight} · ${member.role}`, "Confirmed assignment"]] : [[member.joined, "Joined 14 Squadron", "Recorded personnel event"], [member.lastSortie, "Latest recorded sortie", member.role], ["CURRENT", `${member.flight} assignment`, member.status]];

  return (
    <div className="aircrew-profile-flow">
      <button className="back-to-log" onClick={onBack}>← Return to Squadron Roster</button>
      <div className="aircrew-profile-grid">
        <section className="paper-card aircrew-identity" aria-labelledby="aircrew-identity-title">
          <p className="panel-label">SQD-02 · Personnel record</p>
          <div className="aircrew-identity-body"><div className="aircrew-monogram" aria-label="Neutral portrait fallback"><span>{member.initials}</span><small>Portrait unavailable</small></div><div><span className="service-kicker">Royal Flying Corps personnel file</span><h2 id="aircrew-identity-title">{member.rank} {member.name}</h2><p>{member.role} · {member.flight}</p><dl><div><dt>Aircraft</dt><dd>{member.aircraft}</dd></div><div><dt>Status</dt><dd><em className={member.tone}><StatusMark tone={member.tone} label={member.status} /></em></dd></div><div><dt>Reference</dt><dd>{member.reference}</dd></div></dl></div></div>
          <div className="field-stamp aircrew-stamp">PERSONNEL COPY · READ ONLY</div>
        </section>

        <section className="squadron-panel riveted aircrew-stats" aria-labelledby="aircrew-stats-title">
          <div className="panel-heading"><div><h2 id="aircrew-stats-title">Service totals</h2><p>Authoritative values only</p></div></div>
          <div className="aircrew-stat-grid">{stats.map(([label, value, note]) => <div key={label} data-state={value === "—" ? "unknown" : value === "0" ? "zero" : "known"}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>)}</div>
        </section>

        <section className="dark-panel riveted personnel-history" aria-labelledby="personnel-history-title">
          <div className="panel-heading"><div><h2 id="personnel-history-title">Personnel history</h2><p>Confirmed service events</p></div><span>{partial ? "Partial record" : "Field copy"}</span></div>
          <div className="personnel-note"><strong>Current service note</strong><p>{member.serviceNote}</p></div>
          <div className="personnel-events">{events.map(([date, title, detail], index) => <div key={`${date}-${title}`}><time>{date}</time><i>{String(index + 1).padStart(2, "0")}</i><span><strong>{title}</strong><small>{detail}</small></span></div>)}</div>
        </section>

        <section className="paper-card current-assignment" aria-labelledby="current-assignment-title">
          <div className="panel-heading paper-heading"><div><h2 id="current-assignment-title">Current assignment</h2><p>Roster position</p></div></div>
          <dl><div><dt>Unit</dt><dd>14 Squadron RFC</dd></div><div><dt>Flight</dt><dd>{member.flight}</dd></div><div><dt>Role</dt><dd>{member.role}</dd></div><div><dt>Aircraft type</dt><dd>{member.aircraft}</dd></div><div><dt>Availability</dt><dd><em className={member.tone}><StatusMark tone={member.tone} label={member.status} /></em></dd></div></dl>
          <div className="assignment-notice">This profile records roster state only. It does not predict recovery, promotion, reassignment or next sortie.</div>
        </section>

        <section className="dark-panel riveted aircrew-provenance" aria-labelledby="aircrew-provenance-title">
          <div className="panel-heading"><div><h2 id="aircrew-provenance-title">Record provenance</h2><p>Safe presentation contract</p></div></div>
          <dl><div><dt>Coverage</dt><dd>{partial ? "Partial record" : "Complete record"}</dd></div><div><dt>Identity</dt><dd>{member.reference}</dd></div><div><dt>Presentation</dt><dd>Sanitized fixture</dd></div></dl>
          <p>No private path, raw personnel payload, medical detail or inferred career event is displayed.</p>
        </section>
      </div>
    </div>
  );
}

function FixtureContractNotice({ scenario, surface, viewport }: { scenario: FixtureScenario; surface: FixtureSurface; viewport: FixtureViewportProfile }) {
  if (scenario.id === "complete") return null;
  return (
    <section className={`fixture-contract-notice ${scenario.tone}`} aria-label="Issue 80 fixture contract">
      <span><strong>FIX-80 · {surface.id} / {scenario.label} / {viewport.shortLabel}</strong><small>Desktop validation overlay</small></span>
      <p>{scenario.meaning}</p>
      <code>{scenario.reason}</code>
    </section>
  );
}

function FixtureLoadingFrame({ surface }: { surface: FixtureSurface }) {
  return (
    <section className="fixture-loading-frame riveted" aria-labelledby="fixture-loading-title" aria-busy="true">
      <div className="fixture-loading-copy"><p className="panel-label">{surface.id} · Loading</p><h2 id="fixture-loading-title">Loading sanitized fixture</h2><span>The desktop shell and view geometry remain visible. No previous-career values are reused.</span></div>
      <div className="fixture-skeleton-grid" aria-hidden="true"><i /><i /><i /><i /></div>
      <small>Read-only prototype · fixture_loading</small>
    </section>
  );
}

function FixtureSourceState({ scenario, surface }: { scenario: FixtureScenario; surface: FixtureSurface }) {
  return (
    <section className={`source-state fixture-source-state riveted ${scenario.tone}`} aria-labelledby="fixture-source-title">
      <p className="panel-label">{surface.id} · {scenario.group}</p>
      <h2 id="fixture-source-title">{scenario.label}</h2>
      <p>{scenario.meaning}</p>
      <p className="source-name">{scenario.id === "no-career" ? "Select a career to view its records." : `${surface.label} source · sanitized presentation contract`}</p>
      <div><span>Stable reason</span><code>{scenario.reason}</code><small>Career context is retained safely; no local path, SQL or raw payload is exposed.</small></div>
    </section>
  );
}

function FixtureStateActions({ state, onSelectCareer, onViewStatus, onRetry }: { state: FixtureState; onSelectCareer: () => void; onViewStatus: () => void; onRetry: () => void }) {
  if (["complete", "loading", "empty", "zeroes"].includes(state)) return null;
  return <section className="fixture-state-actions" aria-label="Read-only state actions">
    {state === "no-career" ? <button data-primary="true" onClick={onSelectCareer}>Select career</button> : <>
      {(state === "error" || state === "stale") && <button data-primary="true" onClick={onRetry}>{state === "error" ? "Retry view" : "Refresh snapshot"}</button>}
      <button onClick={onViewStatus}>View data status</button>
    </>}
    <small>Read-only preview: navigation or another sanitized snapshot. No files or settings are changed.</small>
  </section>;
}

function FixtureMatrixDialog({ panelRef, career, screenDraft, stateDraft, viewportDraft, statusDraft, onScreenDraft, onStateDraft, onViewportDraft, onStatusDraft, onCancel, onApply }: {
  panelRef: RefObject<HTMLElement | null>;
  career: Career;
  screenDraft: Screen;
  stateDraft: FixtureState;
  viewportDraft: FixtureViewport;
  statusDraft: string;
  onScreenDraft: (screen: Screen) => void;
  onStateDraft: (state: FixtureState) => void;
  onViewportDraft: (viewport: FixtureViewport) => void;
  onStatusDraft: (status: string) => void;
  onCancel: () => void;
  onApply: () => void;
}) {
  const selectedSurface = fixtureSurfaces.find((surface) => surface.screen === screenDraft) ?? fixtureSurfaces[0];
  const selectedScenario = fixtureScenarios.find((scenario) => scenario.id === stateDraft) ?? fixtureScenarios[0];
  const selectedViewport = fixtureViewports.find((viewport) => viewport.id === viewportDraft) ?? fixtureViewports[0];
  const referenceSnapshot = createPilotDossierSnapshot(dossierIdentityFromCareer(career), stateDraft);
  const referenceFields = referenceSnapshot.data ? [referenceSnapshot.data.missions, referenceSnapshot.data.flightMinutes, referenceSnapshot.data.confirmedVictories, referenceSnapshot.data.claimsCount, referenceSnapshot.data.skill, referenceSnapshot.data.reputation] : [];
  const fieldStates = (["known", "unknown", "unavailable", "invalid"] as const).map((state) => ({ state, count: referenceFields.filter((field) => field.state === state).length }));
  return (
    <div className="fixture-overlay" id="fixture-dialog" role="dialog" aria-modal="true" aria-labelledby="fixture-title" aria-describedby="fixture-description">
      <button className="overlay-dismiss" tabIndex={-1} aria-label="Close fixture matrix" onClick={onCancel} />
      <section ref={panelRef} className="fixture-panel" tabIndex={-1}>
        <header className="fixture-matrix-heading"><div><p className="panel-label">Issue #80 · Prototype controls</p><h2 id="fixture-title">Desktop fixture matrix</h2><p id="fixture-description">Select one screen, one semantic source state and one Windows scale profile. The preview never reads or writes live WoFF data.</p></div><span>READ ONLY<br />DESKTOP</span></header>

        <div className="fixture-matrix-selection" aria-live="polite"><small>Selected contract</small><strong>{selectedSurface.id} / {selectedScenario.label} / {selectedViewport.label}</strong><code>{selectedScenario.reason}</code></div>

        <div className="fixture-workbench">
          <fieldset className="fixture-surface-picker"><legend>Screen ID</legend><div>{fixtureSurfaces.map((surface) => <button key={surface.id} className={screenDraft === surface.screen ? "active" : ""} aria-pressed={screenDraft === surface.screen} onClick={() => onScreenDraft(surface.screen)}><code>{surface.id}</code><span>{surface.label}</span></button>)}</div></fieldset>

          <fieldset className="fixture-state-picker"><legend>Semantic state</legend><div className="fixture-state-grid">{fixtureScenarios.map((scenario) => <button key={scenario.id} className={`${stateDraft === scenario.id ? "active" : ""} ${scenario.tone}`} aria-pressed={stateDraft === scenario.id} onClick={() => onStateDraft(scenario.id)}><span><small>{scenario.group}</small><strong>{scenario.label}</strong></span><em>{scenario.meaning}</em><code>{scenario.reason}</code></button>)}</div></fieldset>
        </div>

        <fieldset className="fixture-viewport-picker"><legend>Desktop viewport profile</legend><div>{fixtureViewports.map((viewport) => <button key={viewport.id} className={viewportDraft === viewport.id ? "active" : ""} aria-pressed={viewportDraft === viewport.id} onClick={() => onViewportDraft(viewport.id)}><strong>{viewport.label}</strong><span>{viewport.canvas}</span></button>)}</div></fieldset>

        <label className="fixture-status-picker">Pilot status fixture
          <select aria-label="Pilot status fixture" value={statusDraft} onChange={event => onStatusDraft(event.target.value)}>{pilotStatusFixtures.map(status => <option key={status.id} value={status.id}>{status.label}</option>)}</select>
          <small>Presentation only; normalized values are never merged into generic Wounded.</small>
        </label>

        <section className="snapshot-contract-inspector" aria-labelledby="snapshot-contract-title">
          <header><div><p className="panel-label">Issue #81 · Reference contract</p><h3 id="snapshot-contract-title">PilotDossierSnapshot</h3></div><span>{Object.isFrozen(referenceSnapshot) && Object.isFrozen(referenceSnapshot.meta) ? "DEEP FROZEN" : "NOT FROZEN"}</span></header>
          <dl><div><dt>career_id</dt><dd>{referenceSnapshot.identityKey ?? "No career selected"}</dd></div><div><dt>Envelope</dt><dd>{referenceSnapshot.state}</dd></div><div><dt>Contract</dt><dd>{referenceSnapshot.meta.version}</dd></div><div><dt>Authority</dt><dd>{referenceSnapshot.meta.authority}</dd></div><div><dt>Observed</dt><dd>{referenceSnapshot.meta.observedAt ?? "Unknown"}</dd></div><div><dt>Freshness</dt><dd>{referenceSnapshot.meta.freshness}</dd></div></dl>
          <div className="snapshot-field-states">{fieldStates.map(({ state, count }) => <span key={state} data-state={state}><strong>{count}</strong><small>{state}</small></span>)}</div>
          <p><strong>Stable reason</strong><code>{referenceSnapshot.reason ?? "snapshot_ready"}</code><span>{referenceSnapshot.meta.safeSourceSummary}</span></p>
        </section>

        <footer className="fixture-actions"><p>Fixtures are sanitized. No edit, delete, import, repair, confirmation or live binding is available.</p><div><button className="close-fixtures" onClick={onCancel}>Cancel</button><button className="apply-fixture" data-primary="true" onClick={onApply}>Apply desktop preview</button></div></footer>
      </section>
    </div>
  );
}

export default function Home() {
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [fixtureState, setFixtureState] = useState<FixtureState>("complete");
  const [fixtureViewport, setFixtureViewport] = useState<FixtureViewport>("desktop-100");
  const [fixtureScreenDraft, setFixtureScreenDraft] = useState<Screen>("dashboard");
  const [fixtureStateDraft, setFixtureStateDraft] = useState<FixtureState>("complete");
  const [fixtureViewportDraft, setFixtureViewportDraft] = useState<FixtureViewport>("desktop-100");
  const [fixtureStatus, setFixtureStatus] = useState("career");
  const [fixtureStatusDraft, setFixtureStatusDraft] = useState("career");
  const [retryPending, setRetryPending] = useState(false);
  const [activeCareer, setActiveCareer] = useState(careers[0]);
  const [pendingCareer, setPendingCareer] = useState<Career | null>(null);
  const [careerTransition, setCareerTransition] = useState(false);
  const [selectedMission, setSelectedMission] = useState<Mission | null>(missionRecords[0]);
  const [selectedAircrew, setSelectedAircrew] = useState<Aircrew | null>(aircrewRecords[1]);
  const [selectedReport, setSelectedReport] = useState<ReportRecord | null>(reportRecords[0]);
  const [careerOpen, setCareerOpen] = useState(false);
  const [fixturesOpen, setFixturesOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("Operations Board ready.");
  const contentRef = useRef<HTMLElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const careerButtonRef = useRef<HTMLButtonElement>(null);
  const careerMenuRef = useRef<HTMLDivElement>(null);
  const fixturePanelRef = useRef<HTMLElement>(null);
  const fixtureReturnFocusRef = useRef<HTMLButtonElement | null>(null);
  const previousScreenRef = useRef<Screen>(screen);
  const previousCareerRef = useRef(activeCareer.id);

  function focusHeading() {
    queueMicrotask(() => headingRef.current?.focus());
    requestAnimationFrame(() => headingRef.current?.focus());
  }

  function openFixtures(trigger: HTMLButtonElement) {
    fixtureReturnFocusRef.current = trigger;
    setFixtureScreenDraft(screen);
    setFixtureStateDraft(fixtureState);
    setFixtureViewportDraft(fixtureViewport);
    setFixtureStatusDraft(fixtureStatus);
    setFixturesOpen(true);
  }

  function closeFixtures() {
    setFixturesOpen(false);
    requestAnimationFrame(() => fixtureReturnFocusRef.current?.focus());
  }

  function applyFixturePreview() {
    const surface = fixtureSurfaces.find((item) => item.screen === fixtureScreenDraft) ?? fixtureSurfaces[0];
    const scenario = fixtureScenarios.find((item) => item.id === fixtureStateDraft) ?? fixtureScenarios[0];
    const viewport = fixtureViewports.find((item) => item.id === fixtureViewportDraft) ?? fixtureViewports[0];
    setScreen(fixtureScreenDraft);
    setFixtureState(fixtureStateDraft);
    setFixtureViewport(fixtureViewportDraft);
    setFixtureStatus(fixtureStatusDraft);
    setRetryPending(false);
    setFixturesOpen(false);
    setCareerOpen(false);
    setAnnouncement(`${surface.id}, ${scenario.label}, desktop ${viewport.shortLabel} fixture displayed.`);
    focusHeading();
  }

  function selectCareer(career: Career) {
    setCareerOpen(false);
    setFixtureState("complete");
    setFixtureStatus("career");
    setRetryPending(false);
    if (career.id === activeCareer.id) {
      setAnnouncement(`${career.rank} ${career.name}, career ${career.reference}, remains selected.`);
      requestAnimationFrame(() => careerButtonRef.current?.focus());
      return;
    }
    setCareerTransition(true);
    setPendingCareer(career);
    setScreen("dashboard");
    setSelectedMission(null);
    setSelectedAircrew(null);
    setSelectedReport(null);
    setAnnouncement(`Loading ${career.rank} ${career.name}, career ${career.reference}. Previous-career content cleared.`);
  }

  function viewDataStatus() {
    setFixtureState("complete");
    setRetryPending(false);
    chooseNav("Data & System Status");
  }

  function retryView() {
    setFixtureState("loading");
    setRetryPending(true);
    setAnnouncement("Requesting another sanitized snapshot. No file or setting is changed.");
    focusHeading();
  }

  useEffect(() => {
    if (!retryPending) return;
    const retry = setTimeout(() => {
      setFixtureState("complete");
      setRetryPending(false);
      setAnnouncement("Sanitized snapshot ready. Screen and career selection retained.");
    }, 1000);
    return () => clearTimeout(retry);
  }, [retryPending]);

  function handleCareerKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const options = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="option"]'));
    const current = (event.target as HTMLElement).closest<HTMLButtonElement>('[role="option"]');
    const currentIndex = current ? options.indexOf(current) : 0;
    const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : event.key === "ArrowDown" ? (currentIndex + 1) % options.length : (currentIndex - 1 + options.length) % options.length;
    event.preventDefault();
    options[nextIndex]?.focus();
  }

  useEffect(() => {
    if (!pendingCareer) return;
    const frame = requestAnimationFrame(() => {
      setActiveCareer(pendingCareer);
      setPendingCareer(null);
      setCareerTransition(false);
      setAnnouncement(`${pendingCareer.rank} ${pendingCareer.name}, career ${pendingCareer.reference}, selected.`);
    });
    return () => cancelAnimationFrame(frame);
  }, [pendingCareer]);

  useEffect(() => {
    const screenChanged = previousScreenRef.current !== screen;
    const careerChanged = previousCareerRef.current !== activeCareer.id;
    previousScreenRef.current = screen;
    previousCareerRef.current = activeCareer.id;
    if (careerTransition || (!screenChanged && !careerChanged)) return;
    focusHeading();
  }, [activeCareer.id, careerTransition, screen]);

  useEffect(() => {
    if (!careerOpen) return;
    requestAnimationFrame(() => careerMenuRef.current?.querySelector<HTMLButtonElement>('[aria-selected="true"]')?.focus());
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setCareerOpen(false);
      requestAnimationFrame(() => careerButtonRef.current?.focus());
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [careerOpen]);

  useEffect(() => {
    if (!fixturesOpen) return;
    const panel = fixturePanelRef.current;
    requestAnimationFrame(() => panel?.querySelector<HTMLButtonElement>("button")?.focus());
    const handleDialogKeys = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setFixturesOpen(false);
        requestAnimationFrame(() => fixtureReturnFocusRef.current?.focus());
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const controls = Array.from(panel.querySelectorAll<HTMLElement>('button:not([disabled]), select:not([disabled])'));
      if (!controls.length) return;
      const first = controls[0];
      const last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", handleDialogKeys);
    return () => document.removeEventListener("keydown", handleDialogKeys);
  }, [fixturesOpen]);

  function chooseNav(label: string) {
    if (label === "Operations") { setScreen("dashboard"); setAnnouncement("Operations Board displayed."); }
    if (label === "Pilot Dossier") { setScreen("pilot"); setAnnouncement("Pilot Dossier displayed."); }
    if (label === "Missions") { setScreen("missions"); setAnnouncement("Mission Log displayed."); }
    if (label === "Squadron") { setScreen("squadron"); setAnnouncement("Squadron Roster displayed."); }
    if (label === "War Diary") { setScreen("diary"); setAnnouncement("War Diary displayed."); }
    if (label === "Reports") { setScreen("reports"); setAnnouncement("Reports Library displayed."); }
    if (label === "Data & System Status") { setScreen("system"); setAnnouncement("Data & System Status displayed."); }
    focusHeading();
  }

  function openMission(mission: Mission) {
    setSelectedMission(mission);
    setScreen("mission-report");
    setAnnouncement(`Mission report ${mission.id} displayed.`);
  }

  function openAircrew(member: Aircrew) {
    setSelectedAircrew(member);
    setScreen("aircrew-profile");
    setAnnouncement(`Aircrew profile ${member.reference} displayed.`);
  }

  function openReport(report: ReportRecord) {
    setSelectedReport(report);
    setScreen("report-viewer");
    setAnnouncement(`Report ${report.id} displayed.`);
  }

  function openDossierContext(next: "career-record" | "victories-claims" | "decorations") {
    setScreen(next);
    const label = next === "career-record" ? "Career Record" : next === "victories-claims" ? "Victories & Claims" : "Decorations";
    setAnnouncement(`${label} displayed.`);
  }

  function isNavActive(label: string) {
    if (label === "Operations") return screen === "dashboard" || screen === "app-shell" || screen === "career-selector";
    if (label === "Pilot Dossier") return screen === "pilot" || screen === "career-record" || screen === "victories-claims" || screen === "decorations";
    if (label === "Missions") return screen === "missions" || screen === "mission-report";
    if (label === "Squadron") return screen === "squadron" || screen === "aircrew-profile";
    if (label === "War Diary") return screen === "diary";
    if (label === "Reports") return screen === "reports" || screen === "report-viewer";
    if (label === "Data & System Status") return screen === "system";
    return false;
  }

  const headerReference = screen === "mission-report"
    ? selectedMission?.id
    : screen === "aircrew-profile"
      ? selectedAircrew?.reference
      : screen === "diary"
        ? `JRN-01 · ${diaryRecords.filter((entry) => entry.careerId === activeCareer.id).length} ENTRIES`
        : screen === "reports"
          ? `RPT-01 · ${reportRecords.filter((report) => report.careerId === activeCareer.id).length} REPORTS`
          : screen === "report-viewer"
            ? selectedReport?.id
            : screen === "system"
              ? "SYS-01 · MIXED HEALTH"
            : undefined;

  const activeFixture = fixtureScenarios.find((scenario) => scenario.id === fixtureState) ?? fixtureScenarios[0];
  const activeSurface = fixtureSurfaces.find((surface) => surface.screen === screen) ?? fixtureSurfaces[0];
  const activeViewport = fixtureViewports.find((viewport) => viewport.id === fixtureViewport) ?? fixtureViewports[0];
  const renderState = activeFixture.renderState;
  const statusFixture = pilotStatusFixtures.find(status => status.id === fixtureStatus) ?? pilotStatusFixtures[0];
  const presentationCareer = fixtureStatus === "career" ? activeCareer : { ...activeCareer, status: statusFixture.value };
  const pilotDossierSnapshot = createPilotDossierSnapshot(dossierIdentityFromCareer(presentationCareer), fixtureState);

  return (
    <div className="desktop-preview" style={{ "--preview-width": `${activeViewport.width}px`, "--preview-height": `${activeViewport.height}px` } as CSSProperties}>
    <div className="app-shell" data-prototype="desktop" data-fixture-viewport={fixtureViewport} data-fixture-state={fixtureState} data-screen-id={activeSurface.id}>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div className="workspace">
        <Header career={activeCareer} state={renderState} fixtureBadge={careerTransition ? "CAREER CHANGE · PREVIOUS CONTENT CLEARED" : activeFixture.id === "complete" ? undefined : activeFixture.badge} hasCareerContext={!careerTransition && activeFixture.id !== "no-career"} screen={screen} viewReference={headerReference} careerOpen={careerOpen} careerButtonRef={careerButtonRef} headingRef={headingRef} onCareerClick={() => setCareerOpen((open) => !open)} />
        {!careerTransition && careerOpen && <div ref={careerMenuRef} className="career-menu" id="career-selector" role="listbox" aria-label="Available careers" onKeyDown={handleCareerKeyDown}>{careers.map((career) => <button key={career.id} role="option" tabIndex={career.id === activeCareer.id ? 0 : -1} aria-selected={career.id === activeCareer.id} onClick={() => selectCareer(career)}><span><strong>{career.rank} {career.name}</strong><small>{career.slotLabel} · {career.squadron} · {career.service} · {presentPilotStatus(career.status).display}</small></span><code>{career.reference}</code></button>)}</div>}
        <aside className="sidebar" id="desktop-primary-navigation" aria-label="Primary navigation">
          <div className="brand"><strong>WoFF Mate</strong><span>Campaign companion</span></div>
          <section className="watchdog" aria-label="Watchdog status"><small>Watchdog</small><strong><i aria-hidden="true" />Running</strong></section>
          <div className="side-rule" />
          <nav>{navItems.map((label) => <button key={label} className={isNavActive(label) ? "active" : ""} aria-current={isNavActive(label) ? "page" : undefined} onClick={() => chooseNav(label)}>{label}</button>)}</nav>
          <button className={`system-status-trigger ${isNavActive("Data & System Status") ? "active" : ""}`} aria-current={isNavActive("Data & System Status") ? "page" : undefined} onClick={() => chooseNav("Data & System Status")}><span><i aria-hidden="true" /> Data &amp; System Status</span><small>Mixed health</small></button>
          <button className="fixture-trigger" aria-haspopup="dialog" aria-expanded={fixturesOpen} aria-controls="fixture-dialog" onClick={(event) => openFixtures(event.currentTarget)}><span><i aria-hidden="true" /> Fixture matrix</span><small>{activeSurface.id} · {activeFixture.label} · {activeViewport.shortLabel}</small></button>
        </aside>

        <main ref={contentRef} className="workspace-content" id="main-content" tabIndex={-1} aria-labelledby="screen-title">
        <FixtureContractNotice scenario={activeFixture} surface={activeSurface} viewport={activeViewport} />
        {careerTransition
          ? <FixtureLoadingFrame surface={{ screen: "career-selector", id: "SEL-01", label: "Career transition" }} />
          : activeFixture.mode === "loading"
          ? <FixtureLoadingFrame surface={activeSurface} />
          : activeFixture.mode === "source"
            ? <FixtureSourceState scenario={activeFixture} surface={activeSurface} />
            : screen === "app-shell"
              ? <ApplicationShellReference career={activeCareer} />
              : screen === "career-selector"
                ? <CareerSelectorReference activeCareer={activeCareer} onSelect={selectCareer} />
            : screen === "dashboard"
          ? <Operations career={presentationCareer} state={renderState} onOpenMission={openMission} onOpenAircrew={openAircrew} />
          : screen === "pilot"
            ? <PilotDossier snapshot={pilotDossierSnapshot} onOpenContext={openDossierContext} />
            : screen === "career-record" || screen === "victories-claims" || screen === "decorations"
              ? <DossierContextView screen={screen} snapshot={pilotDossierSnapshot} onBack={() => { setScreen("pilot"); setAnnouncement("Pilot Dossier displayed."); }} />
            : screen === "missions"
              ? <MissionLog career={activeCareer} state={renderState} onSelect={openMission} />
              : screen === "mission-report"
                ? selectedMission && selectedMission.careerId === activeCareer.id
                  ? <MissionReport mission={selectedMission} state={renderState} onBack={() => { setScreen("missions"); setAnnouncement("Mission Log displayed."); }} />
                  : <section className="source-state riveted"><p className="panel-label">MIS-02 · Cleared detail</p><h2>Mission report not selected</h2><p>No previous-career mission report is retained.</p></section>
                : screen === "diary"
                  ? <WarDiary career={activeCareer} state={renderState} onOpenMission={openMission} />
                  : screen === "reports"
                    ? <ReportsLibrary career={activeCareer} state={renderState} onSelect={openReport} />
                    : screen === "report-viewer"
                      ? selectedReport && selectedReport.careerId === activeCareer.id
                        ? <ReportViewer report={selectedReport} career={activeCareer} state={renderState} onBack={() => { setScreen("reports"); setAnnouncement("Reports Library displayed."); }} />
                        : <section className="source-state riveted"><p className="panel-label">RPT-02 · Cleared detail</p><h2>Report not selected</h2><p>No previous-career report is retained.</p></section>
                      : screen === "system"
                        ? <SystemStatus state={renderState} />
                      : screen === "squadron"
                        ? <SquadronRoster career={activeCareer} state={renderState} onSelect={openAircrew} />
                        : selectedAircrew && activeCareer.id === "rfc-14a-08f2"
                          ? <AircrewProfile member={selectedAircrew} state={renderState} onBack={() => { setScreen("squadron"); setAnnouncement("Squadron Roster displayed."); }} />
                          : <section className="source-state riveted"><p className="panel-label">SQD-02 · Cleared detail</p><h2>Aircrew profile not selected</h2><p>No personnel record from another career is retained.</p></section>}
        {!careerTransition && <FixtureStateActions state={fixtureState} onSelectCareer={() => setCareerOpen(true)} onViewStatus={viewDataStatus} onRetry={retryView} />}
        </main>
      </div>

      {fixturesOpen && <FixtureMatrixDialog panelRef={fixturePanelRef} career={presentationCareer} screenDraft={fixtureScreenDraft} stateDraft={fixtureStateDraft} viewportDraft={fixtureViewportDraft} statusDraft={fixtureStatusDraft} onScreenDraft={setFixtureScreenDraft} onStateDraft={setFixtureStateDraft} onViewportDraft={setFixtureViewportDraft} onStatusDraft={setFixtureStatusDraft} onCancel={closeFixtures} onApply={applyFixturePreview} />}
      <div className="announcement" role="status" aria-live="polite">{announcement}</div>
    </div>
    </div>
  );
}
