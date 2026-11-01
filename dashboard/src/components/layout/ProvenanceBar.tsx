import type { BundleState } from "../../data/BundleContext.tsx";
import { shellStatusItems } from "../../model/shell.ts";
import { StatusBadge } from "../StatusBadge.tsx";

/** Bundle facts on every page: version, generation time, integrity, audit, code, datasets. */
export function ProvenanceBar({ state }: { state: BundleState }) {
  return (
    <section className="provenance" aria-label="Data provenance and status">
      <ul className="provenance__list">
        {shellStatusItems(state).map((item) => (
          <li key={item.key} className="provenance__item">
            <span className="provenance__label">{item.label}</span>
            <StatusBadge tone={item.tone} title={item.detail}>
              {item.value}
            </StatusBadge>
          </li>
        ))}
      </ul>
    </section>
  );
}
