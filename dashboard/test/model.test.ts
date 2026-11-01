import { describe, expect, it } from "vitest";
import type { AuditBlock, Manifest } from "../src/contract/types.ts";
import { checkCompatibility, parseVersion } from "../src/contract/version.ts";
import { Catalog } from "../src/model/catalog.ts";
import { distributionView, finalPointLabel } from "../src/model/distribution.ts";
import { NULL_TEXT, formatValue, isUnavailable } from "../src/model/format.ts";
import { auditView, gitView } from "../src/model/quality.ts";
import { A3_CATEGORIES, A3_CATEGORY_NAMES, MODE_NAMES, ROLE_NAMES, SCENARIO_NAMES, findScenario } from "../src/model/scenarios.ts";
import { routeFromHash } from "../src/router.ts";
import { makeDocs } from "./fixtures/bundle.ts";

describe("format: null is never zero", () => {
  it("shows null as unavailable and zero as a number", () => {
    expect(formatValue(null, "%")).toBe(NULL_TEXT);
    expect(formatValue(undefined, "minutes")).toBe(NULL_TEXT);
    expect(formatValue(0, "%")).toBe("0 %");
    expect(formatValue(0, "residents")).toBe("0 residents");
    expect(formatValue(0, "%")).not.toBe(formatValue(null, "%"));
    expect(isUnavailable(0)).toBe(false);
    expect(isUnavailable(null)).toBe(true);
  });
  it("never rounds finer than the source and never hides a small non-zero share", () => {
    expect(formatValue(0.02, "%")).toBe("0.02 %");
    expect(formatValue(448855.8, "residents")).toBe("448,855.8 residents");
    expect(formatValue(27.95, "minutes")).toBe("27.95 min");
  });
});

describe("distribution view (§7.2)", () => {
  const d = makeDocs().city["walk_distribution"][0];
  const v = distributionView(d, 60);
  it("keeps the open > 60 min bar with its population", () => {
    expect(v.bars).toHaveLength(61);
    expect(v.bars.at(-1)).toEqual({ label: "> 60", lowerMin: 60, upperMin: null, pop: 2, open: true });
    expect(v.bars[0]!.label).toBe("0–1");
    expect(v.popOpenBin).toBe(2);
  });
  it("keeps the final cumulative point (incl. > 60 min) and never extends the curve to 100 %", () => {
    expect(v.cumulative).toHaveLength(60);
    expect(v.cumulative.at(-1)).toEqual({ minutes: 60, pct: 25 });
    expect(v.final).toEqual({ label: finalPointLabel(60), pct: 75 });
    expect(v.final.label).toBe("all citywide times (incl. > 60 min)");
    expect([...v.cumulative.map((c) => c.pct), v.final.pct]).not.toContain(100);
    expect(v.popWithTime).toBe(3);
    expect(v.popTotal).toBe(4);
  });
  it("refuses a distribution without the open bin or the final point", () => {
    const noFinal = { ...d, cumulative: d.cumulative.slice(0, 60) };
    expect(() => distributionView(noFinal, 60)).toThrow(/final cumulative point/);
    const noOpen = { ...d, bins: d.bins.slice(0, 60) };
    expect(() => distributionView(noOpen, 60)).toThrow(/open final bin/);
  });
});

const audit = (a: Partial<AuditBlock>): AuditBlock => ({
  status: "obtained", ran_utc: null, implementation: "x", outcome: "pass", counts: { pass: 1, warn: 0, fail: 0, info: 0 },
  findings: [], reason: null, ...a,
}); // prettier-ignore

describe("audit and Git display states", () => {
  it("never shows a skipped audit as a pass", () => {
    const skipped = auditView(audit({ status: "not_run", outcome: null, counts: null, reason: "skipped" }));
    const passed = auditView(audit({}));
    expect(passed).toMatchObject({ state: "passed", isPass: true });
    expect(skipped).toMatchObject({ state: "not_run", isPass: false });
    expect(skipped.label).not.toMatch(/pass/i);
  });
  it("shows warnings as not a clean pass and lists them", () => {
    const f = { section: "s", check: "c", status: "WARN" as const, detail: "d", action: "" };
    const v = auditView(audit({ outcome: "warn", counts: { pass: 1, warn: 1, fail: 0, info: 0 }, findings: [f] }));
    expect(v).toMatchObject({ state: "passed_with_warnings", isPass: false });
    expect(v.warnings).toEqual([f]);
  });
  it("tells a dirty tree from an unknown one", () => {
    const base: Manifest["code"] = { git_commit: "5ed16d2e92", git_working_tree_clean: false, git_dirty_count: 8, git_dirty_paths: [], abot_version: "0.1.0" };
    expect(gitView(base)).toMatchObject({ state: "dirty" });
    expect(gitView(base).label).toMatch(/8 uncommitted change/);
    const unknown = gitView({ ...base, git_working_tree_clean: null, git_commit: null, git_dirty_count: null });
    expect(unknown.state).toBe("unknown");
    expect(unknown.label).not.toMatch(/clean|uncommitted/);
    expect(gitView({ ...base, git_working_tree_clean: true, git_dirty_count: 0 }).state).toBe("clean");
    expect(gitView({ ...base, git_working_tree_clean: true, git_commit: null }).state).toBe("unknown");
  });
});

describe("catalogue and statements", () => {
  const m = makeDocs().manifest as unknown as Manifest;
  const cat = new Catalog(m);
  it("takes caveat texts from manifest.statements, exactly as written", () => {
    expect(cat.statement("DQ-A1-OPT")).toBe("Fixture text of DQ-A1-OPT (2 of 3 pending).");
    expect(cat.statementsFor("A1.walk.g1.pct_le10").map((s) => s.code)).toEqual(["DQ-SHARE-ALL", "DQ-A1-OPT"]);
    expect(() => cat.statement("DQ-NOPE")).toThrow();
    expect(() => cat.require("A3.walk.g1.pct_le99")).toThrow();
  });
  it("keeps levels and denominators from the catalogue", () => {
    expect(cat.idsAt("barangay")).not.toContain("A3.walk.g1.local_internal_pop_le10");
    expect(cat.describes("A3.walk.g1.pct_le10")).toBe("all residents");
  });
});

describe("names never claim more than the methodology", () => {
  const names = [...Object.values(ROLE_NAMES), ...Object.values(A3_CATEGORY_NAMES), ...Object.values(MODE_NAMES), ...Object.values(SCENARIO_NAMES)];
  it("does not describe A1 as observed or as an upper bound, and does not retype caveats", () => {
    for (const n of names) expect(n).not.toMatch(/observed|upper bound|guarantee|optimistic|not an? /i);
  });
  it("keeps the four A3 categories separate and driving a separate mode", () => {
    expect(A3_CATEGORIES).toEqual(["network_connected", "locally_connected", "access_uncertain", "unconnected"]);
    expect(new Set(A3_CATEGORIES.map((c) => A3_CATEGORY_NAMES[c])).size).toBe(4);
    expect(MODE_NAMES.drive).toMatch(/separate mode/);
    expect(SCENARIO_NAMES["A2:walk"]).toMatch(/supporting evidence/);
  });
  it("takes full scenario labels from the bundle", () => {
    expect(findScenario(makeDocs().manifest as unknown as Manifest, "A1", "drive")!.label).toBe("A1 driving label from the bundle");
  });
});

describe("versions and routes", () => {
  it("parses versions and classifies compatibility", () => {
    expect(parseVersion("1.2.3")).toEqual({ major: 1, minor: 2, patch: 3 });
    expect(parseVersion("1.2")).toBeNull();
    expect(checkCompatibility("abot-dashboard", "1.0.9").status).toBe("compatible");
    expect(checkCompatibility("abot-dashboard", "1.1.0").status).toBe("newer_minor");
    expect(checkCompatibility("abot-dashboard", "0.9.0").status).toBe("incompatible");
  });
  it("reads hash routes with a fallback", () => {
    expect(routeFromHash("#/status", ["status", "map"], "status")).toBe("status");
    expect(routeFromHash("#/map?x=1", ["status", "map"], "status")).toBe("map");
    expect(routeFromHash("#/nope", ["status"], "status")).toBe("status");
    expect(routeFromHash("", ["status"], "status")).toBe("status");
  });
});
