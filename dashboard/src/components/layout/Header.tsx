import { PROJECT } from "./Brand.tsx";
import { NAV_ID } from "./Sidebar.tsx";

export function Header({ section, navOpen, onToggleNav }: { section: string; navOpen: boolean; onToggleNav: () => void }) {
  return (
    <header className="header">
      <button
        type="button"
        className="header__menu"
        aria-controls={NAV_ID}
        aria-expanded={navOpen}
        onClick={onToggleNav}
      >
        <span aria-hidden="true">☰</span> {navOpen ? "Close menu" : "Menu"}
      </button>
      <p className="header__title">
        <strong>{PROJECT.name}</strong> <span aria-hidden="true">/</span> {section}
      </p>
      <p className="header__summary">{PROJECT.tagline}</p>
    </header>
  );
}
