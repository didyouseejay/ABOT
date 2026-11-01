/**
 * Caveats as data (R2: texts come only from manifest.statements). Wherever a value needs a statement,
 * a small numbered reference or a code chip is shown; it opens the statement text in a popover, and
 * every statement used on the page is listed once in "Notes for this view" at the foot of the page.
 *
 * Numbers are assigned in render order through a registry created afresh for each render of the shell;
 * the notes footer is rendered after the page, so it lists exactly the statements the page used.
 */
import { createContext, type ReactNode, useCallback, useContext, useEffect, useId, useMemo, useState } from "react";
import type { Statement } from "../contract/types.ts";

export class NoteRegistry {
  readonly codes: string[] = [];
  n(code: string): number {
    let i = this.codes.indexOf(code);
    if (i < 0) {
      this.codes.push(code);
      i = this.codes.length - 1;
    }
    return i + 1;
  }
}

interface NotesApi {
  reg: NoteRegistry;
  statement: (code: string) => Statement | undefined;
  /** Whether the footer exists on this route (the popover then links to it). */
  footer: boolean;
  openCode: string | null;
  openEl: HTMLElement | null;
  toggle: (el: HTMLElement, code: string) => void;
  close: (refocus?: boolean) => void;
}

const NotesContext = createContext<NotesApi>({
  reg: new NoteRegistry(),
  statement: () => undefined,
  footer: false,
  openCode: null,
  openEl: null,
  toggle: () => {},
  close: () => {},
});

export const useNotes = () => useContext(NotesContext);

export function NotesProvider({ reg, statements, footer, children }: { reg: NoteRegistry; statements: Statement[]; footer: boolean; children: ReactNode }) {
  const [open, setOpen] = useState<{ code: string; el: HTMLElement } | null>(null);
  const byCode = useMemo(() => new Map(statements.map((s) => [s.code, s])), [statements]);
  const close = useCallback((refocus = false) => {
    setOpen((o) => {
      if (o && refocus) o.el.focus();
      return null;
    });
  }, []);
  const toggle = useCallback((el: HTMLElement, code: string) => setOpen((o) => (o && o.el === el ? null : { code, el })), []);
  const api: NotesApi = { reg, statement: (c) => byCode.get(c), footer, openCode: open?.code ?? null, openEl: open?.el ?? null, toggle, close };
  return (
    <NotesContext.Provider value={api}>
      {children}
      <Popover />
    </NotesContext.Provider>
  );
}

function Popover() {
  const { openCode, openEl, statement, close, reg, footer } = useNotes();
  const [pos, setPos] = useState<{ left: number; top: number; width: number } | null>(null);

  useEffect(() => {
    if (!openEl) return setPos(null);
    const r = openEl.getBoundingClientRect();
    const w = Math.min(352, window.innerWidth - 16);
    let left = r.left + window.scrollX;
    if (left + w > window.scrollX + window.innerWidth - 8) left = window.scrollX + window.innerWidth - w - 8;
    setPos({ left: Math.max(8, left), top: r.bottom + window.scrollY + 6, width: w });
  }, [openEl]);

  useEffect(() => {
    if (!openEl) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Element | null;
      if (t?.closest("[data-caveat]") || t?.closest(".popover")) return;
      close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close(true);
    };
    document.addEventListener("click", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [openEl, close]);

  if (!openCode || !pos) return null;
  const s = statement(openCode);
  const jump = (e: React.MouseEvent) => {
    e.preventDefault();
    close();
    const li = document.getElementById(`note-${openCode}`);
    if (li) {
      window.scrollTo({ top: li.getBoundingClientRect().top + window.scrollY - 120 });
      li.setAttribute("tabindex", "-1");
      li.focus();
    }
  };
  return (
    <div className="popover" role="dialog" aria-modal="false" aria-label="Statement" style={{ left: pos.left, top: pos.top, width: pos.width }}>
      <span className="popover__code">
        {openCode} · applies to {s?.applies_to ?? ""}
      </span>
      <p>{s?.text ?? "Statement not in the bundle."}</p>
      {footer && (
        <p className="popover__foot">
          <a href={`#note-${openCode}`} onClick={jump}>
            Note {reg.n(openCode)} in “Notes for this view”
          </a>
        </p>
      )}
    </div>
  );
}

/** Numbered superscript references, one per statement code. */
export function Ref({ codes }: { codes: string[] }) {
  const { reg, toggle, openEl } = useNotes();
  const id = useId();
  return (
    <>
      {codes.map((c) => {
        const n = reg.n(c);
        return (
          <button
            key={c}
            id={`${id}${c}`}
            type="button"
            className="note-ref"
            data-caveat={c}
            aria-label={`Note ${n}: ${c}`}
            aria-expanded={openEl?.id === `${id}${c}`}
            onClick={(e) => toggle(e.currentTarget, c)}
          >
            {n}
          </button>
        );
      })}
    </>
  );
}

/** A statement chip: its code, with the note number. */
export function Chip({ code }: { code: string }) {
  const { reg, toggle, openEl } = useNotes();
  const id = useId();
  const n = reg.n(code);
  return (
    <button
      id={id}
      type="button"
      className="caveat-chip"
      data-caveat={code}
      aria-expanded={openEl?.id === id}
      aria-label={`Statement ${code}, note ${n}`}
      onClick={(e) => toggle(e.currentTarget, code)}
    >
      <span className="caveat-chip__n" aria-hidden="true">
        {n}
      </span>
      {code}
    </button>
  );
}

export function Chips({ codes, label = "Notes" }: { codes: string[]; label?: string }) {
  return (
    <>
      <span className="panel__foot-label">{label}</span>
      {codes.map((c) => (
        <Chip key={c} code={c} />
      ))}
    </>
  );
}

/** "Notes for this view": every statement used on the page, once, verbatim from the bundle. */
export function NotesFooter() {
  const { reg, statement, footer } = useNotes();
  if (!footer || reg.codes.length === 0) return null;
  return (
    <aside className="notes-footer" aria-labelledby="notes-h">
      <div className="notes-footer__inner">
        <h2 id="notes-h">Notes for this view</h2>
        <ol>
          {reg.codes.map((c, i) => (
            <li key={c} id={`note-${c}`}>
              <span className="notes-footer__n">{i + 1}</span>
              <span>
                <span className="notes-footer__code">{c}</span>
                {statement(c)?.text ?? ""}
              </span>
            </li>
          ))}
        </ol>
      </div>
    </aside>
  );
}
