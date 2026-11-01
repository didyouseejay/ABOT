/**
 * Top bar: brand and the five public sections. Below 48rem the sections move into a menu panel: focus
 * moves in on open, Escape closes it and returns focus to the button, choosing a section closes it.
 * The pages for researchers are linked from About and the footer, not from here.
 */
import { ROUTES } from "../../routes.ts";
import { Glyph } from "../glyphs.tsx";
import { Brand } from "./Brand.tsx";
import { NAV_PANEL_ID } from "./ids.ts";

export interface TopBarProps {
  route: string;
  href: (route: string) => string;
  navOpen: boolean;
  onToggleNav: () => void;
  onNavigate: () => void;
}

const current = (id: string, route: string) => (id === route ? ("page" as const) : undefined);

export function TopBar({ route, href, navOpen, onToggleNav, onNavigate }: TopBarProps) {
  const main = ROUTES.filter((r) => !r.reference);
  return (
    <header className="topbar" id="topbar">
      <div className="topbar__inner">
        <Brand href={href("overview")} />
        <nav className="topnav" aria-label="Main">
          <ul className="topnav__list">
            {main.map((r) => (
              <li key={r.id}>
                <a className="topnav__link" href={href(r.id)} aria-current={current(r.id, route)}>
                  {r.navLabel}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <button type="button" className="topbar__menu-btn" aria-expanded={navOpen} aria-controls={NAV_PANEL_ID} onClick={onToggleNav}>
          <Glyph name={navOpen ? "close" : "list"} />
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
          </ul>
        </nav>
      </div>
    </header>
  );
}
