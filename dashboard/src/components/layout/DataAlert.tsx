/**
 * The only bundle notice on the public pages: a dataset that did not load, or a newer bundle version.
 * Everything else about the bundle (version, integrity, audit, code, known issues) is on Data quality,
 * for researchers.
 */
import type { LoadedBundle } from "../../data/loadBundle.ts";
import { failedDatasets } from "../../model/shell.ts";
import type { DatasetKey } from "../../routes.ts";
import { Glyph } from "../glyphs.tsx";

/** What a missing dataset means for someone using the dashboard. */
const EFFECT: Record<DatasetKey, string> = {
  city: "citywide figures",
  barangays: "barangay boundaries on the maps",
  indicators: "barangay figures",
  cells: "the detailed 100 m grid on the map",
  facilities: "facility locations",
  network: "the network evidence for researchers",
  provenance: "the data-source list for researchers",
};

export function DataAlert({ bundle, qualityHref }: { bundle: LoadedBundle; qualityHref: string }) {
  const failed = failedDatasets(bundle);
  const newer = bundle.compatibility.status === "newer_minor";
  if (failed.length === 0 && !newer) return null;
  return (
    <div className="data-alert" role={failed.length ? "alert" : "status"}>
      <div className="data-alert__inner">
        <Glyph name="info" />
        <p>
          {failed.length > 0 && <>Some data could not be loaded, so this is missing: {failed.map((k) => EFFECT[k]).join("; ")}. The rest of the dashboard works. </>}
          {newer && <>This data was made by a newer version of ABOT; a few details may not be shown. </>}
          <a href={qualityHref}>Details</a>
        </p>
      </div>
    </div>
  );
}
