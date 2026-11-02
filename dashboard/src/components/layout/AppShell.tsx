/**
 * The application shell: skip link, top bar, the data alert (only when something failed to load), the
 * main region, "Notes for this view" (pages for researchers only) and the footer. Pure: it receives
 * the view and the bundle state, so it renders the same in the browser and in tests.
 */
import type { BundleState } from "../../data/BundleContext.tsx";
import { AboutPage } from "../../pages/AboutPage.tsx";
import { BarangaysPage } from "../../pages/BarangaysPage.tsx";
import { FacilitiesPage } from "../../pages/FacilitiesPage.tsx";
import { MapPage } from "../../pages/MapPage.tsx";
import { MethodsPage } from "../../pages/MethodsPage.tsx";
import { NetworkPage } from "../../pages/NetworkPage.tsx";
import { OverviewPage } from "../../pages/OverviewPage.tsx";
import { QualityPage } from "../../pages/QualityPage.tsx";
import { formatUtc } from "../../model/format.ts";
import { ROUTES, routeDef } from "../../routes.ts";
import { type View, ViewContext } from "../../view.tsx";
import { NoteRegistry, NotesFooter, NotesProvider } from "../notes.tsx";
import { PageHeader } from "../ui.tsx";
import { FatalState, LoadingState } from "../states/States.tsx";
import { DATA_LICENCE, Mark, PROJECT } from "./Brand.tsx";
import { DataAlert } from "./DataAlert.tsx";
import { MAIN_ID } from "./ids.ts";
import { TopBar } from "./TopBar.tsx";

export interface AppShellProps {
  view: View;
  state: BundleState;
  navOpen: boolean;
  onToggleNav: () => void;
  onNavigate: () => void;
}

const PAGES = {
  overview: OverviewPage,
  map: MapPage,
  barangays: BarangaysPage,
  facilities: FacilitiesPage,
  about: AboutPage,
  methods: MethodsPage,
  quality: QualityPage,
  network: NetworkPage,
} as const;

function Content({ route, state }: { route: string; state: BundleState }) {
  if (state.status !== "ready") {
    return (
      <div className="page">
        <PageHeader title={routeDef(route).title} />
        {state.status === "loading" ? <LoadingState /> : <FatalState issues={state.issues} />}
      </div>
    );
  }
  const Page = PAGES[route as keyof typeof PAGES] ?? OverviewPage;
  return <Page bundle={state.bundle} />;
}

function Footer({ view, state }: { view: View; state: BundleState }) {
  const research = ROUTES.filter((r) => r.reference);
  return (
    <footer className="footer">
      <div className="footer__inner">
        <div className="footer__brand">
          <Mark />
          <div>
            <p className="footer__name">
              {PROJECT.name} · {PROJECT.tagline}
            </p>
            <p className="footer__sub">
              {PROJECT.fullName}. {PROJECT.attribution}
            </p>
          </div>
        </div>
        <nav className="footer__links" aria-label="For researchers">
          <span className="footer__label">For researchers</span>
          {research.map((r) => (
            <a key={r.id} href={view.href(r.id)}>
              {r.navLabel}
            </a>
          ))}
        </nav>
        <p className="footer__meta">
          {state.status === "ready" && <>Data prepared {formatUtc(state.bundle.manifest.generated_utc).slice(0, 10)} · </>}
          Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · Dataset: <a href={DATA_LICENCE.url}>{DATA_LICENCE.name}</a> (<a href={DATA_LICENCE.releases}>downloads</a>) · Code: MIT
        </p>
      </div>
    </footer>
  );
}

export function AppShell({ view, state, navOpen, onToggleNav, onNavigate }: AppShellProps) {
  // A fresh registry per render: the notes footer lists what this render of the page referenced.
  const reg = new NoteRegistry();
  const statements = state.status === "ready" ? state.bundle.manifest.statements : [];
  const research = routeDef(view.route).reference;
  return (
    <ViewContext.Provider value={view}>
      <NotesProvider reg={reg} statements={statements} footer={research}>
        <div className="shell" data-nav-open={navOpen ? "true" : "false"} data-route={view.route}>
          <a className="skip-link" href={`#${MAIN_ID}`}>
            Skip to content
          </a>
          <TopBar route={view.route} href={(r) => view.href(r)} navOpen={navOpen} onToggleNav={onToggleNav} onNavigate={onNavigate} />
          {state.status === "ready" && <DataAlert bundle={state.bundle} qualityHref={view.href("quality")} />}
          <main className="main" id={MAIN_ID} tabIndex={-1}>
            <Content route={view.route} state={state} />
          </main>
          <NotesFooter />
          {view.route !== "map" && <Footer view={view} state={state} />}
        </div>
      </NotesProvider>
    </ViewContext.Provider>
  );
}
