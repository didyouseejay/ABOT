/**
 * Interface states shared by every page. Errors are announced (role="alert") and listed in full; a
 * dataset that did not load is named with its reasons and nothing is shown in its place; an empty
 * filter result says so and offers to clear the filters.
 */
import type { ReactNode } from "react";
import type { Issue, LoadedBundle } from "../../data/loadBundle.ts";
import { DATASET_NAMES, datasetState } from "../../model/shell.ts";
import type { DatasetKey } from "../../routes.ts";
import { Icon } from "../ui.tsx";

export function LoadingState() {
  return (
    <div className="loading state state--loading" role="status" aria-live="polite">
      <p className="state__title">Loading the map data…</p>
      <p className="small muted">This takes a few seconds the first time.</p>
      <div className="progress" role="progressbar" aria-label="Loading the map data">
        <div className="progress__bar skeleton" style={{ width: "100%" }} />
      </div>
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
      <h2 className="state__title">The dashboard data could not be loaded</h2>
      <p>Please reload the page. If this keeps happening, the data files need to be prepared again (for the maintainer: run <code>abot export-dashboard</code>).</p>
      <IssueList issues={issues} />
    </div>
  );
}

/** A panel whose dataset did not load: the dataset is named with its reasons; nothing replaces it. */
export function Unavailable({ bundle, dataset, what = "This panel" }: { bundle: LoadedBundle; dataset: DatasetKey; what?: string }) {
  const st = datasetState(bundle, dataset);
  return (
    <div className="state state--unavailable" role="status">
      <p className="state__title">
        <Icon name="alert" /> {what} is unavailable
      </p>
      <p>
        {DATASET_NAMES[dataset]} did not load{st.status === "failed" ? `: ${st.reasons.join("; ")}` : ""}. Nothing is shown in its place; the rest of the page uses other datasets and still works.
      </p>
    </div>
  );
}

/** A panel the bundle lacks fields for (a contract mismatch): stated, never filled in. */
export function Broken({ what, error }: { what: string; error: unknown }) {
  return (
    <div className="state state--unavailable" role="status">
      <p className="state__title">
        <Icon name="alert" /> {what} could not be shown
      </p>
      <p>
        The bundle does not contain the fields this panel reads (<code>{error instanceof Error ? error.message : String(error)}</code>). Nothing is shown in its place.
      </p>
    </div>
  );
}

/** Render a panel; if the bundle lacks what it reads, show that instead of failing the whole page. */
export function guard(what: string, render: () => ReactNode): ReactNode {
  try {
    return render();
  } catch (e) {
    return <Broken what={what} error={e} />;
  }
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="state state--empty" role="status">
      <p className="state__title">{title}</p>
      {children}
      {action}
    </div>
  );
}
