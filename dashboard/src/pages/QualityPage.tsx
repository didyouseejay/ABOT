/**
 * Data Quality (#/quality): audit result and its warnings, known issues, source validation, per-file
 * integrity, reliability across barangays (table and a small patterned map), the statements and the
 * pipeline QA checks. A skipped audit is never shown as passed.
 */
import { guard, Unavailable } from "../components/states/States.tsx";
import { Badge, MetricTile, PageHeader, PageSection, PageToc, Panel, PropBar, Rel } from "../components/ui.tsx";
import type { LoadedBundle } from "../data/loadBundle.ts";
import { fixed, formatUtc } from "../model/format.ts";
import { auditView } from "../model/quality.ts";
import { bundleStatusItems, datasetState } from "../model/shell.ts";
import { InventoryTable } from "../components/InventoryTable.tsx";
import type { DatasetKey } from "../routes.ts";
import { barangaysOf, relCounts, relOf, svgPaths } from "../model/values.ts";
import { useView } from "../view.tsx";

const AUDIT_BADGE = { passed: ["ok", "Passed"], passed_with_warnings: ["warn", "Passed with warnings"], not_run: ["warn", "Not run"], invalid: ["error", "Not valid"] } as const;

function audit(b: LoadedBundle) {
  const au = b.manifest.data_quality.source_validation.audit;
  const v = auditView(au);
  const c = au.counts;
  const [tone, text] = AUDIT_BADGE[v.state];
  return (
    <Panel
      id="audit"
      title="Audit result"
      tags={<Badge tone={tone}>{text}</Badge>}
      sub={
        <>
          <code>{au.implementation}</code>
          {au.ran_utc ? ` · ran ${formatUtc(au.ran_utc)}` : ""} · status {au.status}
          {au.reason ? ` · ${au.reason}` : ""}
        </>
      }
    >
      {c && (
        <div className="audit-counts">
          <div className="counts">
            {(
              [
                [c.pass, "✓", "pass", "ok"],
                [c.warn, "!", "warn", "warn"],
                [c.fail, "✕", "fail", c.fail > 0 ? "error" : "unknown"],
                [c.info, "i", "info", "info"],
              ] as const
            ).map(([n, sym, l, t]) => (
              <div key={l} className={`count-box count-box--${t}`}>
                <b>{n}</b>
                <span>
                  <span aria-hidden="true">{sym}</span> {l}
                </span>
              </div>
            ))}
          </div>
          <PropBar
            label="Audit checks in the panel"
            parts={[
              { key: "pass", n: c.pass, cls: "propbar__seg--ok", text: "passed" },
              { key: "warn", n: c.warn, cls: "propbar__seg--warn", text: "warnings" },
              { key: "fail", n: c.fail, cls: "propbar__seg--error", text: "failed" },
              { key: "info", n: c.info, cls: "propbar__seg--info", text: "informational" },
            ]}
          />
        </div>
      )}
      {au.findings.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <caption className="visually-hidden">Audit warnings</caption>
            <thead>
              <tr>
                <th scope="col">Status</th>
                <th scope="col">Section</th>
                <th scope="col">Check</th>
                <th scope="col">Detail</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {au.findings.map((f) => (
                <tr key={`${f.section}.${f.check}`}>
                  <td>
                    <Badge tone="warn">{f.status}</Badge>
                  </td>
                  <td>{f.section}</td>
                  <td>
                    <code>{f.check}</code>
                  </td>
                  <td className="small" style={{ minWidth: "16rem" }}>
                    {f.detail}
                  </td>
                  <td className="small" style={{ minWidth: "14rem" }}>
                    {f.action}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function known(b: LoadedBundle) {
  return (
    <Panel id="known" title="Known issues" sub={<>From <code>manifest.known_issues</code>; also summarised under Dataset status.</>}>
      {b.manifest.known_issues.length === 0 ? (
        <p className="small muted">The bundle lists no known issues.</p>
      ) : (
        <ul className="issue-list">
          {b.manifest.known_issues.map((k) => (
            <li key={k.code} className="issue">
              <Badge tone="warn">{k.code}</Badge>
              <p className="issue__text">{k.text}</p>
              <p className="issue__affects">
                <span className="muted">Affects</span>{" "}
                {k.affects.map((a) => (
                  <code key={a}>{a}</code>
                ))}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

// null = the check was not performed (no reference material): shown as such, never as passed or failed
function validationItems(b: LoadedBundle): [string, boolean | null][] {
  const v = b.manifest.data_quality.source_validation;
  const cc = v.component_classes_check;
  return [
    ["A1 reproduces the baseline", v.a1_reproduces_baseline],
    ["Baseline outputs unchanged", v.baseline_outputs_unchanged],
    ["Baseline hashes match the files on disk", v.baseline_hashes_match_disk],
    [
      cc.status === "not_performed" ? "Component classes identical to the archived reference" : `Component classes identical (${cc.components_compared} compared)`,
      cc.status === "not_performed" ? null : cc.identical,
    ],
  ];
}

function validation(b: LoadedBundle) {
  const cc = b.manifest.data_quality.source_validation.component_classes_check;
  const items = validationItems(b);
  return (
    <Panel id="val" title="Source validation">
      <ul className="rel-list check-list">
        {items.map(([l, ok]) => (
          <li key={l} style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}>
            <span>{l}</span>
            {ok === null ? <Badge tone="warn">Not performed</Badge> : ok ? <Badge tone="ok">Yes</Badge> : <Badge tone="error">No</Badge>}
          </li>
        ))}
      </ul>
      <p className="small muted" style={{ margin: "var(--space-3) 0 0" }}>
        Reference: <code style={{ overflowWrap: "anywhere" }}>{cc.reference ?? "none"}</code>
        {cc.reason ? <> · {cc.reason}</> : null}
      </p>
    </Panel>
  );
}

const DATASET_KEY: Record<string, DatasetKey | null> = { city: "city", barangays: "barangays", barangay_indicators: "indicators", cells: "cells", facilities: "facilities", network: "network", provenance: "provenance", manifest: null };

function integrity(b: LoadedBundle) {
  const verified = b.verification === "verified";
  return (
    <Panel
      id="integ"
      title="Integrity"
      tags={verified ? <Badge tone="ok">Verified</Badge> : <Badge tone="warn">Not verified</Badge>}
      sub="Each file's size and SHA-256 are checked against the manifest before anything is shown. The manifest is the reference and is checked for parse and contract version only."
    >
      <div className="table-wrap">
        <table className="data-table data-table--compact">
          <caption className="visually-hidden">File integrity</caption>
          <thead>
            <tr>
              <th scope="col">File</th>
              <th scope="col">Dataset</th>
              <th scope="col" className="n">
                Bytes
              </th>
              <th scope="col">SHA-256 (manifest)</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {b.manifest.files.map((f) => {
              const k = DATASET_KEY[f.dataset];
              const failed = k ? datasetState(b, k).status === "failed" : false;
              return (
                <tr key={f.name}>
                  <td className="mono">{f.name}</td>
                  <td>{f.dataset}</td>
                  <td className="n">{fixed(f.bytes, 0)}</td>
                  <td className="mono" style={{ fontSize: ".68rem" }} title={f.sha256}>
                    {f.sha256.slice(0, 16)}…
                  </td>
                  <td>{failed ? <Badge tone="error">Dataset failed</Badge> : verified ? <Badge tone="ok">Size + SHA-256 match</Badge> : <Badge tone="warn">Size OK · hash not computed</Badge>}</td>
                </tr>
              );
            })}
            <tr>
              <td className="mono">manifest.json</td>
              <td>manifest</td>
              <td className="n">—</td>
              <td className="mono" style={{ fontSize: ".68rem" }}>
                reference file
              </td>
              <td>
                <Badge tone="info">{`Parsed · v${b.manifest.contract_version}`}</Badge>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function reliability(b: LoadedBundle) {
  const list = barangaysOf(b);
  if (!list) {
    return (
      <Panel id="rel" title="Reliability across barangays">
        <Unavailable bundle={b} dataset="indicators" />
      </Panel>
    );
  }
  const overall = relCounts(list, "overall");
  const nElig = list.filter((x) => x.rec.data_quality.ranking_eligible).length;
  const svg = svgPaths(list, 420);
  // flat fills; lightness rises with severity, and every level is named in the legend and tooltip
  const fill: Record<string, string> = { ok: "#e2e8f0", caution: "#fca5a5", low: "#b91c1c" };
  const allUnverified = list.every((x) => relOf(x.rec, "facility_inventory").level === "unverified");
  return (
    <Panel id="rel" title="Reliability across barangays" sub={`Low reliability excludes a barangay from ranks (${overall.low} low → ${nElig} eligible).`} codes={["DQ-SIMPLIFIED", "DQ-POP-ALLOC"]}>
      <div className="grid" style={{ margin: 0 }}>
        <div className="span-5 table-scroll">
          <table className="data-table data-table--compact">
            <caption className="visually-hidden">Barangays by reliability level</caption>
            <thead>
              <tr>
                <th scope="col">Dimension</th>
                <th scope="col" className="n">
                  <Rel level="ok" />
                </th>
                <th scope="col" className="n">
                  <Rel level="caution" />
                </th>
                <th scope="col" className="n">
                  <Rel level="low" />
                </th>
              </tr>
            </thead>
            <tbody>
              {(
                [
                  ["population", "Population"],
                  ["network", "Network"],
                  ["overall", "Overall"],
                ] as const
              ).map(([k, l]) => {
                const c = relCounts(list, k);
                return (
                  <tr key={k}>
                    <th scope="row" style={{ fontWeight: k === "overall" ? 650 : 400 }}>
                      {l}
                    </th>
                    <td className="n">{c.ok}</td>
                    <td className="n">{c.caution}</td>
                    <td className="n">{c.low}</td>
                  </tr>
                );
              })}
              <tr>
                <th scope="row" style={{ fontWeight: 400 }}>
                  Facility inventory
                </th>
                <td colSpan={3} className="n">
                  {allUnverified ? (
                    <>
                      <Rel level="unverified" /> all {list.length}
                    </>
                  ) : (
                    "mixed"
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="span-7">
          {svg && (
            <>
              <svg viewBox={`0 0 ${svg.w} ${svg.h}`} className="chart" role="img" aria-label={`Map of overall reliability by barangay: ${overall.ok} OK, ${overall.caution} caution, ${overall.low} low`} style={{ maxHeight: "20rem" }}>
                {list.map((x) => {
                  const lvl = relOf(x.rec, "overall").level;
                  const d = svg.paths.get(x.code);
                  return d ? (
                    <path key={x.code} d={d} fill={fill[lvl] ?? "#f8fafc"} stroke="#ffffff" strokeWidth="0.6">
                      <title>{`${x.name}: overall ${lvl}`}</title>
                    </path>
                  ) : null;
                })}
              </svg>
              <div className="legend-inline" style={{ marginTop: "var(--space-2)" }}>
                <span className="legend-inline__item">
                  <span className="legend__sw" style={{ background: "#e2e8f0" }} />✓ OK
                </span>
                <span className="legend-inline__item">
                  <span className="legend__sw" style={{ background: "#fca5a5" }} />! Caution
                </span>
                <span className="legend-inline__item">
                  <span className="legend__sw" style={{ background: "#b91c1c" }} />▼ Low
                </span>
              </div>
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}

function statements(b: LoadedBundle) {
  return (
    <Panel id="stm" title={`The ${b.manifest.statements.length} statements`} sub={<>Texts come from <code>manifest.statements</code> at runtime and are shown verbatim wherever their code appears.</>}>
      <ul className="stmt-grid">
        {b.manifest.statements.map((s) => (
          <li key={s.code} className="stmt">
            <code className="stmt__code">{s.code}</code>
            <p className="stmt__text">{s.text}</p>
            <p className="stmt__applies">{s.applies_to}</p>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function QaPanel({ b }: { b: LoadedBundle }) {
  const { p, set } = useView();
  if (b.provenance.status !== "ok") {
    return (
      <Panel id="qa" title="Pipeline QA checks">
        <Unavailable bundle={b} dataset="provenance" />
      </Panel>
    );
  }
  const q = b.provenance.data.qa;
  const keys = Object.keys(q);
  const cur = keys.includes(p["qa"] ?? "") ? (p["qa"] as string) : (keys[0] ?? "");
  const show = (x: unknown) => (x === null || x === undefined ? "—" : typeof x === "object" ? JSON.stringify(x) : String(x));
  return (
    <Panel id="qa" title="Pipeline QA checks" sub="PASS/WARN = a tested condition; info = reported value.">
      <div className="tabs" role="tablist" aria-label="QA file">
        {keys.map((k, i) => (
          <button
            key={k}
            type="button"
            className="tabs__btn"
            role="tab"
            id={`qa-${k}`}
            aria-selected={k === cur}
            tabIndex={k === cur ? 0 : -1}
            onClick={() => set({ qa: i === 0 ? null : k })}
            onKeyDown={(e) => {
              if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
              const n = keys[(i + (e.key === "ArrowRight" ? 1 : keys.length - 1)) % keys.length] as string;
              set({ qa: n === keys[0] ? null : n });
              setTimeout(() => document.getElementById(`qa-${n}`)?.focus(), 0);
            }}
          >
            {k} <span className="muted">{Object.keys(q[k] ?? {}).length}</span>
          </button>
        ))}
      </div>
      <div className="table-wrap" style={{ maxHeight: "28rem" }} role="tabpanel" aria-labelledby={`qa-${cur}`}>
        <table className="data-table data-table--compact">
          <thead>
            <tr>
              <th scope="col">Check</th>
              <th scope="col">Result</th>
              <th scope="col">Value</th>
              <th scope="col">Note</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(q[cur] ?? {}).map(([k, r]) => (
              <tr key={k}>
                <td>
                  <code>{k}</code>
                </td>
                <td>{r.ok === true ? <Badge tone="ok">PASS</Badge> : r.ok === false ? <Badge tone="warn">WARN</Badge> : <Badge tone="info">info</Badge>}</td>
                <td className="small mono" style={{ maxWidth: "18rem", overflowWrap: "anywhere" }}>
                  {show(r.value)}
                </td>
                <td className="small" style={{ minWidth: "14rem" }}>
                  {r.note ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

/** The bundle facts the old provenance bar showed on every page (moved here in M05.3). */
function status(b: LoadedBundle) {
  return (
    <Panel id="status" title="Dataset status" sub="Read from the bundle; success is shown only for a verified, passed or clean state.">
      <dl className="status-list">
        {bundleStatusItems(b).map((i) => (
          <div key={i.key}>
            <dt>{i.label}</dt>
            <dd>
              <Badge tone={i.tone} title={i.detail}>
                {i.value}
              </Badge>
            </dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function inventory(b: LoadedBundle) {
  return (
    <Panel id="inv" title="Facility inventory per indicator group" sub={`Counts of mapped OpenStreetMap features used for each group's travel times.${b.city.facility_inventory.every((r) => r["registry_reference"] === "none") ? " No group has been matched to an official registry." : ""}`} codes={["DQ-FAC-OSM", "DQ-DUP"]}>
      <InventoryTable city={b.city} deep />
    </Panel>
  );
}

function Scorecard({ b }: { b: LoadedBundle }) {
  const au = b.manifest.data_quality.source_validation.audit;
  const a = auditView(au);
  const [tone, text] = AUDIT_BADGE[a.state];
  const c = au.counts;
  const verified = b.verification === "verified";
  const items = validationItems(b);
  const yes = items.filter(([, ok]) => ok === true).length;
  const vTone = items.some(([, ok]) => ok === false) ? "error" : items.some(([, ok]) => ok === null) ? "warn" : "ok";
  const list = barangaysOf(b);
  const nElig = list ? list.filter((x) => x.rec.data_quality.ranking_eligible).length : null;
  return (
    <div className="metrics metrics--4 scorecard">
      <MetricTile tone={tone} label="Source audit" badge={<Badge tone={tone}>{text}</Badge>} value={c ? `${c.pass} / ${c.pass + c.warn + c.fail + c.info}` : "—"} detail={c ? `checks passed · ${c.warn} warn · ${c.fail} fail · ${c.info} info` : (au.reason ?? "No counts in the bundle")}>
        {c && (
          <PropBar
            label="Audit checks"
            parts={[
              { key: "pass", n: c.pass, cls: "propbar__seg--ok", text: "passed" },
              { key: "warn", n: c.warn, cls: "propbar__seg--warn", text: "warnings" },
              { key: "fail", n: c.fail, cls: "propbar__seg--error", text: "failed" },
              { key: "info", n: c.info, cls: "propbar__seg--info", text: "informational" },
            ]}
          />
        )}
      </MetricTile>
      <MetricTile tone={verified ? "ok" : "warn"} label="File integrity" badge={verified ? <Badge tone="ok">Verified</Badge> : <Badge tone="warn">Not verified</Badge>} value={`${b.manifest.files.length}`} detail={verified ? "data files match the manifest (size + SHA-256)" : "data files size-checked; hashes not computed"} />
      <MetricTile tone={vTone} label="Source validation" value={`${yes} / ${items.length}`} detail={vTone === "ok" ? "checks confirmed" : "checks confirmed; see Checks below"} />
      <MetricTile tone="info" label="Ranking eligibility" value={nElig === null || !list ? "—" : `${nElig} / ${list.length}`} detail="barangays reliable enough to rank">
        {list && nElig !== null && (
          <PropBar
            label="Barangays"
            parts={[
              { key: "e", n: nElig, cls: "propbar__seg--brand", text: "eligible" },
              { key: "n", n: list.length - nElig, cls: "propbar__seg--muted", text: "not ranked" },
            ]}
          />
        )}
      </MetricTile>
    </div>
  );
}

export function QualityPage({ bundle }: { bundle: LoadedBundle }) {
  const a = auditView(bundle.manifest.data_quality.source_validation.audit);
  const lead =
    a.state === "passed"
      ? "What was checked, what passed, and what needs review. The audit passed."
      : a.state === "passed_with_warnings"
        ? `What was checked, what passed, and what needs review. The audit passed with warnings; ${bundle.manifest.data_quality.source_validation.audit.counts?.fail ? "some checks failed" : "no check failed"}.`
        : "What was checked, what passed, and what needs review. The audit was not run for this bundle.";
  return (
    <div className="page page--research">
      <PageHeader eyebrow="For researchers" title="Data quality" lead={lead} />
      <PageToc
        items={[
          ["q-summary", "Summary"],
          ["q-checks", "Checks"],
          ["q-files", "Files"],
          ["q-coverage", "Reliability & inventory"],
          ["q-reference", "Statements & QA"],
        ]}
      />
      <PageSection id="q-summary" title="Summary">
        {guard("The quality summary", () => <Scorecard b={bundle} />)}
        {guard("The dataset status", () => status(bundle))}
      </PageSection>
      <PageSection id="q-checks" title="Checks" lead="The source audit, the comparison with the baseline pipeline, and the issues the bundle declares.">
        <div className="grid">
          <div className="span-8">{guard("The audit result", () => audit(bundle))}</div>
          <div className="span-4">{guard("The source validation", () => validation(bundle))}</div>
        </div>
        {guard("The known issues", () => known(bundle))}
      </PageSection>
      <PageSection id="q-files" title="Files">
        {guard("The integrity table", () => integrity(bundle))}
      </PageSection>
      <PageSection id="q-coverage" title="Reliability and facility inventory">
        <div className="stack">
          {guard("The reliability overview", () => reliability(bundle))}
          {guard("The facility inventory", () => inventory(bundle))}
        </div>
      </PageSection>
      <PageSection id="q-reference" title="Statements and pipeline QA">
        <div className="stack">
          {guard("The statements", () => statements(bundle))}
          {guard("The QA checks", () => {
            // read here, so a missing part is reported by guard() instead of failing the page
            if (bundle.provenance.status === "ok") void Object.keys(bundle.provenance.data.qa);
            return <QaPanel b={bundle} />;
          })}
        </div>
      </PageSection>
    </div>
  );
}
