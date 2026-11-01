/**
 * Small shared components of the design: values (null shown as "No value", never 0), tags for
 * scenario, role and reliability (always a word and a symbol, never colour alone), icons, panels and
 * the selection controls. Selection controls write to the address through the view.
 */
import { type KeyboardEvent, type ReactNode, useRef } from "react";
import { PAGE_TITLE_ID } from "./layout/ids.ts";
import { fixed } from "../model/format.ts";
import { categoryDef, groupLabel } from "../model/labels.ts";
import type { RelLevel } from "../model/values.ts";
import { Chips } from "./notes.tsx";

export { StatusBadge as Badge } from "./StatusBadge.tsx";

// --- values -------------------------------------------------------------------------------------

export function NullValue({ reason, short = true }: { reason?: string | undefined; short?: boolean }) {
  const r = reason ?? "not in the bundle";
  return (
    <span className="null-value" tabIndex={0} title={reason ?? "No value in the bundle"} aria-label={`No value: ${r}`}>
      {short ? "—" : "No value"}
    </span>
  );
}

type V = number | null | undefined;
const isNull = (v: V): v is null | undefined => v === null || v === undefined;

export const Num = ({ v, d = 1, reason }: { v: V; d?: number; reason?: string }) => (isNull(v) ? <NullValue reason={reason} /> : <>{fixed(v, d)}</>);
export const Int = ({ v, reason }: { v: V; reason?: string }) => (isNull(v) ? <NullValue reason={reason} /> : <>{fixed(Math.round(v), 0)}</>);
export const Pct = ({ v, d = 1, reason }: { v: V; d?: number; reason?: string }) => (isNull(v) ? <NullValue reason={reason} /> : <>{fixed(v, d)}&#8239;%</>);
export const Min = ({ v, d = 1, reason }: { v: V; d?: number; reason?: string }) => (isNull(v) ? <NullValue reason={reason} /> : <>{fixed(v, d)}&#8239;min</>);

/** Text form for SVG labels and aria text (no element). */
export const txt = (v: V, d = 1, unit = ""): string => (isNull(v) ? "no value" : `${fixed(v, d)}${unit}`);

// --- icons (inline SVG set: 16×16, stroke 1.6) --------------------------------------------------

const ICONS = {
  map: <path d="M1.5 3.5l4-1.5 5 2 4-1.5v10l-4 1.5-5-2-4 1.5z M5.5 2v10 M10.5 4v10" />,
  table: <path d="M2 3h12v10H2z M2 6.5h12 M2 10h12 M6 3v10" />,
  shield: <path d="M8 1.5l5.5 2v4c0 3.2-2.3 5.6-5.5 7-3.2-1.4-5.5-3.8-5.5-7v-4z M5.5 8l1.8 1.8 3.2-3.6" />,
  arrow: <path d="M3 8h10 M9 4l4 4-4 4" />,
  close: <path d="M3.5 3.5l9 9 M12.5 3.5l-9 9" />,
  info: (
    <>
      <circle cx="8" cy="8" r="6.3" />
      <path d="M8 7v4.5 M8 4.6v.1" />
    </>
  ),
  alert: <path d="M8 1.8l6.5 11.7h-13z M8 6.3v3.6 M8 11.6v.1" />,
  print: <path d="M4 6V1.8h8V6 M4 11.5H2V6h12v5.5h-2 M4 9.5h8v4.7H4z" />,
  layers: <path d="M8 2l6.5 3.3L8 8.6 1.5 5.3z M1.5 8.2L8 11.5l6.5-3.3 M1.5 11L8 14.3l6.5-3.3" />,
  search: (
    <>
      <circle cx="7" cy="7" r="4.6" />
      <path d="M10.4 10.4l3.8 3.8" />
    </>
  ),
  filter: <path d="M1.8 2.5h12.4L9.5 8.3v4.8l-3 1.4V8.3z" />,
  external: <path d="M9.5 2.5h4v4 M13.5 2.5L7.5 8.5 M12 9.5v4H2.5V4h4" />,
  compare: <path d="M2 3h5v10H2z M9 3h5v10H9z" />,
  sliders: <path d="M2 4h7 M12 4h2 M2 12h2 M7 12h7 M10.5 2.3v3.4 M5.5 10.3v3.4" />,
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name, className = "icon" }: { name: IconName; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {ICONS[name]}
    </svg>
  );
}

// --- tags ---------------------------------------------------------------------------------------

const REL: Record<RelLevel, [string, string]> = { ok: ["✓", "OK"], caution: ["!", "Caution"], low: ["▼", "Low"], unverified: ["?", "Unverified"], unknown: ["?", "Unknown"] };

export function Rel({ level, dim, reason }: { level: RelLevel; dim?: string; reason?: string | null }) {
  const [s, w] = REL[level];
  return (
    <span className={`rel-badge rel-badge--${level === "unknown" ? "unverified" : level}`} title={reason ?? undefined}>
      <span className="rel-badge__sym" aria-hidden="true">
        {s}
      </span>
      {dim && (
        <>
          <span className="rel-badge__dim">{dim}</span>{" "}
        </>
      )}
      {w}
    </span>
  );
}

export type ScenKey = "a3" | "a1" | "drive" | "a2";
const SCEN: Record<ScenKey, [string, string]> = {
  a3: ["A3 · walk · primary", "A3 component-aware walking: the primary result"],
  a1: ["A1 · walk · comparison", "A1 optimistic walking scenario: comparison only"],
  drive: ["A1 · drive", "A1 driving: separate mode, modelled uncongested"],
  a2: ["A2 · walk · evidence", "A2 all eligible components: evidence only"],
};

export function Scen({ k, text }: { k: ScenKey; text?: string }) {
  return (
    <span className={`scenario-tag scenario-tag--${k}`} title={SCEN[k][1]}>
      {text ?? SCEN[k][0]}
    </span>
  );
}

export type RoleKey = "primary" | "comparative" | "descriptive" | "evidence" | "analysis";
const ROLE: Record<RoleKey, string> = { primary: "Primary", comparative: "Comparative", descriptive: "Descriptive", evidence: "Evidence only", analysis: "Analysis only" };

export function Role({ k, text }: { k: RoleKey; text?: string }) {
  return <span className={`role-tag role-tag--${k}`}>{text ?? ROLE[k]}</span>;
}

export const roleOf = (r: string): RoleKey =>
  (({ primary: "primary", comparative: "comparative", descriptive: "descriptive", evidence_only: "evidence", analysis_only: "analysis" }) as Record<string, RoleKey>)[r] ?? "descriptive";

/** Stamp on every analysis-only record (title: DQ-ANALYSIS-ONLY from the bundle). */
export function Stamp({ title }: { title?: string | undefined }) {
  return (
    <span className="stamp" title={title}>
      ◌ Analysis only · not applied
    </span>
  );
}

export function CatSym({ id }: { id: string }) {
  return (
    <span className={`cat-sym cat-sym--${id}`} aria-hidden="true">
      {categoryDef(id)?.sym ?? "?"}
    </span>
  );
}

// --- layout -------------------------------------------------------------------------------------

export function PageHeader({ eyebrow, tagline, title, lead, controls }: { eyebrow?: ReactNode; tagline?: string; title: string; lead?: ReactNode; controls?: ReactNode }) {
  return (
    <header className="page__header">
      <div className="page__heading">
        {eyebrow && <p className="page__eyebrow">{eyebrow}</p>}
        {tagline && <p className="page__tagline">{tagline}</p>}
        <h1 id={PAGE_TITLE_ID} tabIndex={-1}>
          {title}
        </h1>
        {lead && <p className="page__lead">{lead}</p>}
      </div>
      {controls && <div className="page__controls">{controls}</div>}
    </header>
  );
}

export function Panel({ id, title, sub, tags, codes = [], cls = "", foot, children }: { id: string; title: ReactNode; sub?: ReactNode; tags?: ReactNode; codes?: string[]; cls?: string; foot?: ReactNode; children: ReactNode }) {
  return (
    <section className={`panel ${cls}`} id={id} aria-labelledby={`${id}-h`}>
      <div className="panel__head">
        <h2 className="panel__title" id={`${id}-h`}>
          {title}
        </h2>
        {tags && <div className="panel__tags">{tags}</div>}
        {sub && <p className="panel__sub">{sub}</p>}
      </div>
      <div className="panel__body">{children}</div>
      {(codes.length > 0 || foot) && (
        <div className="panel__foot">
          {foot}
          {codes.length > 0 && <Chips codes={codes} />}
        </div>
      )}
    </section>
  );
}

export function SectionBand({ title, kind, tags, children }: { title: string; kind?: "drive" | "evidence"; tags?: ReactNode; children?: ReactNode }) {
  return (
    <div className={`section-band${kind ? ` section-band--${kind}` : ""}`}>
      <h2>{title}</h2>
      {tags}
      {children && <p>{children}</p>}
    </div>
  );
}

export function StatStrip({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <div className="stat-strip">
      {items.map(([v, l], i) => (
        <div className="stat-strip__item" key={i}>
          <div className="stat-strip__v">{v}</div>
          <div className="stat-strip__l">{l}</div>
        </div>
      ))}
    </div>
  );
}

// --- controls -----------------------------------------------------------------------------------

export type SegOption = [value: string, label: ReactNode, disabled?: boolean];

/** A radiogroup of buttons with a roving tabindex; arrow keys move the selection. */
export interface SegProps {
  id: string;
  label?: string;
  options: SegOption[];
  value: string;
  onChange: (v: string) => void;
  cls?: string;
  ariaLabel?: string;
  btnCls?: string | ((v: string) => string);
  /** Stretch the buttons over the full width. */
  fill?: boolean;
}

export function Seg({ id, label, options, value, onChange, cls = "", ariaLabel, btnCls = "", fill = false }: SegProps) {
  const root = useRef<HTMLDivElement>(null);
  const onKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    const enabled = options.filter((o) => !o[2]);
    const i = enabled.findIndex((o) => o[0] === value);
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : enabled.length - 1;
    const next = enabled[(i + step) % enabled.length];
    if (!next) return;
    onChange(next[0]);
    setTimeout(() => document.getElementById(`${id}-${next[0].replace(/\W/g, "")}`)?.focus(), 0);
  };
  const group = (
    <div className={`seg ${cls}`} role="radiogroup" aria-labelledby={label ? `${id}-l` : undefined} aria-label={label ? undefined : ariaLabel} id={id} ref={root} style={fill ? { width: "100%" } : undefined}>
      {options.map(([v, t, dis]) => (
        <button
          key={v}
          type="button"
          className={`seg__btn ${typeof btnCls === "function" ? btnCls(v) : btnCls}`.trim()}
          role="radio"
          aria-checked={v === value}
          tabIndex={v === value ? 0 : -1}
          id={`${id}-${v.replace(/\W/g, "")}`}
          disabled={dis}
          style={fill ? { flex: 1 } : undefined}
          onClick={() => onChange(v)}
          onKeyDown={onKey}
        >
          {t}
        </button>
      ))}
    </div>
  );
  if (!label) return group;
  return (
    <div className="field">
      <span className="field__label" id={`${id}-l`}>
        {label}
      </span>
      {group}
    </div>
  );
}

export function GroupSelect({ id, groups, value, onChange, label = "Indicator group", phrase }: { id: string; groups: readonly string[]; value: string; onChange: (g: string) => void; label?: string; phrase?: (g: string) => string }) {
  return (
    <label className="field" htmlFor={id}>
      <span className="field__label">{label}</span>
      <select className="select" id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {groups.map((g) => (
          <option key={g} value={g}>
            {phrase ? phrase(g) : groupLabel(g)}
          </option>
        ))}
      </select>
    </label>
  );
}

export function thresholdOptions(list: readonly number[]): SegOption[] {
  return list.map((t) => [String(t), `≤ ${t} min`]);
}

export function Check({ id, checked, onChange, disabled, children }: { id: string; checked: boolean; onChange: (on: boolean) => void; disabled?: boolean; children: ReactNode }) {
  return (
    <label className="check" htmlFor={id}>
      <input type="checkbox" id={id} checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span>{children}</span>
    </label>
  );
}

export function printPage() {
  window.print();
}
