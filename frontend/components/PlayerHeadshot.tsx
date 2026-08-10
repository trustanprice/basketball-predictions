"use client";

import { useState } from "react";
import { headshotUrl } from "@/lib/headshots";

/**
 * A player's NBA.com headshot. Some player IDs 404 (recent draftees, players
 * with no current headshot on file) — on error this swaps to a simple
 * initials placeholder rather than showing a broken image icon, tracked in
 * client state since detecting the 404 needs onError.
 */
export function PlayerHeadshot({
  playerId,
  name,
  size = 40,
}: {
  playerId: number | string;
  name: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <span
        aria-hidden
        className="text-label inline-flex shrink-0 items-center justify-center rounded-full bg-line/10 text-[10px] text-ink-muted"
        style={{ width: size, height: size }}
      >
        {name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- external CDN, not an optimizable local/known-domain asset worth configuring next/image for
    <img
      src={headshotUrl(playerId)}
      alt={name}
      width={size}
      height={size}
      className="shrink-0 rounded-full bg-line/10 object-cover"
      style={{ width: size, height: size }}
      onError={() => setFailed(true)}
    />
  );
}
