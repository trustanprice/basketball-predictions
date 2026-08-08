# frontend/

Not yet scaffolded — this is a placeholder until Phase 6 (Next.js on Vercel, calling a real API
for win-model and live-ratings results). Recorded here so the constraint isn't lost before then:

- Reads pre-computed results from `backend/api/` over HTTP. It does **not** read
  `data/` or any dataframe directly — that was the old Streamlit pattern, and it's the thing
  this rewrite is moving off of.
- Deployed on Vercel from this subdirectory. Framework/router/styling choices (App Router vs.
  Pages, TypeScript, Tailwind, etc.) are undecided and will be recorded here once Phase 6
  starts — don't infer conventions from this stub, it intentionally has none yet.
