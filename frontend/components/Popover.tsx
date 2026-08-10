"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/**
 * THE consistent interaction pattern for "click a name, see real info" across
 * the whole site: a popover anchored to the clicked element. Chosen over
 * inline-expand or a slide-over panel because it's the only one of the three
 * that fits every case asked for without changing shape — a scroll-spy dot,
 * a team chip, and a coach name are all small, inline, contextual triggers;
 * a popover stays anchored right where you clicked instead of pushing page
 * content around (inline expand) or requiring a whole new panel chrome
 * (slide-over) for what's usually 3-6 lines of information.
 *
 * Where a name already opens something bigger (RatingBreakdownCard's own
 * <details>, the coaching table row's team-season history), that native
 * disclosure stays as-is rather than being squeezed into a small popover —
 * same underlying principle (click, not hover, reveals real info), just
 * already served by an existing, better-suited affordance. See
 * frontend/AGENTS.md.
 *
 * Keyboard: Enter/Space on the trigger (native <button>, free), Escape
 * closes (handled here explicitly — unlike native <details>, nothing does
 * this for free). Click-outside also closes.
 */
export interface PopoverTriggerProps {
  onClick: (e: React.MouseEvent) => void;
  "aria-expanded": boolean;
  "aria-controls": string;
}

export function Popover({
  trigger,
  renderTrigger,
  children,
  panelClassName = "",
  align = "left",
}: {
  /** Simple case: plain content, auto-wrapped in the default styled trigger button. */
  trigger?: ReactNode;
  /** Advanced case: full control over the trigger element (e.g. ScrollSpyNav's
   * <a href> needs native scroll-to-anchor behavior AND a popover toggle). */
  renderTrigger?: (props: PopoverTriggerProps) => ReactNode;
  children: ReactNode;
  panelClassName?: string;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [open]);

  const triggerProps: PopoverTriggerProps = {
    onClick: () => setOpen((o) => !o),
    "aria-expanded": open,
    "aria-controls": panelId,
  };

  return (
    <span ref={containerRef} className="relative inline-block">
      {renderTrigger ? (
        renderTrigger(triggerProps)
      ) : (
        <button
          type="button"
          onClick={triggerProps.onClick}
          aria-expanded={open}
          aria-controls={panelId}
          className="cursor-pointer rounded-sm underline decoration-ink-muted/40 decoration-dotted underline-offset-4 transition-colors duration-200 ease-out hover:decoration-ink-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {trigger}
        </button>
      )}
      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-modal="false"
          className={`card animate-popover-in absolute top-full z-50 mt-2 w-72 text-sm shadow-[0_8px_30px_rgba(0,0,0,0.4)] ${
            align === "right" ? "right-0" : "left-0"
          } ${panelClassName}`}
        >
          {children}
        </div>
      )}
    </span>
  );
}
