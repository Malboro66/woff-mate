import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import test from "node:test";

test("renders the WoFF Mate Operations Board identity", async () => {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  const response = await worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );

  assert.equal(response.status, 200);
  assert.match(
    response.headers.get("content-type") ?? "",
    /^text\/html\b/i,
  );
  const html = await response.text();
  assert.match(html, /<title>WoFF Mate UI V2<\/title>/i);
  assert.match(html, /Operations Board/i);
  assert.match(html, /Recent sorties/i);
  assert.match(html, /14 Squadron/i);
  assert.doesNotMatch(html, /Starter Project/i);
});

test("includes the read-only Missions to Mission Report flow", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(source, /MIS-01 · Sortie index/i);
  assert.match(source, /MIS-02 · Mission report/i);
  assert.match(source, /Return to Mission Log/i);
  assert.match(source, /No mission is recalculated by this view/i);
});

test("includes the read-only Squadron to Aircrew Profile flow", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(source, /SQD-01 · Unit strength/i);
  assert.match(source, /SQD-02 · Personnel record/i);
  assert.match(source, /Return to Squadron Roster/i);
  assert.match(source, /No rank, recovery date or assignment is inferred/i);
});

test("includes the career-scoped read-only War Diary timeline", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(source, /JRN-01 · Campaign chronicle/i);
  assert.match(source, /Narrative timeline/i);
  assert.match(source, /Open linked mission report/i);
  assert.match(source, /entry\.careerId === career\.id/i);
  assert.match(source, /No create, edit, delete, save or regeneration commands are exposed/i);
  assert.match(source, /No game paths, SQL, raw payloads or previous-career entries are displayed/i);
});

test("includes the career-scoped Reports Library to Report Viewer flow", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(source, /RPT-01 · Produced reports/i);
  assert.match(source, /RPT-02 · Report viewer/i);
  assert.match(source, /Return to Reports Library/i);
  assert.match(source, /report\.careerId === career\.id/i);
  assert.match(source, /report\.careerId !== career\.id/i);
  assert.match(source, /No generation, export, import, editing, deletion or repair action is available/i);
  assert.match(source, /does not generate, export, edit, recalculate or repair reports/i);
});

test("includes the global read-only mixed System Status view", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(source, /SYS-01 · Mixed health/i);
  assert.match(source, /Configuration · Database · Sources · Processing/i);
  assert.match(source, /snapshot_age_exceeded/i);
  assert.match(source, /processing_snapshot_missing/i);
  assert.match(source, /No edit, repair, reset, auto-detect, process control or live-session command is available/i);
  assert.match(source, /No local paths, SQL, cursors or raw payloads are displayed/i);
  assert.match(css, /\.system-status-trigger[\s\S]*margin-top: auto/i);
});

test("preserves keyboard, contrast, and 100–200% scaling contracts", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(source, /className="skip-link" href="#main-content"/i);
  assert.match(source, /className="workspace-content" id="main-content" tabIndex=\{-1\} aria-labelledby="screen-title"/i);
  assert.match(source, /aria-controls="career-selector" aria-haspopup="listbox"/i);
  assert.match(source, /\["ArrowDown", "ArrowUp", "Home", "End"\]/i);
  assert.match(source, /event\.key === "Escape"/i);
  assert.match(source, /button:not\(\[disabled\]\)/i);
  assert.match(source, /function StatusMark/i);
  assert.match(source, /className="status-mark" aria-hidden="true"/i);
  assert.match(source, /id="desktop-primary-navigation"/i);
  assert.match(source, /const navItems = \["Operations", "Pilot Dossier", "Missions", "Squadron", "War Diary", "Reports"\]/i);
  assert.match(source, /<h1 ref=\{headingRef\} id="screen-title" tabIndex=\{-1\}>/i);
  assert.match(source, /headingRef\.current\?\.focus\(\)/i);
  assert.match(source, /function chooseNav[\s\S]*?focusHeading\(\);/i);
  assert.match(source, /data-prototype="desktop" data-fixture-viewport=/i);
  assert.match(source, /Desktop 100%/i);
  assert.match(source, /Desktop 125%/i);
  assert.match(source, /Desktop 150%/i);
  assert.match(source, /Desktop 200%/i);
  assert.doesNotMatch(source, /mobile-footer-nav|mobile-primary-navigation|mobile-menu/i);
  assert.match(css, /:where\(button, a, \[tabindex\]\):focus-visible/i);
  assert.match(css, /0 0 0 3px #f7f2e6, 0 0 0 6px #7d5a18 !important/i);
  assert.match(css, /\.workspace-content:focus-visible[\s\S]*#f7f2e6[\s\S]*#7d5a18/i);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/i);
  assert.match(css, /@media \(prefers-contrast: more\)/i);
  assert.match(css, /@media \(forced-colors: active\)/i);
  assert.match(css, /body \{[\s\S]*?min-width: 720px/i);
  assert.match(css, /container: desktop \/ inline-size/i);
  assert.match(css, /@container desktop \(max-width: 820px\)[\s\S]*?\.app-shell \{ --sidebar: 184px; \}[\s\S]*?\.sidebar \{ display: flex/i);
  assert.match(css, /\.dossier-stats \{[^}]*repeat\(6/i);
  assert.match(css, /@container desktop \(max-width: 1180px\)[\s\S]*\.dossier-stats \{[^}]*repeat\(3/i);
  assert.match(css, /@container desktop \(max-width: 820px\)[\s\S]*\.dossier-stats \{[^}]*repeat\(2/i);
  assert.match(css, /\.mission-row-head,[\s\S]*\.aircrew-row-head \{ display: none; \}/i);
  assert.match(css, /\.table-wrap \{ overflow: visible; \}/i);
  assert.match(css, /UI V2 rendered-conformance floor/i);
  assert.match(css, /font-size: max\(12px, 1em\) !important/i);
  assert.match(css, /small, code, dt, dd, th, td, p, span, em, strong, button/i);
  assert.match(css, /\.paper-card[\s\S]*?--surface-text: #201d18/i);
  assert.match(css, /\.aircrew-monogram small[\s\S]*?color: #f4efe2 !important/i);
  assert.match(css, /\.report-document :where\(span, small, dt, code, time\)/i);
  assert.match(css, /\.assignment-notice[^}]*color: #5b5345[^}]*font-size: 12px/i);
  assert.match(css, /\.report-code[^}]*font-size: 12px/i);
  assert.match(css, /\.system-key b[^}]*font-size: 12px/i);
  assert.match(css, /\.ledger-list i,[\s\S]*\.report-index > span > i \{ font-size: 12px !important; \}/i);
});

test("clears previous-career content before presenting a new stable identity", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  assert.match(source, /const \[pendingCareer, setPendingCareer\]/i);
  assert.match(source, /const \[careerTransition, setCareerTransition\]/i);
  assert.match(source, /setCareerTransition\(true\)/i);
  assert.match(source, /setScreen\("dashboard"\)/i);
  assert.match(source, /setSelectedMission\(null\)/i);
  assert.match(source, /setSelectedAircrew\(null\)/i);
  assert.match(source, /setSelectedReport\(null\)/i);
  assert.match(source, /mission\.careerId === career\.id/i);
  assert.match(source, /careerTransition[\s\S]*?<FixtureLoadingFrame/i);
  assert.match(source, /WoFF Pilot 1/i);
  assert.match(source, /WoFF Pilot 2/i);
  assert.match(source, /WoFF Pilot 3/i);
  assert.match(source, /Slots remain persistent and may be sparse/i);
  assert.match(source, /data-fixture="sparse-slots-2-3"/i);
  assert.match(source, /sparseCareers = careers\.filter/i);
  assert.match(source, /Pilot1 vacant/i);
});

test("implements the Issue 80 desktop fixture matrix", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  const requiredStates = ["Loading", "Empty", "Partial", "Missing", "Truncated", "Unsupported", "Unreadable", "Error", "Stale", "Authoritative zeroes", "Unknown values", "Not available", "No career"];
  const requiredSurfaces = ["APP-00", "SEL-01", "OPR-01", "DOS-01", "DOS-02", "DOS-03", "DOS-04", "MIS-01", "MIS-02", "SQD-01", "SQD-02", "JRN-01", "RPT-01", "RPT-02", "SYS-01"];

  assert.match(source, /Issue #80 · Prototype controls/i);
  assert.match(source, /Desktop fixture matrix/i);
  for (const state of requiredStates) assert.match(source, new RegExp(state, "i"));
  for (const surface of requiredSurfaces) assert.match(source, new RegExp(surface, "i"));
  assert.match(source, /fixture_loading/i);
  assert.match(source, /collection_empty/i);
  assert.match(source, /record_truncated/i);
  assert.match(source, /source_format_unsupported/i);
  assert.match(source, /source_unreadable/i);
  assert.match(source, /query_error/i);
  assert.match(source, /never coerced to zero/i);
  assert.match(source, /No edit, delete, import, repair, confirmation or live binding is available/i);
});

test("implements the immutable Issue 81 presentation contract", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  const contract = await readFile(new URL("../app/view-models.ts", import.meta.url), "utf8");

  for (const state of ["loading", "ready", "empty", "missing", "stale", "unavailable", "error"]) {
    assert.match(contract, new RegExp(`SnapshotState[^;]+${state}`, "i"));
  }
  for (const fieldState of ["known", "unknown", "unavailable", "invalid"]) {
    assert.match(contract, new RegExp(`FieldState[^;]+${fieldState}`, "i"));
  }

  assert.match(contract, /Readonly<\{[\s\S]*?contract: string;[\s\S]*?authority: string;[\s\S]*?freshness: Freshness;/i);
  assert.match(contract, /function deepFreeze<[^>]+>[\s\S]*?Object\.freeze\(value\)/i);
  assert.match(contract, /identityKey: identity\.careerId/i);
  assert.match(contract, /version: "pilot-dossier\.v1"/i);
  assert.match(contract, /authority: "Sanitized fixture query service"/i);
  assert.match(contract, /stale: "snapshot_age_exceeded"/i);
  assert.match(contract, /careerId === "rfc-14a-08f2"/i);
  assert.match(contract, /careerId === "raf-41b-22c1"/i);
  assert.match(contract, /portrait_not_supplied/i);
  assert.match(contract, /no SQL, parser payload, cursor or local path/i);

  assert.match(page, /Issue #81 · Reference contract/i);
  assert.match(page, /PilotDossierSnapshot/i);
  assert.match(page, /DEEP FROZEN/i);
  assert.match(page, /career_id/i);
  assert.match(page, /createPilotDossierSnapshot/i);
});

test("uses real wood, wool-felt, and paper material textures", async () => {
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(css, /url\("\/textures\/sidebar-wood\.webp"\)/i);
  assert.match(css, /url\("\/textures\/workspace-felt\.webp"\)/i);
  assert.match(css, /url\("\/textures\/card-paper\.webp"\)/i);

  const [wood, felt, paper] = await Promise.all([
    stat(new URL("../public/textures/sidebar-wood.webp", import.meta.url)),
    stat(new URL("../public/textures/workspace-felt.webp", import.meta.url)),
    stat(new URL("../public/textures/card-paper.webp", import.meta.url)),
  ]);
  assert.ok(wood.size > 1_000);
  assert.ok(felt.size > 1_000);
  assert.ok(paper.size > 1_000);
});
