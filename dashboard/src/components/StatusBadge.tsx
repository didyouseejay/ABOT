import type { ReactNode } from "react";
import type { Tone } from "../model/shell.ts";

/** Symbol plus text, so the tone never depends on colour alone. */
const ICON: Record<Tone, string> = { ok: "✓", warn: "!", error: "✕", unknown: "?", info: "i" };
const TONE_WORD: Record<Tone, string> = { ok: "OK", warn: "Warning", error: "Error", unknown: "Unknown", info: "Info" };

export function StatusBadge({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string | undefined }) {
  return (
    <span className={`badge badge--${tone}`} title={title}>
      <span className="badge__icon" aria-hidden="true">
        {ICON[tone]}
      </span>
      <span className="visually-hidden">{TONE_WORD[tone]}: </span>
      {children}
    </span>
  );
}
