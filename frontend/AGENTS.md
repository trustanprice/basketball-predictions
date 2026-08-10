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
- **Team selection is global, not per-page.** `TeamThemeProvider` (wraps the whole app in
  `layout.tsx`) holds the one `selectedTeam` used everywhere, persisted to `localStorage`.
  `NavTeamSelector` (in the nav, every page) is the only picker — pages don't have their own.
  `PredictionsExplorer`'s forecast card and `FeatureScatterChart`'s clickable points both read/
  write this same context (`useTeamTheme()`); clicking a scatter point isn't "a second picker,"
  it's another way to change the one global selection. Team color is scoped to identity chrome
  only (a border, dot, or underline) — never the amber section/key-stat accent or the green
  positive/hollow-locked status colors, see `lib/teamColors.ts`. Players/Coaching pages
  deliberately don't re-theme their content on selection (only the nav selector itself shows the
  color) — they aren't team-specific views, and re-theming league-wide tables/rankings by a
  selected team would misleadingly imply a filter that doesn't exist.
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
