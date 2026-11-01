/**
 * Display states of the audit block (§6.1.1) and the Git metadata (§7.1, §9.1). A skipped audit is
 * never a pass, and an unknown working tree is never shown as clean or as dirty.
 */
import type { AuditBlock, Manifest } from "../contract/types.ts";

export type AuditState = "passed" | "passed_with_warnings" | "not_run" | "invalid";

export interface AuditView {
  state: AuditState;
  label: string;
  isPass: boolean;
  warnings: AuditBlock["findings"];
}

export function auditView(a: AuditBlock): AuditView {
  if (a.status === "obtained" && a.outcome === "pass") {
    return { state: "passed", label: "Audit passed", isPass: true, warnings: [] };
  }
  if (a.status === "obtained" && a.outcome === "warn") {
    return { state: "passed_with_warnings", label: `Audit passed with ${a.findings.length} warning(s)`, isPass: false, warnings: a.findings };
  }
  if (a.status === "not_run") {
    return { state: "not_run", label: "Audit not run for this bundle", isPass: false, warnings: [] };
  }
  return { state: "invalid", label: "Audit state not valid for a bundle", isPass: false, warnings: [] };
}

export type GitState = "clean" | "dirty" | "unknown";

export interface GitView {
  state: GitState;
  label: string;
  commit: string | null;
}

export function gitView(code: Manifest["code"]): GitView {
  const commit = code.git_commit;
  if (code.git_working_tree_clean === true && commit !== null) {
    return { state: "clean", label: `Built from commit ${commit.slice(0, 7)} (clean working tree)`, commit };
  }
  if (code.git_working_tree_clean === false) {
    const n = code.git_dirty_count ?? code.git_dirty_paths.length;
    return {
      state: "dirty",
      label: `Built from a working tree with ${n} uncommitted change(s)` + (commit ? ` on top of ${commit.slice(0, 7)}` : ""),
      commit,
    };
  }
  return { state: "unknown", label: "Code version unknown (Git metadata unavailable)", commit };
}
