/** Project identity: mark, short name and full name. */
export const PROJECT = {
  name: "ABOT",
  fullName: "Geospatial Accessibility and Public Infrastructure Intelligence System",
  tagline: "Bringing essential services within reach.",
  phrase: "Mapping communities. Measuring accessibility. Informing better infrastructure decisions.",
  institution: "West Visayas State University",
} as const;

/** A location ring around a small network of nodes: places, links, reach. Decorative. */
export function Mark() {
  return (
    <svg className="brand__mark" viewBox="0 0 36 36" aria-hidden="true" focusable="false">
      <circle cx="18" cy="18" r="15" fill="none" stroke="currentColor" strokeWidth="2" opacity="0.55" />
      <path d="M11 22 L18 11 L25 21 Z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <circle cx="18" cy="11" r="2.6" fill="var(--color-highlight)" />
      <circle cx="11" cy="22" r="2.2" fill="currentColor" />
      <circle cx="25" cy="21" r="2.2" fill="currentColor" />
    </svg>
  );
}

/** The brand as the home link in the top bar; the full name hides visually (not for screen readers) when space is tight. */
export function Brand({ href }: { href: string }) {
  return (
    <a className="brand" href={href} aria-label={`${PROJECT.name} home: Overview`}>
      <Mark />
      <span className="brand__name">{PROJECT.name}</span>
      <span className="brand__full">{PROJECT.fullName}</span>
    </a>
  );
}
