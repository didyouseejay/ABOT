import type { ReactNode } from "react";

export const PAGE_TITLE_ID = "page-title";

/** Every page: an eyebrow, one h1 (the focus target after navigation), an optional lead, content. */
export function PageContainer({ eyebrow, title, lead, children }: { eyebrow?: string; title: string; lead?: string; children?: ReactNode }) {
  return (
    <article className="page" aria-labelledby={PAGE_TITLE_ID}>
      <header className="page__header">
        {eyebrow && <p className="page__eyebrow">{eyebrow}</p>}
        <h1 id={PAGE_TITLE_ID} tabIndex={-1}>
          {title}
        </h1>
        {lead && <p className="page__lead">{lead}</p>}
      </header>
      {children}
    </article>
  );
}
