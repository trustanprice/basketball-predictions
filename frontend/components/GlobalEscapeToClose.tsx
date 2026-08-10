"use client";

import { useEffect } from "react";

/**
 * Escape closes any open native <details> element site-wide (MethodologyPanel,
 * RatingBreakdownCard, CoachingExplorer's per-season blocks). Native <details>
 * gets Enter/Space-to-toggle for free from the browser, but nothing closes it
 * on Escape — this is that missing piece, applied once, globally, rather than
 * duplicated per component. Popover.tsx handles its own Escape separately
 * (it's not a <details>).
 */
export function GlobalEscapeToClose() {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      document.querySelectorAll("details[open]").forEach((el) => {
        (el as HTMLDetailsElement).open = false;
      });
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return null;
}
