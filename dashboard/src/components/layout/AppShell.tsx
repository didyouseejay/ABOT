/**
 * The application shell: skip link, top navigation, provenance colophon and notices, the main region,
 * "Notes for this view" and the footer. Pure: it receives the view and the bundle state, so it renders
 * the same in the browser and in tests.
 */
import type { BundleState } from "../../data/BundleContext.tsx";
import { AboutPage } from "../../pages/AboutPage.tsx";
import { BarangaysPage } from "../../pages/BarangaysPage.tsx";
import { FacilitiesPage } from "../../pages/FacilitiesPage.tsx";
import { MapPage } from "../../pages/MapPage.tsx";
import { NetworkPage } from "../../pages/NetworkPage.tsx";
import { OverviewPage } from "../../pages/OverviewPage.tsx";
import { QualityPage } from "../../pages/QualityPage.tsx";
import { failedDatasets } from "../../model/shell.ts";
import { routeDef } from "../../routes.ts";
import { type View, ViewContext } from "../../view.tsx";
import { NoteRegistry, NotesFooter, NotesProvider } from "../notes.tsx";
import { PageHeader } from "../ui.tsx";
import { FatalState, LoadingState } from "../states/States.tsx";
import { PROJECT } from "./Brand.tsx";
import { MAIN_ID } from "./ids.ts";
import { Notices, ProvenanceBar } from "./ProvenanceBar.tsx";
import { TopBar } from "./TopBar.tsx";

export interface AppShellProps {
  view: View;
  state: BundleState;
  navOpen: boolean;
  onToggleNav: () => void;
  onNavigate: () => void;
  /** null: the default (open only when a dataset failed). */
  noticesOpen?: boolean | null;
  onToggleNotices?: () => void;
}

const PAGES = {
  overview: OverviewPage,
  map: MapPage,
  barangays: BarangaysPage,
  facilities: FacilitiesPage,
  network: NetworkPage,
  quality: QualityPage,
  about: AboutPage,
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

export function AppShell({ view, state, navOpen, onToggleNav, onNavigate, noticesOpen = null, onToggleNotices = () => {} }: AppShellProps) {
  // A fresh registry per render: the notes footer lists what this render of the page referenced.
  const reg = new NoteRegistry();
  const statements = state.status === "ready" ? state.bundle.manifest.statements : [];
  const open = noticesOpen ?? (state.status === "ready" && failedDatasets(state.bundle).length > 0);
  return (
    <ViewContext.Provider value={view}>
      <NotesProvider reg={reg} statements={statements} footer={view.route !== "map"}>
        <div className="shell" data-nav-open={navOpen ? "true" : "false"} data-route={view.route}>
          <a className="skip-link" href={`#${MAIN_ID}`}>
            Skip to content
          </a>
          <TopBar route={view.route} href={(r) => view.href(r)} navOpen={navOpen} onToggleNav={onToggleNav} onNavigate={onNavigate} />
          <ProvenanceBar state={state} noticesOpen={open} onToggleNotices={onToggleNotices} />
          {state.status === "ready" && <Notices bundle={state.bundle} open={open} qualityHref={view.href("quality")} />}
          <main className="main" id={MAIN_ID} tabIndex={-1}>
            <Content route={view.route} state={state} />
          </main>
          <NotesFooter />
          <footer className="footer">
            <div className="footer__inner">
              <span className="footer__tag">{PROJECT.tagline}</span>
              <span>{PROJECT.phrase}</span>
              <span>
                {PROJECT.name} · {PROJECT.institution} · Research prototype, read-only
              </span>
              <span className="footer__links">
                <a href={view.href("quality")}>Data Quality</a>
                <a href={view.href("about")}>Methodology</a>
              </span>
            </div>
          </footer>
        </div>
      </NotesProvider>
    </ViewContext.Provider>
  );
}
