/**
 * A registered section whose content is not built yet. It states what is planned and shows whether
 * the datasets the page will read loaded; it shows no values.
 */
import { DatasetAvailability, EmptyState } from "../components/states/States.tsx";
import { PageContainer } from "../components/layout/PageContainer.tsx";
import type { LoadedBundle } from "../data/loadBundle.ts";
import type { RouteDef } from "../routes.ts";

export function PlaceholderPage({ route, bundle }: { route: RouteDef; bundle: LoadedBundle }) {
  return (
    <PageContainer eyebrow="ABOT dashboard" title={route.title} lead={route.summary}>
      <EmptyState title="This page is not built yet">
        <p>Its content is planned for {route.planned}. No values are shown here until then.</p>
      </EmptyState>
      <section className="panel" aria-labelledby={`datasets-${route.id}`}>
        <h2 id={`datasets-${route.id}`}>Data this page will use</h2>
        <DatasetAvailability bundle={bundle} datasets={route.datasets} />
      </section>
    </PageContainer>
  );
}
