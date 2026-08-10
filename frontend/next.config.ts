import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // This repo writes its own AGENTS.md per-directory (see root AGENTS.md's
  // documentation strategy) — don't let Next.js auto-generate/overwrite one,
  // and don't create a CLAUDE.md at all (not this project's convention).
  agentRules: false,
};

export default nextConfig;
