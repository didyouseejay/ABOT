/**
 * Line icons for the public pages (24×24, stroke 2, after the Lucide set): one per service and a few
 * for the map controls. Always decorative: the text next to an icon names it.
 */
import type { ReactNode } from "react";

const G = {
  hospital: (
    <>
      <path d="M12 6v4M14 8h-4" />
      <path d="M18 22V5a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v17" />
      <path d="M14 22v-4a2 2 0 0 0-4 0v4M2 22h20" />
    </>
  ),
  clinic: (
    <>
      <path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7z" />
      <path d="M3.2 12h6.3l.5-1 2 4.5 2-7 1.5 3.5h5.3" />
    </>
  ),
  pill: (
    <>
      <path d="m10.5 20.5 10-10a5 5 0 1 0-7-7l-10 10a5 5 0 1 0 7 7z" />
      <path d="m8.5 8.5 7 7" />
    </>
  ),
  school: (
    <>
      <path d="M14 22v-4a2 2 0 1 0-4 0v4" />
      <path d="m18 10 4 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-8l4-2" />
      <path d="M18 5v17M6 5v17m-2-16 8-4 8 4" />
      <circle cx="12" cy="9" r="2" />
    </>
  ),
  cap: (
    <>
      <path d="M22 10 12 5 2 10l10 5z" />
      <path d="M6 12v5c3 3 9 3 12 0v-5M22 10v6" />
    </>
  ),
  shield: <path d="M20 13c0 5-3.5 7.5-7.7 9a1 1 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1z" />,
  flame: <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.4-.5-2-1-3-1-2.1-.2-4 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.2.4-2.3 1-3a2.5 2.5 0 0 0 2.5 2.5z" />,
  store: (
    <>
      <path d="M3 9 4.5 4h15L21 9" />
      <path d="M3 9h18v1.5a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0z" />
      <path d="M5 13v8h14v-8M10 21v-4h4v4" />
    </>
  ),
  cart: (
    <>
      <circle cx="8" cy="21" r="1" />
      <circle cx="19" cy="21" r="1" />
      <path d="M2 2h2l2.7 12.4a2 2 0 0 0 2 1.6h9.7a2 2 0 0 0 2-1.6L22 7H5.1" />
    </>
  ),
  bank: <path d="M3 22h18M6 18v-7m4 7v-7m4 7v-7m4 7v-7M12 2l8 5H4z" />,
  walk: (
    <>
      <circle cx="13" cy="4" r="2" />
      <path d="m9 20 3-6 3 3v4M7 11l3-3 3 1 2 3h3M12 14l-1-5" />
    </>
  ),
  car: (
    <>
      <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9L18 10l-2.7-3.6A2 2 0 0 0 13.7 6H8.3a2 2 0 0 0-1.7.9L4 10l-1.1.6A2 2 0 0 0 2 12.4V16c0 .6.4 1 1 1h2" />
      <circle cx="7" cy="17" r="2" />
      <circle cx="17" cy="17" r="2" />
      <path d="M9 17h6" />
    </>
  ),
  street: (
    <>
      <path d="M14.1 6.3 9.9 4.2a2 2 0 0 0-1.8 0L3.6 6.4A1 1 0 0 0 3 7.3v12.1a1 1 0 0 0 1.4.9l3.7-1.9a2 2 0 0 1 1.8 0l4.2 2.1a2 2 0 0 0 1.8 0l4.5-2.2a1 1 0 0 0 .6-.9V5.3a1 1 0 0 0-1.4-.9l-3.7 1.9a2 2 0 0 1-1.8 0z" />
      <path d="M15 6.8v14M9 3.2v14" />
    </>
  ),
  satellite: (
    <>
      <path d="m13.5 6.5-3.1-3.1a1.4 1.4 0 0 0-2 0L5.4 6.4a1.4 1.4 0 0 0 0 2l3.1 3.1M8 13l-3 3M17.5 10.5l3.1 3.1a1.4 1.4 0 0 1 0 2l-3 3a1.4 1.4 0 0 1-2 0l-3.1-3.1" />
      <path d="m9 15 1.5 1.5M16 3a5 5 0 0 1 5 5M16 7a1 1 0 0 1 1 1M9.5 9.5l5 5" />
    </>
  ),
  blank: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M9 21V9" />
    </>
  ),
  pin: (
    <>
      <path d="M20 10c0 5-5.5 10.2-7.4 11.8a1 1 0 0 1-1.2 0C9.5 20.2 4 15 4 10a8 8 0 0 1 16 0" />
      <circle cx="12" cy="10" r="3" />
    </>
  ),
  users: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </>
  ),
  list: <path d="M3 12h.01M3 18h.01M3 6h.01M8 12h13M8 18h13M8 6h13" />,
  arrowRight: <path d="M5 12h14m-7-7 7 7-7 7" />,
  search: (
    <>
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  sliders: <path d="M21 4h-7m-4 0H3m18 8h-9m-4 0H3m18 8h-5m-4 0H3M14 2v4M8 10v4m8 4v4" />,
  close: <path d="M18 6 6 18M6 6l12 12" />,
  info: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4m0-4h.01" />
    </>
  ),
  layers: (
    <>
      <path d="M12.8 2.2a2 2 0 0 0-1.6 0L2.6 6.1a1 1 0 0 0 0 1.8l8.6 3.9a2 2 0 0 0 1.6 0l8.6-3.9a1 1 0 0 0 0-1.8z" />
      <path d="m2 12 9.2 4.2a2 2 0 0 0 1.6 0L22 12M2 17l9.2 4.2a2 2 0 0 0 1.6 0L22 17" />
    </>
  ),
  externalLink: <path d="M15 3h6v6m-11 5L21 3m-3 10v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />,
  book: <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />,
} satisfies Record<string, ReactNode>;

export type GlyphName = keyof typeof G;

export function Glyph({ name, className = "glyph" }: { name: GlyphName; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {G[name]}
    </svg>
  );
}

const SERVICE_GLYPH: Record<string, GlyphName> = {
  health_hospital: "hospital",
  health_primary_care: "clinic",
  pharmacy: "pill",
  education_basic: "school",
  education_higher: "cap",
  safety_police: "shield",
  safety_fire: "flame",
  market_public: "store",
  market_supermarket: "cart",
  finance_bank: "bank",
};

export function ServiceGlyph({ id, className }: { id: string; className?: string }) {
  return <Glyph name={SERVICE_GLYPH[id] ?? "pin"} {...(className ? { className } : {})} />;
}
