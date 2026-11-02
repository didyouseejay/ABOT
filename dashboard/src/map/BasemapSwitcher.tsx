/** The background-map choice shown on every map: street map or none (a radiogroup). */
import { Glyph, type GlyphName } from "../components/glyphs.tsx";
import { Seg } from "../components/ui.tsx";
import { BASEMAPS, type BasemapId } from "./leaflet.ts";

const GLYPH: Record<BasemapId, GlyphName> = { street: "street", none: "blank" };

export function BasemapSwitcher({ id, value, onChange }: { id: string; value: BasemapId; onChange: (b: BasemapId) => void }) {
  return (
    <div className="basemap-switch">
      <Seg
        id={id}
        ariaLabel="Background map"
        cls="seg--basemap"
        options={BASEMAPS.map((b) => [
          b.id,
          <>
            <Glyph name={GLYPH[b.id]} />
            <span>{b.label}</span>
          </>,
        ])}
        value={value}
        onChange={(v) => onChange(v as BasemapId)}
      />
    </div>
  );
}
