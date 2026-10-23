# EcoCompute AI

AI Data Center Sustainability Simulator. **Phase 0** = a local, frontend-only
dashboard prototype (Vite + React + TS + Tailwind + MapLibre). All figures are
clearly labeled **DEMO / PLACEHOLDER** values, not live measurements.

## Run it

> Windows note: PowerShell script execution is disabled here, so run npm via `cmd /c "..."`.

```
cmd /c "npm install"
cmd /c "npm run dev"     # open http://localhost:5173/
```

Build: `cmd /c "npm run build"` → output in `dist/`.

## What you can do

- Click a map marker (Gainesville FL, Phoenix AZ, Seattle WA) to select a site.
- Zoom/pan the map; set IT capacity (10–300 MW) and cooling type.
- Click **Analyze** to update the water and electricity estimates
  (carbon and drought are placeholders).

## Handoff docs (read these to continue the work)

- [`docs/PROGRESS.md`](docs/PROGRESS.md) — what's done, bugs fixed, env quirks.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — phased TODO (don't start future phases without approval).
- [`docs/TECHNICAL.md`](docs/TECHNICAL.md) — architecture, data flow, calculations, gotchas.
