/** The contract this frontend implements (docs/DASHBOARD_DATA_CONTRACT.md §9.2 condition 4, §14). */
export const CONTRACT_ID = "abot-dashboard";
export const SUPPORTED_VERSION = "1.1.0";

export interface Version {
  major: number;
  minor: number;
  patch: number;
}

export function parseVersion(v: unknown): Version | null {
  if (typeof v !== "string") return null;
  const m = /^(\d+)\.(\d+)\.(\d+)$/.exec(v);
  if (!m) return null;
  return { major: Number(m[1]), minor: Number(m[2]), patch: Number(m[3]) };
}

export type Compatibility =
  | { status: "compatible" }
  | { status: "newer_minor"; message: string }
  | { status: "incompatible"; message: string };

/**
 * Major mismatch: refuse to load. Newer minor: load and warn (fields this frontend does not know
 * are ignored, never guessed). Older minor or any patch difference: compatible.
 */
export function checkCompatibility(contract: unknown, version: unknown): Compatibility {
  if (contract !== CONTRACT_ID) {
    return { status: "incompatible", message: `not an ${CONTRACT_ID} bundle (contract: ${String(contract)})` };
  }
  const got = parseVersion(version);
  const want = parseVersion(SUPPORTED_VERSION) as Version;
  if (got === null) return { status: "incompatible", message: `unreadable contract_version: ${String(version)}` };
  if (got.major !== want.major) {
    return {
      status: "incompatible",
      message: `bundle contract ${String(version)} has another major version than the supported ${SUPPORTED_VERSION}`,
    };
  }
  if (got.minor > want.minor) {
    return {
      status: "newer_minor",
      message:
        `bundle contract ${String(version)} is newer than the supported ${SUPPORTED_VERSION}: ` +
        "fields added in the newer version are not shown",
    };
  }
  return { status: "compatible" };
}
