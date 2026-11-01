/**
 * Data Quality (#/quality): audit result and its warnings, known issues, source validation, per-file
 * integrity, reliability across barangays (table and a small patterned map), the statements and the
 * pipeline QA checks. A skipped audit is never shown as passed.
 */
import { guard, Unavailable } from "../components/states/States.tsx";
import { Badge, PageHeader, Panel, Rel } from "../components/ui.tsx";
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
        <div className="counts" style={{ marginBottom: "var(--space-4)" }}>
          {(
            [
              [c.pass, "✓ pass", "ok"],
              [c.warn, "! warn", "warn"],
              [c.fail, "✕ fail", c.fail > 0 ? "error" : "unknown"],
              [c.info, "i info", "info"],
            ] as const
          ).map(([n, l, t]) => (
            <div key={l} className={`count-box badge--${t}`} style={{ borderRadius: "var(--radius-sm)" }}>
              <b>{n}</b>
              <span>{l}</span>
            </div>
          ))}
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
        <ul className="statement-list">
          {b.manifest.known_issues.map((k) => (
            <li key={k.code} style={{ gridTemplateColumns: "8rem minmax(0,1fr)" }}>
              <span>
                <Badge tone="warn">{k.code}</Badge>
              </span>
              <span>
                {k.text}
                <span className="small muted" style={{ display: "block" }}>
                  affects: {k.affects.join(", ")}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function validation(b: LoadedBundle) {
  const v = b.manifest.data_quality.source_validation;
  const items: [string, boolean][] = [
    ["A1 reproduces the baseline", v.a1_reproduces_baseline],
    ["Baseline outputs unchanged", v.baseline_outputs_unchanged],
    ["Baseline hashes match the files on disk", v.baseline_hashes_match_disk],
    [`Component classes identical (${v.component_classes_check.components_compared} compared)`, v.component_classes_check.identical],
  ];
  return (
    <Panel id="val" title="Source validation">
      <ul className="rel-list">
        {items.map(([l, ok]) => (
          <li key={l} style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}>
            <span>{l}</span>
            {ok ? <Badge tone="ok">Yes</Badge> : <Badge tone="error">No</Badge>}
          </li>
        ))}
      </ul>
      <p className="small muted" style={{ margin: "var(--space-3) 0 0" }}>
        Reference: <code style={{ overflowWrap: "anywhere" }}>{v.component_classes_check.reference ?? "none"}</code>
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
  const fill: Record<string, string> = { ok: "url(#p-ok)", caution: "url(#p-caution)", low: "url(#p-low)" };
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
                <defs>
                  <pattern id="p-ok" width="6" height="6" patternUnits="userSpaceOnUse">
                    <rect width="6" height="6" fill="#e7f4ec" />
                  </pattern>
                  <pattern id="p-caution" width="5" height="5" patternUnits="userSpaceOnUse">
                    <rect width="5" height="5" fill="#fff4dc" />
                    <circle cx="2.5" cy="2.5" r="1" fill="#b8892c" />
                  </pattern>
                  <pattern id="p-low" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <rect width="5" height="5" fill="#fdecee" />
                    <line x1="0" y1="0" x2="0" y2="5" stroke="#a1121f" strokeWidth="1.6" />
                  </pattern>
                </defs>
                {list.map((x) => {
                  const lvl = relOf(x.rec, "overall").level;
                  const d = svg.paths.get(x.code);
                  return d ? (
                    <path key={x.code} d={d} fill={fill[lvl] ?? "#eef1f1"} stroke="#7d8789" strokeWidth="0.4">
                      <title>{`${x.name}: overall ${lvl}`}</title>
                    </path>
                  ) : null;
                })}
              </svg>
              <div className="legend-inline" style={{ marginTop: "var(--space-2)" }}>
                <span className="legend-inline__item">
                  <span className="legend__sw" style={{ background: "#e7f4ec" }} />✓ OK
                </span>
                <span className="legend-inline__item">
                  <span className="legend__sw" style={{ background: "radial-gradient(#b8892c 1px,#fff4dc 1.2px) 0 0/5px 5px" }} />! Caution (dots)
                </span>
                <span className="legend-inline__item">
                  <span className="legend__sw" style={{ background: "repeating-linear-gradient(45deg,#fdecee 0 2px,#a1121f 2px 3px)" }} />▼ Low (hatched)
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
      <ul className="statement-list">
        {b.manifest.statements.map((s) => (
          <li key={s.code}>
            <span>
              <code>{s.code}</code>
            </span>
            <span>{s.text}</span>
            <span className="small muted">{s.applies_to}</span>
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

export function QualityPage({ bundle }: { bundle: LoadedBundle }) {
  const a = auditView(bundle.manifest.data_quality.source_validation.audit);
  const lead =
    a.state === "passed"
      ? "What was checked, what passed, and what needs review. The audit passed."
      : a.state === "passed_with_warnings"
        ? `What was checked, what passed, and what needs review. The audit passed with warnings; ${bundle.manifest.data_quality.source_validation.audit.counts?.fail ? "some checks failed" : "no check failed"}.`
        : "What was checked, what passed, and what needs review. The audit was not run for this bundle.";
  return (
    <div className="page">
      <PageHeader eyebrow="For researchers" title="Data quality" lead={lead} />
      <div className="grid">
        <div className="span-12">{guard("The dataset status", () => status(bundle))}</div>
      </div>
      <div className="grid">
        <div className="span-8">{guard("The audit result", () => audit(bundle))}</div>
        <div className="span-4">
          {guard("The known issues", () => known(bundle))}
          <div style={{ height: "var(--space-4)" }} />
          {guard("The source validation", () => validation(bundle))}
        </div>
      </div>
      <div className="grid">
        <div className="span-12">{guard("The integrity table", () => integrity(bundle))}</div>
      </div>
      <div className="grid">
        <div className="span-12">{guard("The reliability overview", () => reliability(bundle))}</div>
      </div>
      <div className="grid">
        <div className="span-12">{guard("The facility inventory", () => inventory(bundle))}</div>
      </div>
      <div className="grid">
        <div className="span-12">{guard("The statements", () => statements(bundle))}</div>
      </div>
      <div className="grid">
        <div className="span-12">
          {guard("The QA checks", () => {
            // read here, so a missing part is reported by guard() instead of failing the page
            if (bundle.provenance.status === "ok") void Object.keys(bundle.provenance.data.qa);
            return <QaPanel b={bundle} />;
          })}
        </div>
      </div>
    </div>
  );
}
