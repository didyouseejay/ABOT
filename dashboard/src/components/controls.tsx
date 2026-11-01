/**
 * The selection controls of the public pages: which service, walking or by car, and the time limit.
 * Each writes the shared selection to the address, so it carries over between pages.
 */
import { serviceName } from "../model/labels.ts";
import { useView } from "../view.tsx";
import { Glyph } from "./glyphs.tsx";
import { Seg } from "./ui.tsx";

export function ServiceSelect({ id, groups, label = "Service" }: { id: string; groups: readonly string[]; label?: string }) {
  const { s, set } = useView();
  return (
    <label className="field" htmlFor={id}>
      <span className="field__label">{label}</span>
      <select className="select" id={id} value={s.g} onChange={(e) => set({ g: e.target.value })}>
        {groups.map((g) => (
          <option key={g} value={g}>
            {serviceName(g)}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ModeSwitch({ id, label = "Getting there" }: { id: string; label?: string }) {
  const { s, set } = useView();
  return (
    <Seg
      id={id}
      label={label}
      options={[
        ["walk", <><Glyph name="walk" />Walking</>],
        ["drive", <><Glyph name="car" />By car</>],
      ]}
      value={s.m}
      onChange={(v) => set({ m: v })}
    />
  );
}

export function TimeLimit({ id, walk, drive, label = "Within" }: { id: string; walk: readonly number[]; drive: readonly number[]; label?: string }) {
  const { s, set } = useView();
  const isDrive = s.m === "drive";
  const list = isDrive ? drive : walk;
  return (
    <Seg
      id={id}
      label={label}
      options={list.map((t) => [String(t), `${t} min`])}
      value={String(isDrive ? s.dt : s.t)}
      onChange={(v) => set(isDrive ? { dt: v } : { t: v })}
    />
  );
}
