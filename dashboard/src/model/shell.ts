/**
 * What the application shell shows about the bundle: one labelled item per fact, each with a tone.
 * Every value is read from the bundle (nothing is hard-coded), and unknown or unavailable is never
 * given the tone of success: "ok" is used only for a verified, passed or clean state.
 */
import type { BundleState } from "../data/BundleContext.tsx";
import type { DatasetState, LoadedBundle } from "../data/loadBundle.ts";
import type { DatasetKey } from "../routes.ts";
import { formatUtc } from "./format.ts";
import { type AuditState, type GitState, auditView, gitView } from "./quality.ts";

export type Tone = "ok" | "warn" | "error" | "unknown" | "info";

export interface StatusItem {
  key: "contract" | "generated" | "integrity" | "audit" | "git" | "datasets";
  label: string;
  value: string;
  tone: Tone;
  detail?: string;
}

const AUDIT_TONE: Record<AuditState, Tone> = {
  passed: "ok",
  passed_with_warnings: "warn",
  not_run: "warn",
  invalid: "error",
};

const GIT_TONE: Record<GitState, Tone> = { clean: "ok", dirty: "warn", unknown: "unknown" };

export const DATASET_NAMES: Record<DatasetKey, string> = {
  city: "Citywide values (city.json)",
  barangays: "Barangay boundaries (barangays.geojson)",
  indicators: "Barangay indicators (barangay_indicators.json)",
  cells: "Population cells (cells-NNN.geojson)",
  facilities: "Facilities (facilities.geojson)",
  network: "Network evidence (network.json)",
  provenance: "Provenance (provenance.json)",
};

export function datasetState(b: LoadedBundle, key: DatasetKey): DatasetState<unknown> {
  return key === "city" ? { status: "ok", data: b.city } : b[key];
}

export function failedDatasets(b: LoadedBundle): DatasetKey[] {
  return (Object.keys(DATASET_NAMES) as DatasetKey[]).filter((k) => datasetState(b, k).status === "failed");
}

export function bundleStatusItems(b: LoadedBundle): StatusItem[] {
  const m = b.manifest;
  const audit = auditView(m.data_quality.source_validation.audit);
  const git = gitView(m.code);
  const failed = failedDatasets(b);
  const items: StatusItem[] = [
    {
      key: "contract",
      label: "Dataset version",
      value: `${m.contract} ${m.contract_version}`,
      tone: b.compatibility.status === "compatible" ? "info" : "warn",
      ...(b.compatibility.status === "newer_minor" ? { detail: b.compatibility.message } : {}),
    },
    { key: "generated", label: "Generated", value: formatUtc(m.generated_utc), tone: "info", detail: m.generated_utc },
    b.verification === "verified"
      ? { key: "integrity", label: "Integrity", value: "Verified (sizes and SHA-256)", tone: "ok" }
      : {
          key: "integrity",
          label: "Integrity",
          value: "Not verified (SHA-256 unavailable; sizes checked)",
          tone: "warn",
          detail: "Web Crypto is not available in this context (it needs https or localhost).",
        },
    { key: "audit", label: "Audit", value: audit.label, tone: AUDIT_TONE[audit.state] },
    {
      key: "git",
      label: "Code",
      value: git.label,
      tone: GIT_TONE[git.state],
      ...(m.code.git_commit ? { detail: m.code.git_commit } : {}),
    },
    failed.length === 0
      ? { key: "datasets", label: "Datasets", value: "All datasets available", tone: "ok" }
      : {
          key: "datasets",
          label: "Datasets",
          value: `${failed.length} dataset(s) unavailable`,
          tone: "error",
          detail: failed.map((k) => DATASET_NAMES[k]).join("; "),
        },
  ];
  return items;
}

/** Items while the bundle is loading or could not be loaded: nothing is claimed as known. */
export function shellStatusItems(state: BundleState): StatusItem[] {
  if (state.status === "ready") return bundleStatusItems(state.bundle);
  if (state.status === "loading") {
    return [{ key: "datasets", label: "Bundle", value: "Loading…", tone: "unknown" }];
  }
  return [{ key: "datasets", label: "Bundle", value: "Not loaded (see the error on this page)", tone: "error" }];
}
