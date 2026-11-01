import { hrefFor } from "../../router.ts";
import { ROUTES } from "../../routes.ts";
import { Brand, PROJECT } from "./Brand.tsx";

export const NAV_ID = "primary-navigation";

/** Section navigation. The active section is marked with aria-current="page" (and visually). */
export function Sidebar({ route, onNavigate }: { route: string; onNavigate?: () => void }) {
  return (
    <aside className="shell__sidebar" aria-label="ABOT">
      <Brand />
      <nav className="nav" id={NAV_ID} aria-label="Dashboard sections">
        <ul className="nav__list">
          {ROUTES.map((r) => (
            <li key={r.id}>
              <a
                className="nav__link"
                href={hrefFor(r.id)}
                aria-current={r.id === route ? "page" : undefined}
                onClick={onNavigate}
              >
                {r.navLabel}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <div className="sidebar__tagline">
        <strong>{PROJECT.tagline}</strong>
        {PROJECT.phrase}
      </div>
    </aside>
  );
}
