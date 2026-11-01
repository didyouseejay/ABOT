/**
 * Interface states shared by every page. Errors are announced (role="alert") and listed in full;
 * an unverified or newer bundle is stated, never implied to be fine.
 */
import type { ReactNode } from "react";
import type { Issue, LoadedBundle } from "../../data/loadBundle.ts";
import { DATASET_NAMES, datasetState } from "../../model/shell.ts";
import type { DatasetKey } from "../../routes.ts";
import { StatusBadge } from "../StatusBadge.tsx";

export function LoadingState() {
  return (
    <div className="state state--loading" role="status" aria-live="polite">
      <p className="state__title">Loading the dashboard bundle…</p>
      <p>Every file is checked against the bundle manifest before anything is shown.</p>
    </div>
  );
}

export function IssueList({ issues }: { issues: Issue[] }) {
  return (
    <ul className="state__list">
      {issues.map((i, n) => (
        <li key={n}>
          <strong>{i.level === "error" ? "Error" : "Warning"}</strong> <code>{i.dataset}</code>: {i.message}
        </li>
      ))}
    </ul>
  );
}

/** The bundle could not be loaded at all: nothing is shown in its place. */
export function FatalState({ issues }: { issues: Issue[] }) {
  return (
    <div className="state state--error" role="alert">
      <h2 className="state__title">The dashboard bundle could not be loaded</h2>
      <p>
        No values are shown. Re-create the bundle with <code>abot export-dashboard</code>, then reload this page.
      </p>
      <IssueList issues={issues} />
    </div>
  );
}

/** Bundle-wide notices shown above every page: integrity not verified, newer contract, failed datasets. */
export function BundleNotices({ bundle }: { bundle: LoadedBundle }) {
  const notices: ReactNode[] = [];
  if (bundle.verification === "unavailable") {
    notices.push(
      <div key="integrity" className="state state--warn" role="status">
        <p className="state__title">Integrity not verified</p>
        <p>
          File sizes were checked, but SHA-256 hashes could not be computed in this context (Web Crypto needs https
          or localhost). The data is shown, unverified.
        </p>
      </div>,
    );
  }
  if (bundle.compatibility.status === "newer_minor") {
    notices.push(
      <div key="version" className="state state--warn" role="status">
        <p className="state__title">Newer bundle version</p>
        <p>{bundle.compatibility.message}</p>
      </div>,
    );
  }
  const errors = bundle.issues.filter((i) => i.level === "error");
  if (errors.length > 0) {
    notices.push(
      <div key="errors" className="state state--error" role="alert">
        <p className="state__title">Some datasets could not be loaded</p>
        <p>Pages that need them show what is missing. Other pages are unaffected.</p>
        <IssueList issues={errors} />
      </div>,
    );
  }
  return <>{notices}</>;
}

/** Which datasets a page needs and whether they loaded; failed ones list their reasons. */
export function DatasetAvailability({ bundle, datasets }: { bundle: LoadedBundle; datasets: DatasetKey[] }) {
  return (
    <ul className="dataset-list">
      {datasets.map((k) => {
        const st = datasetState(bundle, k);
        return (
          <li key={k} className="dataset-list__item">
            <StatusBadge tone={st.status === "ok" ? "ok" : "error"}>{st.status === "ok" ? "Loaded" : "Unavailable"}</StatusBadge>
            <span>{DATASET_NAMES[k]}</span>
            {st.status === "failed" && (
              <ul className="dataset-list__reasons">
                {st.reasons.map((r, n) => (
                  <li key={n}>{r}</li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state--empty">
      <p className="state__title">{title}</p>
      {children}
    </div>
  );
}
