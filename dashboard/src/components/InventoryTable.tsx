/** Facility inventory per indicator group (city.facility_inventory), on Overview and, in depth, on Facilities. */
import type { City } from "../contract/types.ts";
import { groupLabel } from "../model/labels.ts";
import { Int, Rel } from "./ui.tsx";

const COLS: [key: string, label: string][] = [
  ["n_in_city", "In city"],
  ["n_in_buffer_outside_city", "In 3 km buffer"],
  ["n_destinations_connected", "Connected destinations"],
  ["n_not_connected_not_used", "Not connected (not used)"],
  ["n_unnamed", "Unnamed"],
  ["n_duplicate_review_pending", "Pending duplicate review"],
];

const num = (v: unknown): number | null => (typeof v === "number" ? v : null);

export function InventoryTable({ city, deep = false }: { city: City; deep?: boolean }) {
  const cols = deep ? [...COLS, ["n_not_decided_by_tag_rule", "Not decided by tag rule"] as [string, string]] : COLS;
  return (
    <div className="table-wrap">
      <table className="data-table">
        <caption className="visually-hidden">Facility inventory per indicator group</caption>
        <thead>
          <tr>
            <th scope="col">Group</th>
            {cols.map(([k, l]) => (
              <th key={k} scope="col" className="n">
                {l}
              </th>
            ))}
            <th scope="col">Inventory</th>
            {deep && (
              <>
                <th scope="col">Registry</th>
                <th scope="col">Note</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {city.facility_inventory.map((r) => {
            const g = String(r["group"]);
            const status = String(r["inventory_status"] ?? "");
            return (
              <tr key={g}>
                <th scope="row" style={{ fontWeight: 500 }}>
                  {groupLabel(g)}
                </th>
                {cols.map(([k]) => (
                  <td key={k} className="n">
                    <Int v={num(r[k])} />
                  </td>
                ))}
                <td>{status === "unverified" ? <Rel level="unverified" /> : status}</td>
                {deep && (
                  <>
                    <td>{String(r["registry_reference"] ?? "—")}</td>
                    <td className="small muted" style={{ minWidth: "16rem" }}>
                      {String(r["note"] ?? "")}
                    </td>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
