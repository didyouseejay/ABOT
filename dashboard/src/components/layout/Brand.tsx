/** Project identity: mark, short name, full name and author; and the data licence notice. */
export const PROJECT = {
  name: "ABOT",
  fullName: "Geospatial Accessibility and Public Infrastructure Intelligence System",
  tagline: "Bringing essential services within reach.",
  phrase: "Mapping communities. Measuring accessibility. Informing better infrastructure decisions.",
  author: "Carl John L. Coopera",
  attribution: "An independent personal portfolio project by Carl John L. Coopera.",
  place: "Iloilo City",
} as const;

/** The published dataset (OpenStreetMap-derived) is a Derivative Database under the ODbL 1.0. */
export const DATA_LICENCE = {
  name: "ODbL 1.0",
  url: "https://opendatacommons.org/licenses/odbl/1-0/",
  releases: "https://github.com/didyouseejay/ABOT/releases",
  notice: "the ABOT dataset is made available under the Open Database License (ODbL) 1.0",
} as const;

/** A location ring around a small network of nodes: places, links, reach. Decorative. */
export function Mark() {
  return (
    <svg className="brand__mark" viewBox="0 0 36 36" aria-hidden="true" focusable="false">
      <rect width="36" height="36" rx="10" fill="var(--color-brand)" />
      <circle cx="18" cy="18" r="11.5" fill="none" stroke="#fff" strokeWidth="1.6" opacity="0.5" />
      <path d="M12.5 21.5 L18 13 L23.5 20.5 Z" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx="18" cy="13" r="2.3" fill="var(--color-highlight)" />
      <circle cx="12.5" cy="21.5" r="1.9" fill="#fff" />
      <circle cx="23.5" cy="20.5" r="1.9" fill="#fff" />
    </svg>
  );
}

/** The brand as the home link in the top bar. */
export function Brand({ href }: { href: string }) {
  return (
    <a className="brand" href={href} aria-label={`${PROJECT.name} home`}>
      <Mark />
      <span className="brand__text">
        <span className="brand__name">{PROJECT.name}</span>
        <span className="brand__sub">{PROJECT.place} · access to services</span>
      </span>
    </a>
  );
}
