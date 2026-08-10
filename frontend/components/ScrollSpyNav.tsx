"use client";

import { useEffect, useState } from "react";
import { Popover } from "./Popover";

export interface ScrollSpySection {
  id: string;
  number: string;
  label: string;
  /** Shown in the dot's popover — what this section actually contains. */
  description: string;
}

/**
 * Fixed vertical strip pinned to the left edge — a minimal scroll-spy table
 * of contents for ONE page's own numbered sections (01/02/03, matching
 * SectionHeading). Per-page, not a replacement for the top-level Nav.tsx
 * (predictions/players/coaching) — that stays a separate, ordinary nav bar.
 *
 * Each dot is a real click target on two levels at once: the <a href> still
 * does its native job (scrolls to the section, works with zero JS), and a
 * Popover layered on top (not preventing default) shows what that section
 * contains — real info on click, not hover, so this works on touch too.
 */
export function ScrollSpyNav({ sections }: { sections: ScrollSpySection[] }) {
  const [activeId, setActiveId] = useState(sections[0]?.id);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
          }
        }
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: 0 }
    );

    const elements = sections
      .map((s) => document.getElementById(s.id))
      .filter((el): el is HTMLElement => el !== null);
    elements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, [sections]);

  return (
    <nav
      aria-label="Section navigation"
      className="fixed left-0 top-1/2 z-40 hidden -translate-y-1/2 flex-col items-center gap-2 py-8 pl-3 md:flex"
    >
      {sections.map((s) => {
        const isActive = s.id === activeId;
        return (
          <Popover
            key={s.id}
            align="left"
            panelClassName="ml-2"
            renderTrigger={(triggerProps) => (
              <a
                href={`#${s.id}`}
                onClick={triggerProps.onClick}
                aria-expanded={triggerProps["aria-expanded"]}
                aria-controls={triggerProps["aria-controls"]}
                className="group flex flex-col items-center"
                aria-current={isActive ? "true" : undefined}
              >
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-full transition-colors duration-200 ease-out ${
                    isActive ? "bg-accent" : "bg-ink-muted/40 group-hover:bg-ink-muted"
                  }`}
                />
                <span className="flex h-24 w-4 items-center justify-center">
                  <span
                    className={`text-label origin-center -rotate-90 whitespace-nowrap text-[10px] transition-colors duration-200 ease-out ${
                      isActive ? "text-ink" : "text-ink-muted/50 group-hover:text-ink-muted"
                    }`}
                  >
                    {s.number} {s.label}
                  </span>
                </span>
              </a>
            )}
          >
            <p className="text-label text-accent">
              {s.number} {s.label}
            </p>
            <p className="prose-narrow mt-2 text-ink-muted">{s.description}</p>
          </Popover>
        );
      })}
    </nav>
  );
}
