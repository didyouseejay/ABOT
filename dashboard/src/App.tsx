/**
 * M05.2 S1–S2 foundation: loads the bundle and shows its load and verification status only. The
 * overview, map and data-quality pages are later stages (S3+).
 */
import { type BundleState, useBundle } from "./data/BundleContext.tsx";
import type { DatasetState } from "./data/loadBundle.ts";
import { formatUtc } from "./model/format.ts";
import { auditView, gitView } from "./model/quality.ts";
import { hrefFor, useHashRoute } from "./router.ts";

const ROUTES = ["status"] as const;

function datasetLine(name: string, st: DatasetState<unknown>) {
  return (
    <li key={name}>
      <code>{name}</code>: {st.status === "ok" ? "loaded" : `not available (${st.reasons.length} problem(s))`}
    </li>
  );
}

function Status({ state }: { state: BundleState }) {
  if (state.status === "loading") return <p role="status">Loading the dashboard bundle…</p>;
  if (state.status === "fatal") {
    return (
      <section role="alert">
        <h2>The dashboard bundle could not be loaded</h2>
        <ul>
          {state.issues.map((i, n) => (
            <li key={n}>
              <strong>{i.level}</strong> ({i.dataset}): {i.message}
            </li>
          ))}
        </ul>
      </section>
    );
  }
  const b = state.bundle;
  const m = b.manifest;
  const cellLine =
    b.cells.status === "ok" ? `${b.cells.data.length.toLocaleString("en")} cells` : "cell layer disabled";
  return (
    <section>
      <h2>Bundle status</h2>
      <dl>
        <dt>Contract</dt>
        <dd>
          {m.contract} {m.contract_version}
        </dd>
        <dt>Generated</dt>
        <dd>{formatUtc(m.generated_utc)}</dd>
        <dt>File verification</dt>
        <dd>
          {b.verification === "verified" ? "sizes and SHA-256 verified" : "sizes checked; SHA-256 verification unavailable"}
        </dd>
        <dt>Audit</dt>
        <dd>{auditView(m.data_quality.source_validation.audit).label}</dd>
        <dt>Code</dt>
        <dd>{gitView(m.code).label}</dd>
        <dt>Cells</dt>
        <dd>{cellLine}</dd>
      </dl>
      <ul>
        {datasetLine("barangays", b.barangays)}
        {datasetLine("barangay_indicators", b.indicators)}
        {datasetLine("facilities", b.facilities)}
        {datasetLine("network", b.network)}
        {datasetLine("provenance", b.provenance)}
        {datasetLine("cells", b.cells)}
      </ul>
      {b.issues.length > 0 && (
        <>
          <h3>Issues</h3>
          <ul>
            {b.issues.map((i, n) => (
              <li key={n}>
                <strong>{i.level}</strong> ({i.dataset}): {i.message}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export default function App() {
  const route = useHashRoute(ROUTES, "status");
  const state = useBundle();
  return (
    <main className="app">
      <header>
        <h1>ABOT dashboard</h1>
        <nav>
          <a href={hrefFor("status")} aria-current={route === "status" ? "page" : undefined}>
            Bundle status
          </a>
        </nav>
      </header>
      <Status state={state} />
    </main>
  );
}
