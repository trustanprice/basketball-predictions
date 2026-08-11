# frontend/

Next.js (App Router, TypeScript, Tailwind) — read-only presentation layer over the Phase 5
API. No auth, no database, no server-side logic beyond calling that API. Deployed on Vercel
from this subdirectory.

## Conventions

- **All data fetching is server-side**, in `page.tsx` files (`async` Server Components calling
  `lib/api.ts`). Nothing fetches from the browser — `lib/api.ts` reads a plain `API_BASE_URL`
  env var (no `NEXT_PUBLIC_` prefix) specifically because it should never end up in the client
  bundle. Don't add a client-side fetch unless the feature genuinely needs live browser-side
  interactivity that server rendering can't provide — none of the current views do.
- **Client components (`"use client"`) are small, interactive islands**, not data-fetching
  wrappers: `PredictionsExplorer` (forecast card), `FeatureScatterChart` (hover tooltips + click
  to select), `CoachingExplorer` (click-to-expand coach history). Each receives already-fetched
  data as props from its parent Server Component page — it never calls `lib/api.ts` itself.
- **Team theme selection and team analysis selection are two deliberately separate states —
  do not re-link them.** This was previously one shared `selectedTeam` (picking a team in the nav
  both themed the site and changed what `PredictionsExplorer` displayed); that coupling was
  removed on purpose. Now:
  - `TeamThemeProvider`'s `selectedTeam` (nav's `NavTeamSelector`, persisted to `localStorage`) is
    **purely a visual theme choice** — it recolors the whole site (background and the amber
    accent both shift toward the selected team's colors, not just border/underline chrome
    anymore) but never determines what data is shown on any page.
  - `PredictionsExplorer` holds its **own separate local state** for which team's forecast is
    displayed, independent of the nav's theme selection. A user can have the site themed
    Cavaliers while viewing the Lakers' forecast — that's intended, not a bug to "fix" by
    re-syncing them.
  - The green "live/validated" and hollow "locked/future" status colors stay fixed regardless of
    team theme — those encode real data meaning and must stay visually distinct from whichever
    team color is active. Contrast-check before using a team's raw color as a large fill or body
    text color (several teams' colors are near-black/near-white — Nets, Bulls, Spurs); fall back
    to an accent/tint rather than a literal solid fill where that would hurt readability.
  - Players/Coaching pages: use judgment on how much of the theme bleeds into page content vs.
    just the nav/chrome — they aren't team-specific views the way predictions is, so don't force
    a full recolor of league-wide tables/rankings if it would misleadingly imply a filter that
    doesn't exist, but the nav and shared chrome should still reflect the selected theme.
- **Expand/collapse uses native `<details>`/`<summary>`** (`MethodologyPanel`,
  `RatingBreakdownCard`, and the per-season blocks in `CoachingExplorer`) instead of client
  state where the interaction is just open/closed — zero extra client JS. Reach for
  `useState` only when the interaction is genuinely more than that (the team dropdown, the
  chart's hover tooltip, coach-row click-to-filter).
- **No data-fetching library** (no SWR/React Query) — deliberate, not an oversight. Everything
  here is read-mostly; `lib/api.ts`'s `fetch(..., { next: { revalidate: 3600 } })` matches the
  backend's own ~1h staleness bound (see `backend/AGENTS.md`'s refresh strategy) via Next's
  built-in ISR. Don't add one without revisiting that reasoning first.
- **No charting library** — `FeatureScatterChart` is hand-rolled inline SVG. ~30 points and one
  tooltip doesn't justify a new dependency; revisit if a future chart needs more than that.
- **Player headshots** (`lib/headshots.ts`) come straight from NBA.com's own CDN
  (`cdn.nba.com/headshots/nba/latest/1040x760/{PLAYER_ID}.png`) — no API key, no new dependency.
  `PlayerHeadshot` is a plain `<img>`, not `next/image` (the CDN isn't in `next.config.ts`'s
  image domains, and it's not worth configuring for one external host); its `onError` swaps to
  an initials placeholder for the IDs that 404 (recent draftees, players with no headshot on
  file) rather than showing a broken image icon.
- **`lib/types.ts` mirrors `backend/api/schemas.py` by hand** — there's no shared schema
  generation between the two projects. When a Pydantic model changes, update the matching
  TypeScript interface in the same change; nothing will catch a drift automatically.
- **`next.config.ts` sets `agentRules: false`** — without it, `next dev`/`next build`
  regenerate a Next.js-authored `AGENTS.md` (and a `CLAUDE.md` stub) in this directory, which
  fights this file. If a future Next.js upgrade reintroduces the same behavior under a
  different flag, keep suppressing it — this project's `AGENTS.md` convention is per-directory
  and hand-maintained, not tool-generated.

## The scatter chart's axis selection (read this before touching `FeatureScatterChart`)

Axes are **not** hardcoded to specific feature names. It walks `metadata.top_feature_importance`
(rank order) and picks the first two features present for every team in the dataset being
plotted. Today that's `E_L`/`PLUS_MINUS`, not the true top-2 (`SOS`/`E_L`) — `SOS` is null for
every team in the current forecast season, a real backend data-pipeline gap (see
`backend/AGENTS.md`), not a frontend bug. The component detects this mismatch itself and renders
an explicit on-chart caveat naming which features were actually plotted — don't remove that
caveat or silently swap in different axes without it; a chart with unlabeled substituted axes is
worse than one that says what it's showing and why.

## Running locally

```bash
cd frontend
npm install
cp .env.example .env.local   # API_BASE_URL defaults to http://localhost:8000
npm run dev
```

Needs the backend API running separately (`uvicorn backend.api.main:app --port 8000` from the
repo root — see root `AGENTS.md`). The players page renders a "not available yet" state rather
than erroring if the backend hasn't completed its first player-ratings refresh — that's an
expected state on a fresh backend start, not a frontend bug either.

## Deployment (Vercel)

- Root Directory: `frontend/` (this is a monorepo — Vercel needs to be told to build from here,
  not the repo root).
- Env var: `API_BASE_URL` set to the deployed backend's URL (Render — see `backend/AGENTS.md`).
- Pages are statically prerendered with a 1h ISR revalidation window (see `lib/api.ts`), which
  means **the backend API must be reachable at Vercel build time**, not just at request time —
  a backend that's down during a Vercel deploy will fail that deploy's prerender step, not just
  serve stale data. Worth knowing before assuming a deploy failure is a frontend problem.
