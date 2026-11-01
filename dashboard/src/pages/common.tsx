/**
 * The barangay panel shared by the map's side drawer (compact) and the Barangays profile (full): the
 * selected service in one sentence, every service at a glance, the facilities counted in the barangay
 * and the data confidence in everyday words. Walking is the primary result; the full profile adds a
 * second list for the other mode.
 */
import { ServiceGlyph, Glyph } from "../components/glyphs.tsx";
import { CONFIDENCE, FAC_CATS, facCatName, servicePhrase, serviceName } from "../model/labels.ts";
import { brgyAvg, brgyShare, intText, limitOf, minText, pctText, verbOf } from "../model/plain.ts";
import type { Shared } from "../model/view.ts";
import { type Barangay, relOf } from "../model/values.ts";
import { fixed } from "../model/format.ts";
import { useView } from "../view.tsx";

export const NOT_RANKED = "Not ranked: the population or road data for this barangay is too uncertain";

function ServiceList({ b, groups, s, title }: { b: Barangay; groups: string[]; s: Shared; title: string }) {
  return (
    <section className="bp-section">
      <h3>{title}</h3>
      <ul className="svc-list">
        {groups.map((g) => {
          const v = brgyShare(b.rec, s, g);
          return (
            <li key={g} data-selected={g === s.g ? "true" : undefined}>
              <ServiceGlyph id={g} />
              <span className="svc-list__name">{serviceName(g)}</span>
              <span className="meter" aria-hidden="true">
                <span className="meter__fill" style={{ width: `${v ?? 0}%` }} />
              </span>
              <span className="svc-list__v">{pctText(v)}</span>
              <span className="svc-list__avg">{minText(brgyAvg(b.rec, s, g))}</span>
            </li>
          );
        })}
      </ul>
      <p className="bp-legend">
        Share of residents within {limitOf(s)} min · typical {verbOf(s)} time
      </p>
    </section>
  );
}

export function BarangayPanel({ b, groups, compact, onClose }: { b: Barangay; groups: string[]; compact: boolean; onClose: () => void }) {
  const { s, href } = useView();
  const r = b.rec;
  const share = brgyShare(r, s);
  const avg = brgyAvg(r, s);
  const rel = relOf(r, "overall");
  const [word, text] = CONFIDENCE[rel.level] ?? ["Unknown", ""];
  const other: Shared = { ...s, m: s.m === "drive" ? "walk" : "drive" };
  const facs = FAC_CATS.map((c) => [c, r.facility_counts[`n_${c}`] ?? null] as const);

  return (
    <>
      <div className="drawer__grabber" aria-hidden="true" />
      <div className="drawer__head">
        <div>
          <p className="drawer__eyebrow">Barangay</p>
          <h2 className="drawer__title" id="drawer-title">
            {b.name}
          </h2>
          <p className="drawer__meta">
            <Glyph name="users" /> {intText(r.pop_total)} residents
            {b.props?.area_km2 != null && <> · {fixed(b.props.area_km2, 2)} km²</>}
          </p>
        </div>
        <button type="button" className="drawer__close" aria-label={`Close ${b.name}`} onClick={onClose}>
          <Glyph name="close" />
        </button>
      </div>
      <div className="drawer__body">
        <section className="bp-highlight" aria-live="polite">
          <p className="bp-highlight__v">{pctText(share)}</p>
          <p className="bp-highlight__t">
            of residents can {verbOf(s)} to {servicePhrase(s.g)} within {limitOf(s)} minutes.
          </p>
          <p className="bp-highlight__avg">
            <Glyph name="clock" /> Typical {verbOf(s)}: <b>{minText(avg)}</b>
          </p>
        </section>
        <ServiceList b={b} groups={groups} s={s} title={`All services · ${s.m === "drive" ? "by car" : "walking"}`} />
        {!compact && <ServiceList b={b} groups={groups} s={other} title={`All services · ${other.m === "drive" ? "by car" : "walking"}`} />}
        <section className="bp-section">
          <h3>Mapped facilities in this barangay</h3>
          <ul className="fac-counts">
            {facs.map(([c, n]) => (
              <li key={c} data-zero={n === 0 || n === null ? "true" : undefined}>
                <span className="fac-dot" style={{ background: `var(--fac-${c})` }} aria-hidden="true" />
                <span>{facCatName(c)}</span>
                <b>{intText(n)}</b>
              </li>
            ))}
          </ul>
        </section>
        <section className={`bp-confidence bp-confidence--${rel.level}`}>
          <p>
            <b>Data confidence: {word}.</b> {text}
          </p>
        </section>
      </div>
      <div className="drawer__actions">
        {compact ? (
          <a className="btn btn--primary" href={href("barangays", { b: b.code })}>
            Full profile <Glyph name="arrowRight" />
          </a>
        ) : (
          <a className="btn btn--primary" href={href("map", { b: b.code })}>
            <Glyph name="pin" />
            Show on map
          </a>
        )}
      </div>
    </>
  );
}
