/**
 * The provenance colophon on every page (dataset, generation time, integrity, audit, code, datasets)
 * and the bundle notices beneath it. Every value is read from the bundle; unknown is never given the
 * tone of success. The notices (known issues and loader conditions) are collapsed behind a count,
 * and open by themselves when a dataset failed.
 */
import type { ReactNode } from "react";
import type { BundleState } from "../../data/BundleContext.tsx";
import type { LoadedBundle } from "../../data/loadBundle.ts";
import { formatUtc } from "../../model/format.ts";
import { auditView, gitView } from "../../model/quality.ts";
import { DATASET_NAMES, failedDatasets, shellStatusItems } from "../../model/shell.ts";
import { Badge, Icon } from "../ui.tsx";
import { NOTICES_ID } from "./ids.ts";

const AUDIT_TEXT = { passed: ["ok", "Passed"], passed_with_warnings: ["warn", "Passed with warnings"], not_run: ["warn", "Not run"], invalid: ["error", "Not valid"] } as const;

/** Number of datasets a complete bundle has: the manifest plus the seven data datasets. */
const DATASET_COUNT = Object.keys(DATASET_NAMES).length + 1;

function items(b: LoadedBundle): [label: string, value: ReactNode, optional?: boolean][] {
  const m = b.manifest;
  const a = auditView(m.data_quality.source_validation.audit);
  const counts = m.data_quality.source_validation.audit.counts;
  const git = gitView(m.code);
  const failed = failedDatasets(b);
  const [aTone, aText] = AUDIT_TEXT[a.state];
  return [
    ["Dataset", <span className="provenance__value">{`${m.contract} v${m.contract_version}`}</span>],
    ["Generated", <span className="provenance__value">{formatUtc(m.generated_utc)}</span>],
    [
      "Integrity",
      b.verification === "verified" ? (
        <Badge tone="ok" title="Every data file matches the size and SHA-256 in the manifest">
          Verified
        </Badge>
      ) : (
        <Badge tone="warn" title="File sizes checked; SHA-256 could not be computed in this context">
          Not verified
        </Badge>
      ),
    ],
    [
      "Audit",
      <Badge tone={aTone} title={counts ? `${counts.pass} pass · ${counts.warn} warn · ${counts.fail} fail · ${counts.info} info` : a.label}>
        {aText}
      </Badge>,
    ],
    [
      "Code",
      <>
        <span className="provenance__value">{git.commit ? git.commit.slice(0, 7) : "unknown"}</span>{" "}
        {git.state === "dirty" && (
          <Badge tone="warn" title={git.label}>
            uncommitted changes
          </Badge>
        )}
        {git.state === "unknown" && (
          <Badge tone="unknown" title={git.label}>
            unknown
          </Badge>
        )}
        {git.state === "clean" && <Badge tone="ok">clean</Badge>}
      </>,
      true,
    ],
    [
      "Datasets",
      failed.length === 0 ? (
        <Badge tone="ok">{`${DATASET_COUNT} of ${DATASET_COUNT} loaded`}</Badge>
      ) : (
        <Badge tone="error" title={`Failed: ${failed.map((k) => DATASET_NAMES[k]).join("; ")}`}>
          {`${DATASET_COUNT - failed.length} of ${DATASET_COUNT} loaded`}
        </Badge>
      ),
    ],
  ];
}

export function noticeCount(b: LoadedBundle): number {
  return b.manifest.known_issues.length + (b.verification === "unavailable" ? 1 : 0) + (b.compatibility.status === "newer_minor" ? 1 : 0) + failedDatasets(b).length;
}

export function ProvenanceBar({ state, noticesOpen, onToggleNotices }: { state: BundleState; noticesOpen: boolean; onToggleNotices: () => void }) {
  if (state.status !== "ready") {
    return (
      <section className="provenance" aria-label="Data provenance and status">
        <div className="provenance__inner">
          <ul className="provenance__list">
            {shellStatusItems(state).map((i) => (
              <li key={i.key} className="provenance__item">
                <span className="provenance__label">{i.label}</span>
                <Badge tone={i.tone}>{i.value}</Badge>
              </li>
            ))}
          </ul>
        </div>
      </section>
    );
  }
  const n = noticeCount(state.bundle);
  return (
    <section className="provenance" aria-label="Data provenance and status">
      <div className="provenance__inner">
        <ul className="provenance__list">
          {items(state.bundle).map(([label, value, opt]) => (
            <li key={label} className={`provenance__item${opt ? " provenance__item--opt" : ""}`}>
              <span className="provenance__label">{label}</span>
              {value}
            </li>
          ))}
          {n > 0 && (
            <li className="provenance__item provenance__notices">
              <button type="button" className="linkbtn" aria-expanded={noticesOpen} aria-controls={NOTICES_ID} onClick={onToggleNotices}>
                <Icon name="info" />
                {n} bundle notice{n === 1 ? "" : "s"}
              </button>
            </li>
          )}
        </ul>
      </div>
    </section>
  );
}

/** Known issues (manifest.known_issues) and loader conditions; collapsed unless opened or a dataset failed. */
export function Notices({ bundle, open, qualityHref }: { bundle: LoadedBundle; open: boolean; qualityHref: string }) {
  const out: ReactNode[] = bundle.manifest.known_issues.map((k) => (
    <div key={k.code} className="notice notice--warn" role="note">
      <span>
        <Badge tone="warn">Known issue</Badge>
      </span>
      <p>{k.text}</p>
      <span className="notice__code">{k.code}</span>
    </div>
  ));
  if (bundle.verification === "unavailable") {
    out.push(
      <div key="integrity" className="notice notice--warn" role="status">
        <span>
          <Badge tone="warn">Integrity not verified</Badge>
        </span>
        <p>File sizes were checked, but SHA-256 hashes could not be computed in this context (Web Crypto needs https or localhost). The data is shown, unverified.</p>
        <span className="notice__code">LOADER</span>
      </div>,
    );
  }
  if (bundle.compatibility.status === "newer_minor") {
    out.push(
      <div key="version" className="notice notice--info" role="status">
        <span>
          <Badge tone="info">Newer bundle version</Badge>
        </span>
        <p>{bundle.compatibility.message}</p>
        <span className="notice__code">CONTRACT</span>
      </div>,
    );
  }
  for (const k of failedDatasets(bundle)) {
    const st = k === "city" ? null : bundle[k];
    out.push(
      <div key={k} className="notice notice--error" role="alert">
        <span>
          <Badge tone="error">Dataset failed</Badge>
        </span>
        <p>
          <strong>{DATASET_NAMES[k]}</strong> did not load: {st && st.status === "failed" ? st.reasons.join("; ") : "unknown reason"}.{" "}
          {k === "cells" ? "The map shows barangay polygons and facilities; the whole cell layer is hidden." : "Panels that need it say so; other panels are unaffected."}
        </p>
        <span className="notice__code">{k}</span>
      </div>,
    );
  }
  if (out.length === 0) return null;
  return (
    <div className="notices" id={NOTICES_ID} hidden={!open}>
      <div className="notices__inner" role="region" aria-label="Bundle notices">
        {out}
        <p className="small muted" style={{ margin: 0 }}>
          These come from <code>manifest.known_issues</code> and the loader. Details: <a href={qualityHref}>Data Quality</a>. Generated {formatUtc(bundle.manifest.generated_utc)}.
        </p>
      </div>
    </div>
  );
}
