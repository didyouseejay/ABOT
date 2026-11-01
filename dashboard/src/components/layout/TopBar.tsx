/**
 * Top app bar: brand, the seven sections as tabs, and two collapsed forms. At medium widths the three
 * reference sections move into a "Reference" menu; below 56rem all sections move into a menu panel.
 * Both menus: focus moves in on open, Escape closes and returns focus to the button, choosing closes.
 */
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { ROUTES, routeDef } from "../../routes.ts";
import { Brand } from "./Brand.tsx";
import { MORE_MENU_ID, NAV_PANEL_ID } from "./ids.ts";

export interface TopBarProps {
  route: string;
  href: (route: string) => string;
  navOpen: boolean;
  onToggleNav: () => void;
  onNavigate: () => void;
}

const current = (id: string, route: string) => (id === route ? ("page" as const) : undefined);

export function TopBar({ route, href, navOpen, onToggleNav, onNavigate }: TopBarProps) {
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRoot = useRef<HTMLDivElement>(null);
  const moreBtn = useRef<HTMLButtonElement>(null);
  const isRef = routeDef(route).reference;
  const main = ROUTES.filter((r) => !r.reference);
  const refs = ROUTES.filter((r) => r.reference);

  useEffect(() => {
    if (!moreOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!moreRoot.current?.contains(e.target as Node)) setMoreOpen(false);
    };
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [moreOpen]);

  const openMore = (focusFirst: boolean) => {
    setMoreOpen(true);
    if (focusFirst) setTimeout(() => moreRoot.current?.querySelector<HTMLElement>(`#${MORE_MENU_ID} a`)?.focus(), 0);
  };
  const onMenuKey = (e: KeyboardEvent<HTMLUListElement>) => {
    const links = [...e.currentTarget.querySelectorAll<HTMLElement>("a")];
    const i = links.indexOf(document.activeElement as HTMLElement);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      links[(i + 1) % links.length]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      links[(i - 1 + links.length) % links.length]?.focus();
    } else if (e.key === "Escape") {
      setMoreOpen(false);
      moreBtn.current?.focus();
    }
  };

  return (
    <header className="topbar" id="topbar">
      <div className="topbar__inner">
        <Brand href={href("overview")} />
        <nav className="topnav" aria-label="Main">
          <ul className="topnav__list">
            {ROUTES.map((r, i) => (
              <li key={r.id} className={`topnav__group${r.reference ? " topnav__group--ref" : ""}${r.reference && !ROUTES[i - 1]?.reference ? " topnav__group--ref-first" : ""}`}>
                <a className="topnav__link" href={href(r.id)} aria-current={current(r.id, route)}>
                  {r.navLabel}
                </a>
              </li>
            ))}
          </ul>
          <div className="topnav__more" ref={moreRoot}>
            <button
              type="button"
              className="topnav__more-btn"
              ref={moreBtn}
              aria-expanded={moreOpen}
              aria-controls={MORE_MENU_ID}
              data-active={String(isRef)}
              onClick={() => (moreOpen ? setMoreOpen(false) : openMore(false))}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  openMore(true);
                }
              }}
            >
              <span>{isRef ? `Reference · ${routeDef(route).navLabel}` : "Reference"}</span>
              <svg className="icon" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" />
              </svg>
            </button>
            <ul className="topnav__more-menu" id={MORE_MENU_ID} hidden={!moreOpen} onKeyDown={onMenuKey} onClick={() => setMoreOpen(false)}>
              {refs.map((r) => (
                <li key={r.id}>
                  <a href={href(r.id)} aria-current={current(r.id, route)}>
                    {r.navLabel}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </nav>
        <button type="button" className="topbar__menu-btn" aria-expanded={navOpen} aria-controls={NAV_PANEL_ID} onClick={onToggleNav}>
          <svg viewBox="0 0 18 18" aria-hidden="true">
            <path d="M2 4.5h14M2 9h14M2 13.5h14" stroke="currentColor" strokeWidth="1.7" fill="none" />
          </svg>
          <span>{navOpen ? "Close" : "Menu"}</span>
        </button>
      </div>
      <div className="navpanel" id={NAV_PANEL_ID} data-open={String(navOpen)}>
        <nav aria-label="Main (menu)">
          <ul className="navpanel__list">
            {main.map((r) => (
              <li key={r.id}>
                <a href={href(r.id)} aria-current={current(r.id, route)} onClick={onNavigate}>
                  {r.navLabel}
                </a>
              </li>
            ))}
            <li className="navpanel__label" aria-hidden="true">
              Reference
            </li>
            {refs.map((r) => (
              <li key={r.id}>
                <a href={href(r.id)} aria-current={current(r.id, route)} onClick={onNavigate}>
                  {r.navLabel}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
