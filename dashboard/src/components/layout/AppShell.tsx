/**
 * The application shell: skip link, sidebar navigation, header, provenance bar and the main region.
 * Pure: it receives the route and the bundle state, so it renders the same in the browser and in tests.
 */
import type { BundleState } from "../../data/BundleContext.tsx";
import { PlaceholderPage } from "../../pages/PlaceholderPage.tsx";
import { routeDef } from "../../routes.ts";
import { BundleNotices, FatalState, LoadingState } from "../states/States.tsx";
import { Header } from "./Header.tsx";
import { PageContainer } from "./PageContainer.tsx";
import { ProvenanceBar } from "./ProvenanceBar.tsx";
import { Sidebar } from "./Sidebar.tsx";

export const MAIN_ID = "main-content";

export interface AppShellProps {
  route: string;
  state: BundleState;
  navOpen: boolean;
  onToggleNav: () => void;
  onNavigate: () => void;
}

function Content({ route, state }: { route: string; state: BundleState }) {
  const def = routeDef(route);
  if (state.status === "loading") {
    return (
      <PageContainer eyebrow="ABOT dashboard" title={def.title}>
        <LoadingState />
      </PageContainer>
    );
  }
  if (state.status === "fatal") {
    return (
      <PageContainer eyebrow="ABOT dashboard" title={def.title}>
        <FatalState issues={state.issues} />
      </PageContainer>
    );
  }
  return (
    <>
      <BundleNotices bundle={state.bundle} />
      <PlaceholderPage route={def} bundle={state.bundle} />
    </>
  );
}

export function AppShell({ route, state, navOpen, onToggleNav, onNavigate }: AppShellProps) {
  return (
    <div className="shell" data-nav-open={navOpen ? "true" : "false"}>
      <a className="skip-link" href={`#${MAIN_ID}`}>
        Skip to content
      </a>
      <Sidebar route={route} onNavigate={onNavigate} />
      <div className="shell__column">
        <Header section={routeDef(route).navLabel} navOpen={navOpen} onToggleNav={onToggleNav} />
        <ProvenanceBar state={state} />
        <main className="shell__main" id={MAIN_ID} tabIndex={-1}>
          <Content route={route} state={state} />
        </main>
      </div>
    </div>
  );
}
