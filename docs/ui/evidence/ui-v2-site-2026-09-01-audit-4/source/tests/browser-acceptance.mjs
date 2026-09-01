import assert from "node:assert/strict";

// Browser results can cross JavaScript realms; compare their serializable
// values, not realm-specific Array prototypes.
function sameValues(actual, expected, message) {
  assert.equal(JSON.stringify(actual), JSON.stringify(expected), message);
}

// Driver contract: the documented control-browser tab.playwright API. Run in
// the supervised Sites preview; no DOM writes, app internals or forced clicks.
export const screens = ["APP-00", "SEL-01", "OPR-01", "DOS-01", "DOS-02", "DOS-03", "DOS-04", "MIS-01", "MIS-02", "SQD-01", "SQD-02", "JRN-01", "RPT-01", "RPT-02", "SYS-01"];
export const states = {
  complete: "Ready Complete", loading: "Transition Loading", empty: "Valid empty Empty",
  partial: "Degraded Partial", "no-career": "Context No career", missing: "Absent Missing",
  truncated: "Degraded Truncated", unsupported: "Format Unsupported", unreadable: "Failure Unreadable",
  error: "Failure Error", stale: "Freshness Stale", zeroes: "Valid value Authoritative zeroes",
  unknown: "Field state Unknown values", unavailable: "Absent Not available",
};
export const profiles = { 100: [1440, 1024, 256], 125: [1152, 819, 232], 150: [960, 683, 232], 200: [720, 512, 184] };
export const statusCases = [
  ["Active", "Active"], ["KIA", "Killed in Action (KIA)"], ["PoW", "Prisoner of War (PoW)"],
  ["MIA", "Missing in Action (MIA)"], ["Invalided Out", "Invalided Out"], ["Survived War", "Survived War"],
  ["Lightly Wounded", "Lightly Wounded"], ["Seriously Wounded", "Seriously Wounded"],
  ["missing", "Unknown"], ["blank", "Unknown"], ["unavailable", "Unknown"], ["future", "Transferred (future)"],
];

export async function selectFixture(tab, { screen = "DOS-01", state = "complete", scale = 100, status = "career" } = {}) {
  await tab.playwright.getByRole("button", { name: /^Fixture matrix/ }).click();
  const dialog = tab.playwright.getByRole("dialog", { name: "Desktop fixture matrix" });
  await dialog.waitFor({ state: "visible" });
  const screenButton = dialog.getByRole("button", { name: new RegExp(`^${screen} `) });
  await screenButton.click();
  assert.equal(await screenButton.getAttribute("aria-pressed"), "true");
  const stateButton = dialog.getByRole("button", { name: new RegExp(`^${states[state]} `) });
  await stateButton.click();
  assert.equal(await stateButton.getAttribute("aria-pressed"), "true");
  const scaleButton = dialog.getByRole("button", { name: new RegExp(`^Desktop ${scale}% `) });
  await scaleButton.click();
  assert.equal(await scaleButton.getAttribute("aria-pressed"), "true");
  await dialog.getByLabel("Pilot status fixture", { exact: true }).selectOption(status);
  await dialog.getByRole("button", { name: "Apply desktop preview", exact: true }).click();
  await tab.playwright.locator(`.app-shell[data-screen-id="${screen}"][data-fixture-state="${state}"][data-fixture-viewport="desktop-${scale}"]`).waitFor({ state: "visible" });
  assert.equal(await dialog.isVisible(), false);
}

export async function observe(tab) {
  return tab.playwright.evaluate(() => {
    const normalize = text => (text ?? "").replace(/\s+/g, " ").trim();
    const rect = element => {
      if (!element) return null;
      const r = element.getBoundingClientRect();
      return { x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom };
    };
    const rendered = element => {
      const style = getComputedStyle(element);
      const r = element.getBoundingClientRect();
      return !!r.width && !!r.height && style.visibility !== "hidden" && style.display !== "none" && !element.closest('[aria-hidden="true"], [hidden], [inert]');
    };
    const readableText = el => el.nodeType === 3 ? el.textContent : el.getAttribute?.("aria-hidden") === "true" ? "" : [...el.childNodes].map(readableText).join(" ");
    const name = el => normalize(el.getAttribute("aria-label") || (el.getAttribute("aria-labelledby") ?? "").split(/\s+/).map(id => document.getElementById(id)?.textContent ?? "").join(" ") || readableText(el));
    const intent = el => {
      if (el.matches('a.skip-link[href="#main-content"]')) return "skip";
      if (el.matches('.pilot-fact, .career-menu button, .selector-reference-options button')) return "select-career";
      if (el.matches('.sidebar nav button, .system-status-trigger, .back-to-log, .dossier-context-links button')) return "navigate";
      if (el.matches('.mission-inline-link, .roster-profile-link, .mission-row, .aircrew-row, .diary-mission-link, .open-report')) return "open-record";
      if (el.matches('.mission-filters button, .squadron-filters button, .diary-filters button, .reports-filters button, .system-filters button')) return "filter";
      if (el.matches('.fixture-trigger, .fixture-panel button, .fixture-panel select, .overlay-dismiss')) return "preview-fixture";
      if (el.matches('.fixture-state-actions button')) return ({ "Select career": "select-career", "View data status": "navigate", "Retry view": "request-snapshot", "Refresh snapshot": "request-snapshot" })[name(el)] ?? "unknown";
      return "unknown";
    };
    const controlElements = [...document.querySelectorAll('button, a[href], input, select, textarea, [role="button"], [role="link"], [role="menuitem"], [contenteditable="true"]')].filter(rendered);
    const controls = controlElements.map(el => ({
      tag: el.tagName.toLowerCase(), role: el.getAttribute("role") || (el.tagName === "A" ? "link" : el.tagName === "SELECT" ? "combobox" : el.tagName === "BUTTON" ? "button" : "input"),
      name: name(el), intent: intent(el), rect: rect(el), tabIndex: el.tabIndex,
      disabled: !!el.disabled, primary: el.matches('[data-primary="true"], .pilot-fact, .sidebar nav button'),
      href: el.getAttribute("href"), inMain: !!el.closest("main"),
    }));
    const shell = document.querySelector(".app-shell");
    const main = document.querySelector("main");
    const stats = document.querySelector(".dossier-stats");
    const side = rect(document.querySelector(".dossier-side"));
    const ledger = rect(document.querySelector(".service-ledger"));
    const fonts = [...document.querySelectorAll(".app-shell *")].filter(rendered).filter(el => [...el.childNodes].some(n => n.nodeType === 3 && normalize(n.textContent))).map(el => ({ text: normalize(el.textContent).slice(0, 140), size: Number.parseFloat(getComputedStyle(el).fontSize) }));
    return {
      screen: shell.getAttribute("data-screen-id"), state: shell.getAttribute("data-fixture-state"), profile: shell.getAttribute("data-fixture-viewport"),
      viewport: { width: document.documentElement.clientWidth, height: window.innerHeight },
      canvas: rect(document.querySelector(".desktop-preview")), rail: rect(document.querySelector(".sidebar")),
      shell: { clientWidth: shell.clientWidth, scrollWidth: shell.scrollWidth }, main: { clientWidth: main.clientWidth, scrollWidth: main.scrollWidth },
      statsColumns: stats ? getComputedStyle(stats).gridTemplateColumns.trim().split(/\s+/).length : null,
      sideAfterLedger: side && ledger ? side.y >= ledger.bottom - 1 : null,
      heading: document.querySelector("h1")?.textContent, headingFocused: document.activeElement === document.querySelector("h1"), headingTabIndex: document.querySelector("h1")?.tabIndex,
      mainText: normalize(main.innerText), headerText: normalize(document.querySelector("header").innerText),
      fields: [...document.querySelectorAll(".dossier-stats > div")].map(el => ({ label: el.querySelector("span")?.textContent, display: el.querySelector("strong")?.textContent, state: el.getAttribute("data-state"), note: el.querySelector("small")?.textContent })),
      status: document.querySelector(".pilot-status") ? { input: document.querySelector(".pilot-status").getAttribute("data-status-input"), visible: normalize(readableText(document.querySelector(".pilot-status em"))), displayText: normalize(document.querySelector(".pilot-status em").innerText).replace(/^[✓!?—◷]\s*/, ""), accessible: document.querySelector(".pilot-status em").getAttribute("aria-label"), notice: normalize(document.querySelector(".status-mapping-notice")?.textContent) } : null,
      counts: { events: document.querySelectorAll(".service-ledger .ledger-list > div").length, victories: document.querySelectorAll(".dossier-side .victory-list > div").length, emptyCollections: document.querySelectorAll("main .legitimate-empty").length, unknownCollections: document.querySelectorAll("main .collection-unavailable").length, busy: document.querySelectorAll('main [aria-busy="true"]').length },
      fonts: { measured: fonts.length, minimum: Math.min(...fonts.map(f => f.size)), failures: fonts.filter(f => f.size < 12) }, controls,
    };
  });
}

export function assertSurface(sample, { requireHeadingFocus = true } = {}) {
  assert.ok(screens.includes(sample.screen));
  assert.ok(sample.state in states);
  assert.ok(sample.controls.length >= 10, "shell controls must actually be rendered");
  assert.equal(sample.headingTabIndex, -1);
  if (requireHeadingFocus) assert.equal(sample.headingFocused, true, `${sample.screen}: h1 focus`);
  assert.equal(sample.shell.scrollWidth, sample.shell.clientWidth, `${sample.screen}: shell overflow`);
  assert.equal(sample.main.scrollWidth, sample.main.clientWidth, `${sample.screen}: main overflow`);
  assert.ok(sample.fonts.measured > 0);
  assert.ok(sample.fonts.minimum >= 12, "measured minimum type size");
  sameValues(sample.fonts.failures, []);
  for (const control of sample.controls) {
    assert.notEqual(control.intent, "unknown", `Unreviewed control: ${control.name}`);
    assert.ok(control.name, "unnamed control");
    assert.doesNotMatch(control.name, /\b(?:create|edit|delete|save|import|export|repair|reset|launch|regenerate|generate|start session|stop session|confirm claim)\b/i, `Prohibited action: ${control.name}`);
    assert.ok(control.rect.width >= 32, `Narrow target: ${control.name}`);
    assert.ok(control.rect.height >= (control.primary ? 40 : 32), `Short target: ${control.name} (${control.rect.height})`);
  }
}

export function assertViewport(sample, scale) {
  const [width, height, rail] = profiles[scale];
  assert.equal(sample.profile, `desktop-${scale}`);
  assert.ok(Math.abs(sample.canvas.width - Math.min(width, sample.viewport.width)) <= 1, "profile must change the actual canvas width");
  assert.ok(Math.abs(sample.canvas.height - Math.min(height, sample.viewport.height)) <= 1, "profile must change the actual canvas height");
  assert.equal(sample.rail.width, rail);
}

export function assertScale(sample, scale) {
  assertViewport(sample, scale);
  assert.equal(sample.statsColumns, scale === 100 ? 6 : scale === 200 ? 2 : 3);
  assert.equal(sample.sideAfterLedger, scale !== 100);
}

export function assertState(sample, state) {
  assert.equal(sample.state, state);
  const mainActions = sample.controls.filter(c => c.inMain).map(c => c.name);
  assert.doesNotMatch(sample.mainText, /(?:[A-Z]:\\|\/Users\/|\/home\/|Traceback|SELECT\s+\*\s+FROM|password\s*=|api_key\s*=)/i);
  if (["loading", "no-career", "missing", "truncated", "unsupported", "unreadable", "error", "unavailable"].includes(state)) {
    sameValues(sample.fields, []);
    assert.equal(sample.counts.events, 0);
    assert.equal(sample.counts.victories, 0);
    assert.equal(sample.counts.emptyCollections, 0, "unavailable is not a valid empty collection");
    assert.doesNotMatch(sample.mainText, /Balloon Defense|Observation balloon|Sopwith Camel|Albatros/);
  } else assert.equal(sample.fields.length, 6);
  if (state === "loading") { assert.equal(sample.counts.busy, 1); sameValues(mainActions, []); }
  if (state === "complete") sameValues(sample.fields.map(f => f.display), ["27", "46.3 h", "8", "11", "73", "61"]);
  if (state === "empty") {
    assert.match(sample.mainText, /read successfully.*validly empty/i);
    assert.equal(sample.counts.events, 0); assert.equal(sample.counts.victories, 0);
    assert.equal(sample.fields[0].display, "27", "empty collection must not zero unrelated totals");
  }
  if (state === "zeroes") for (const field of sample.fields) { assert.equal(field.state, "zero"); assert.match(field.display, /^0(?:\.0 h)?$/); }
  if (state === "unknown") { for (const field of sample.fields) { assert.equal(field.state, "unknown"); assert.equal(field.display, "Unknown"); } assert.equal(sample.counts.unknownCollections, 1); }
  if (state === "partial") { sameValues(sample.fields.map(f => f.state), ["known", "unavailable", "known", "unknown", "invalid", "unavailable"]); assert.match(sample.mainText, /Partial|PARTIAL/); }
  if (state === "no-career") { assert.match(sample.headerText, /No career selected/); assert.doesNotMatch(sample.headerText, /Arthur Bennett|14 Squadron|RFC-14A/); sameValues(mainActions, ["Select career"]); }
  if (state === "missing") assert.match(sample.mainText, /Pilot Dossier source/);
  if (state === "truncated") assert.match(sample.mainText, /unvalidated values stay hidden/);
  if (state === "unsupported") assert.match(sample.mainText, /not recognized/);
  if (state === "unreadable") assert.match(sample.mainText, /could not be read/);
  if (state === "error") sameValues(mainActions, ["Retry view", "View data status"]);
  if (state === "stale") {
    assert.match(sample.mainText, /14 AUG 1917 · 23:41/);
    assert.match(sample.mainText, /not current data/);
    assert.equal(sample.fields[0].display, "27");
    assert.ok(mainActions.includes("Refresh snapshot"));
  }
  if (["partial", "missing", "truncated", "unsupported", "unreadable", "error", "stale", "unknown", "unavailable"].includes(state)) assert.equal(mainActions.at(-1), "View data status");
}

export function assertStatus(sample, fixture) {
  const label = statusCases.find(([id]) => id === fixture)?.[1];
  assert.ok(label, `Unknown status fixture: ${fixture}`);
  assert.ok(sample.status, "Pilot status must actually be rendered");
  assert.equal(sample.status.visible, label);
  assert.equal(sample.status.accessible, label);
  assert.equal(sample.status.displayText.toLowerCase(), label.toLowerCase());
  assert.equal(!!sample.status.notice, fixture === "future");
  if (fixture === "future") assert.match(sample.status.notice, /Unsupported status mapping.*authoritative value retained/);
}

export function assertTabSequence(sample, stops) {
  const expected = sample.controls.filter(c => c.tabIndex >= 0 && !c.disabled).map(c => c.name);
  sameValues(stops.map(s => s.name), expected, "Tab must traverse all controls in reading order");
  assert.equal(stops[0].name, "Skip to main content");
  assert.match(stops[1].name, /^(Change|Select) active career$/);
  sameValues(stops.slice(2, 8).map(s => s.name), ["Operations", "Pilot Dossier", "Missions", "Squadron", "War Diary", "Reports"]);
  assert.equal(stops[8].name, "Data & System Status Mixed health");
  assert.match(stops[9].name, /^Fixture matrix/);
  const returns = { "MIS-02": "← Return to Mission Log", "SQD-02": "← Return to Squadron Roster", "RPT-02": "← Return to Reports Library", "DOS-02": "← Return to Pilot Dossier", "DOS-03": "← Return to Pilot Dossier", "DOS-04": "← Return to Pilot Dossier" };
  if (sample.state === "complete" && returns[sample.screen]) assert.equal(stops[10].name, returns[sample.screen], "Contextual return must be the first main stop");
  if (sample.screen === "DOS-01" && sample.state === "complete") sameValues(stops.slice(10).map(s => s.name), ["Open Career Record", "Open Victories & Claims", "Open Decorations"]);
  for (const stop of stops) { assert.equal(stop.visibleFocus, true, stop.name); assert.equal(stop.inViewport, true, stop.name); assert.match(stop.boxShadow, /3px.*6px/); assert.notEqual(stop.tag, "h1"); }
}

export async function tabSequence(tab) {
  const sample = await observe(tab);
  const expected = sample.controls.filter(c => c.tabIndex >= 0 && !c.disabled).map(c => c.name);
  await tab.playwright.getByRole("button", { name: /^(Change|Select) active career$/ }).press("Shift+Tab");
  const stops = [];
  for (let i = 0; i < expected.length; i++) {
    const stop = await tab.playwright.evaluate(() => {
      const el = document.activeElement;
      const r = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const readableText = node => node.nodeType === 3 ? node.textContent : node.getAttribute?.("aria-hidden") === "true" ? "" : [...node.childNodes].map(readableText).join(" ");
      return { name: (el.getAttribute("aria-label") || readableText(el)).replace(/\s+/g, " ").trim(), tag: el.tagName.toLowerCase(), visibleFocus: el.matches(":focus-visible"), boxShadow: style.boxShadow, inViewport: r.right > 0 && r.bottom > 0 && r.left < window.innerWidth && r.top < window.innerHeight };
    });
    stops.push(stop);
    if (i < expected.length - 1) await tab.cua.keypress({ keys: ["TAB"] });
  }
  assertTabSequence(sample, stops);
  return { expected, stops };
}

export async function exerciseStateActions(tab) {
  const results = [];
  for (const [state, action] of [["error", "Retry view"], ["stale", "Refresh snapshot"]]) {
    await selectFixture(tab, { state });
    const before = await observe(tab);
    await tab.playwright.getByRole("button", { name: action, exact: true }).click();
    const loading = await observe(tab);
    assertState(loading, "loading");
    await tab.playwright.locator('.app-shell[data-fixture-state="complete"]').waitFor({ state: "visible" });
    const after = await observe(tab);
    assertState(after, "complete");
    assert.equal(after.screen, before.screen);
    assert.match(before.headerText, /Arthur Bennett/);
    assert.match(after.headerText, /RFC-14A-08F2/);
    assert.match(after.headerText, /Arthur Bennett/);
    results.push({ action, before, loading, after });
  }
  await selectFixture(tab, { state: "missing" });
  const missing = await observe(tab);
  await tab.playwright.getByRole("button", { name: "View data status", exact: true }).click();
  const system = await observe(tab);
  assertSurface(system);
  assert.equal(system.screen, "SYS-01");
  assert.equal(system.state, "complete");
  results.push({ action: "View data status", before: missing, after: system });
  await selectFixture(tab, { state: "no-career" });
  const unselected = await observe(tab);
  await tab.playwright.getByRole("button", { name: "Select career", exact: true }).click();
  const selected = tab.playwright.getByRole("option", { name: /WoFF Pilot 1.*RFC-14A-08F2/ });
  await selected.waitFor({ state: "visible" });
  await selected.press("Enter");
  const recovered = await observe(tab);
  assertState(recovered, "complete");
  assert.match(recovered.headerText, /RFC-14A-08F2/);
  results.push({ action: "Select career", before: unselected, after: recovered });
  return results;
}

export async function exerciseDialog(tab) {
  await selectFixture(tab, { scale: 200 });
  await tab.playwright.getByRole("button", { name: /^Fixture matrix/ }).press("Enter");
  const dialog = tab.playwright.getByRole("dialog", { name: "Desktop fixture matrix" });
  await dialog.waitFor({ state: "visible" });
  const state = await tab.playwright.evaluate(() => ({
    first: document.querySelector(".fixture-panel button").textContent,
    focus: document.activeElement.textContent,
    controls: [...document.querySelectorAll(".fixture-panel button,.fixture-panel select")].map(el => ({ tag: el.tagName.toLowerCase(), name: el.getAttribute("aria-label") || el.textContent, width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height })),
  }));
  assert.equal(state.focus, state.first);
  for (const control of state.controls) { assert.ok(control.width >= 32, control.name); assert.ok(control.height >= 40, control.name); }
  await dialog.getByRole("button", { name: /^APP-00 / }).press("Shift+Tab");
  const backward = await tab.playwright.evaluate(() => document.activeElement.textContent);
  assert.equal(backward, "Apply desktop preview");
  await dialog.getByRole("button", { name: "Apply desktop preview", exact: true }).press("Tab");
  const forward = await tab.playwright.evaluate(() => document.activeElement.textContent);
  assert.equal(forward, state.first);
  const stops = [];
  for (let i = 0; i < state.controls.length; i++) {
    stops.push(await tab.playwright.evaluate(() => ({
      name: document.activeElement.getAttribute("aria-label") || document.activeElement.textContent,
      visibleFocus: document.activeElement.matches(":focus-visible"),
      boxShadow: getComputedStyle(document.activeElement).boxShadow,
    })));
    if (i < state.controls.length - 1) await tab.cua.keypress({ keys: ["TAB"] });
  }
  sameValues(stops.map(s => s.name), state.controls.map(c => c.name));
  for (const stop of stops) { assert.equal(stop.visibleFocus, true, stop.name); assert.match(stop.boxShadow, /3px.*6px/); }
  await dialog.getByLabel("Pilot status fixture", { exact: true }).press("Tab");
  const nextToStatus = await tab.playwright.evaluate(() => document.activeElement.textContent);
  assert.equal(nextToStatus, "Cancel");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).press("Shift+Tab");
  const statusFocus = await tab.playwright.evaluate(() => ({ label: document.activeElement.getAttribute("aria-label"), visible: document.activeElement.matches(":focus-visible"), shadow: getComputedStyle(document.activeElement).boxShadow }));
  assert.equal(statusFocus.label, "Pilot status fixture");
  assert.equal(statusFocus.visible, true);
  assert.match(statusFocus.shadow, /3px.*6px/);
  await dialog.getByLabel("Pilot status fixture", { exact: true }).press("Escape");
  assert.equal(await dialog.isVisible(), false);
  const restored = await tab.playwright.evaluate(() => document.activeElement.textContent.trim());
  assert.match(restored, /^Fixture matrix/);
  return { ...state, stops, backward, forward, nextToStatus, statusFocus, restored };
}

export async function exerciseCareerIsolation(tab) {
  const choose = async reference => {
    await tab.playwright.getByRole("button", { name: /^(Change|Select) active career$/ }).press("Enter");
    await tab.playwright.getByRole("option", { name: new RegExp(reference) }).click();
    await tab.playwright.locator(".board-header").getByText(new RegExp(reference)).waitFor({ state: "visible" });
  };
  const contexts = [];
  for (const [screen, nav, record, oldReference] of [
    ["MIS-02", "Missions", "Open report for Line Patrol, 15 AUG 1917", "MIS-1917-08-15-027"],
    ["SQD-02", "Squadron", "Open aircrew profile for Capt. Edward Collins", "RFC-14-A-002"],
    ["RPT-02", "Reports", "Open field report", "RPT-RFC14A-19170815-CAREER"],
  ]) {
    await selectFixture(tab, { screen: "OPR-01" });
    await choose("RFC-14A-08F2");
    await tab.playwright.getByRole("button", { name: nav, exact: true }).click();
    await tab.playwright.getByRole("button", { name: record, exact: true }).first().click();
    const before = await observe(tab);
    assert.equal(before.screen, screen);
    assert.ok(`${before.headerText} ${before.mainText}`.includes(oldReference));
    await choose("RAF-41B-22C1");
    const after = await observe(tab);
    assertSurface(after);
    assert.equal(after.screen, "OPR-01");
    assert.match(after.mainText, /41 Squadron.*RAF/);
    assert.match(after.mainText, /Bertangles/);
    assert.match(after.mainText, /WoFF Pilot 2/);
    assert.ok(!`${after.headerText} ${after.mainText}`.includes(oldReference));
    await selectFixture(tab, { screen });
    const reopened = await observe(tab);
    assert.ok(!`${reopened.headerText} ${reopened.mainText}`.includes(oldReference));
    assert.doesNotMatch(reopened.mainText, /14 Squadron|Bailleul|RFC-14A/);
    contexts.push({ screen, oldReference, before, after, reopened });
  }
  await selectFixture(tab, { screen: "SEL-01" });
  const sparse = await observe(tab);
  const options = sparse.controls.filter(control => control.inMain);
  assert.equal(options.length, 2);
  assert.match(options[0].name, /WoFF Pilot 2.*RAF-41B-22C1/);
  assert.match(options[1].name, /WoFF Pilot 3.*CAREER-14B8/);
  for (const option of options) assert.doesNotMatch(option.name, /WoFF Pilot 1/);
  await selectFixture(tab, { screen: "OPR-01" });
  await choose("RFC-14A-08F2");
  return { contexts, sparse };
}

// Small deterministic cases can run in bounded batches in a supervised
// browser session. Every recorded row is preceded by observable interactions
// and assertions; no producer emits a hard-coded "passed" field.
export const acceptanceCases = [
  ...Object.keys(profiles).flatMap(scale => screens.map(screen => ({ kind: "surface", screen, scale: Number(scale) }))),
  ...Object.keys(states).map(state => ({ kind: "state", state })),
  ...statusCases.map(([status]) => ({ kind: "status", status })),
  ...screens.map(screen => ({ kind: "keyboard", screen, scale: 200 })),
  ...Object.keys(states).filter(state => state !== "complete").map(state => ({ kind: "keyboard", screen: "DOS-01", state, scale: 200 })),
  { kind: "actions" }, { kind: "dialog" }, { kind: "isolation" },
];

export async function runAcceptanceCase(tab, spec) {
  if (spec.kind === "actions") return exerciseStateActions(tab);
  if (spec.kind === "dialog") return exerciseDialog(tab);
  if (spec.kind === "isolation") return exerciseCareerIsolation(tab);
  await selectFixture(tab, spec);
  const sample = await observe(tab);
  assertSurface(sample);
  assertViewport(sample, spec.scale ?? 100);
  if (spec.kind === "keyboard") {
    if (spec.state) assertState(sample, spec.state);
    return { screen: sample.screen, state: sample.state, profile: sample.profile, ...await tabSequence(tab) };
  }
  if (spec.kind === "state") assertState(sample, spec.state);
  if (spec.kind === "status") { assertStatus(sample, spec.status); return { case: spec.status, ...sample }; }
  if (spec.kind === "surface" && spec.screen === "DOS-01") assertScale(sample, spec.scale);
  return sample;
}
