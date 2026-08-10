/**
 * "01 SECTION TITLE" — the numbered section pattern used at every major
 * section break across all three views. `id` doubles as the ScrollSpyNav
 * anchor target for that section.
 */
export function SectionHeading({
  number,
  title,
  id,
  description,
}: {
  number: string;
  title: string;
  id?: string;
  description?: string;
}) {
  return (
    <div id={id} className="mb-6 flex scroll-mt-24 items-baseline gap-4">
      <span aria-hidden className="text-label pt-1 text-sm text-accent">
        {number}
      </span>
      <div>
        <h2 className="text-headline text-3xl sm:text-4xl">{title}</h2>
        {description && <p className="prose-narrow mt-2 text-ink-muted">{description}</p>}
      </div>
    </div>
  );
}
