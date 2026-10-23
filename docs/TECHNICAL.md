# EcoCompute AI — Technical Description

> How the current codebase (through Phase 1A) is structured and how the pieces
> fit together. A forward-looking **Planned architecture** section at the end
> records decisions from `ROADMAP.md` that are not built yet.

Last updated: 2026-10-23

---

## Stack

| Concern      | Choice                                  |
| ------------ | --------------------------------------- |
| Build tool   | Vite 5                                  |
| UI framework | React 18 (+ StrictMode)                 |
| Language     | TypeScript 5 (strict)                   |
| Styling      | Tailwind CSS 3 + a little custom CSS    |
| Map          | MapLibre GL JS 4 (OSM raster tiles)     |
| Icons        | lucide-react                            |

Frontend-only (no backend/DB/AI). **As of Phase 1B there is one external network
dependency:** the Zippopotam.us ZIP geocoding API, called from the browser in
`src/data/geocode.ts`. No *environmental* data APIs yet — those arrive in Phase
3. A backend (FastAPI) is planned for Phase 2A; see **Planned architecture** at
the end of this file.

## Project layout

```
EcoDataCenter/
├─ index.html              # Vite entry, mounts #root
├─ vite.config.ts          # React plugin + server.host:true, port 5173
├─ tsconfig.json           # strict; includes src + vite.config.ts
├─ tailwind.config.js      # custom navy/teal palette
├─ postcss.config.js       # tailwindcss + autoprefixer
├─ package.json            # scripts: dev / build / preview
├─ docs/                   # <- handoff docs (this folder)
│  ├─ PROGRESS.md
│  ├─ ROADMAP.md
│  └─ TECHNICAL.md
└─ src/
   ├─ main.tsx             # React root wrapped in ErrorBoundary
   ├─ index.css            # maplibre css import + tailwind layers + slider/marker styles
   ├─ vite-env.d.ts
   ├─ App.tsx              # layout + all app state (single source of truth)
   ├─ components/
   │  ├─ MapPanel.tsx      # MapLibre map + markers (imperative, isolated DOM)
   │  ├─ ConfigPanel.tsx   # location, capacity + utilization sliders, cooling, stale/error, Analyze
   │  ├─ MetricsPanel.tsx  # four metric cards + assumptions line (adaptive units)
   │  └─ ErrorBoundary.tsx # fallback UI instead of blank screen
   └─ data/
      ├─ demo.ts           # types, LOCATIONS, COOLING_PRESETS, computeMetrics()
      ├─ geocode.ts        # Phase 1B: US ZIP -> Location via Zippopotam.us (external API)
      └─ demo.test.ts      # deterministic model tests (node --test, excluded from build)
```

## State & data flow (Phase 1A)

All state lives in `App.tsx` and flows down via props (no state library needed):

```
App  ── location, searchedLocations, capacity, utilization, cooling,
        result, error, stale, zipInput, zipSearching, zipError (useState)
 ├─ MapPanel      locations (presets + searched), selectedId, onSelect → setLocation + markStale
 ├─ ConfigPanel   capacity/utilization/cooling, stale, error, zip* props,
 │                onZipInputChange / onZipSearch / onCapacity|Utilization|CoolingChange / onAnalyze
 └─ MetricsPanel  result ({ metrics, assumptions } | null)
```

- **ZIP search (Phase 1B):** `onZipSearch` → `geocodeUsZip(zip, signal)`
  (`src/data/geocode.ts`). On success it appends to `searchedLocations`
  (de-duped), selects the new site, and marks results stale. An `AbortController`
  cancels any in-flight lookup. Errors surface as `zipError` in the config panel
  (`ZipNotFoundError` / `ZipLookupError`). `MapPanel` receives presets + searched
  as one `locations` array.

- Changing marker / capacity / utilization / cooling updates state **and** sets
  `stale = true` (only if a result already exists).
- **Analyze** → `computeMetrics({ location, capacityMW, utilization, cooling })`.
  On success: sets `result`, clears `error`/`stale`. On thrown validation error:
  sets `error` (shown in the config panel), leaves prior result untouched.
- `MetricsPanel` renders "—" while `result` is `null`, otherwise adaptive units
  plus an "Assumptions used" line (utilization, PUE, WUE, grid factor).

## The calculation (Phase 1A — modeled, documented)

In `src/data/demo.ts`. Transparent deterministic estimates (plausible
assumptions, not measured site data). Annual:

- `IT_energy_MWh       = capacity_MW × 8760 × utilization`
- `Facility_energy_MWh = IT_energy_MWh × PUE`
- `Water_L             = IT_energy_MWh × 1000 × WUE_L_per_kWh`
- `Carbon_tonnes       = Facility_energy_MWh × grid_factor_kgCO2e_per_MWh / 1000`

- Cooling presets (`COOLING_PRESETS`, editable): PUE + WUE per cooling type.
- Location carries `gridFactorKgPerMWh` (demo regional) + `droughtRisk` label.
- **Water does not use any water-stress factor**; it depends on IT energy and
  WUE only. Drought risk is a separate placeholder label.
- `computeMetrics` validates ranges (capacity 10–300 MW, utilization 0.3–1.0,
  PUE ≥ 1, WUE ≥ 0) and **throws** on invalid/NaN input (no silent zeroing).
- Returns `AnalysisResult = { metrics, assumptions }` so the UI can show exactly
  which assumptions produced the numbers.

### Tests

`src/data/demo.test.ts` — zero extra deps, Node 22 built-in runner:
`cmd /c "npm test"`. Covers scaling (capacity, utilization, PUE, WUE), water
independence from location, carbon conversion, a known-value check, and
invalid-input throwing. `src/**/*.test.ts` is excluded from `tsconfig.json`.

### Error handling

`src/components/ErrorBoundary.tsx` is used twice: once around the whole app in
`main.tsx`, and again around `MapPanel` in `App.tsx`. It takes an optional
`fallback` prop (used for the map-specific message) and otherwise shows a default
card with **Try again** (resets the boundary) and **Reload application** buttons.
The old temporary runtime overlay was removed.

## MapPanel — imperative MapLibre + 2D fallback

`MapPanel` renders one of two views and can switch between them at runtime:

- **3D MapLibre view (default when WebGL is available).** MapLibre manages its
  own DOM. Under React 18 StrictMode (dev), components mount → unmount → remount
  once; if MapLibre rendered into a React-managed node, the double teardown
  caused `removeChild` errors. Fix: the effect creates an **inner `<div>`
  imperatively**, hands that to MapLibre, and removes it on cleanup, so React
  only owns the outer wrapper. Markers are plain `<button>` elements; `onSelect`
  is kept in a ref so the init effect can stay `[]`-deps.
- **2D SVG fallback view (when WebGL is unavailable or the user toggles it).**
  A stylized continental-US SVG with clickable site markers and per-site selector
  cards. Preset sites use hand-tuned coordinates; searched (ZIP) sites are placed
  via `projectToSvg(lat,lng)`, a rough linear projection of the US bounding box
  (approximate by design). Selecting a site uses the same `onSelect(location)`
  contract as the 3D markers.

Markers are driven by the `locations` prop (presets + ZIP-searched). A
marker-sync effect adds MapLibre markers for sites that appear after init, and
selecting a site eases the 3D map to its coordinates.

WebGL safety: `isWebGLAvailable()` probes `maplibregl.supported` (when present)
plus a canvas WebGL context and never throws. MapLibre init is wrapped in
try/catch and listens for runtime `error` events; a WebGL/context failure flips
`useFallback` to the 2D view instead of crashing. A **2D ⇄ 3D toggle** and a
**Retry** control let the user switch manually. In `App.tsx`, `MapPanel` is also
wrapped in its own section-level `ErrorBoundary` with a map-specific `fallback`,
so a map failure degrades only that panel, not the whole app.

## Styling

- Tailwind utility classes throughout; custom palette (`navy.900/800/700/600`,
  `teal.accent`) in `tailwind.config.js`.
- `src/index.css` imports `maplibre-gl` CSS first, then Tailwind layers, then
  custom range-slider and marker/popup styling. `html,body,#root { height:100% }`
  so the `min-h-full` layout fills the viewport.
- Responsive: single column on small screens; `lg:` breakpoint switches to the
  5-column (3/2 ≈ 60/40) map+config split and 4-up metric cards.

## Commands (Windows / this environment)

PowerShell script execution is disabled, so call npm through cmd:

```
cmd /c "npm install"
cmd /c "npm run dev"       # http://localhost:5173/  (or 127.0.0.1)
cmd /c "npm run build"     # tsc && vite build -> dist/
cmd /c "npm run preview"   # serve the built dist/
```

Terminal stdout is garbled in this environment; redirect to a file and read it
(`cmd /c "npm run build > out.log 2>&1"`). An empty `tsc --noEmit` log = no errors.

## Gotchas for the next agent

- Don't re-run the interactive `npm create vite`; the project already exists.
- Keep `server.host: true` or the browser may show a blank page (IPv4/IPv6).
- Error handling now uses `ErrorBoundary.tsx` (the temporary overlay is gone).
- Carbon/drought stay labeled DEMO/PLACEHOLDER until real data lands (Phase 3).
- `npm test` needs Node 22+ (`--experimental-strip-types`); it adds no deps.

---

## Planned architecture (NOT built yet — from ROADMAP.md)

These are decisions recorded ahead of time so the next agent implements them
consistently. **Do not build any of this without explicit approval for that
phase.** Only `ROADMAP.md` defines scope/acceptance per phase.

### Phase 1B — ZIP / location search ✅ BUILT (2026-10-23)

- Decision taken: **Option B** (runtime geocoding API, Zippopotam.us) — the
  project's first external network dependency. Implemented in `src/data/geocode.ts`
  and wired through `App.tsx` / `ConfigPanel.tsx` / `MapPanel.tsx`. See the
  state-flow and MapPanel sections above and `PROGRESS.md` for details.

### Phase 2A — FastAPI backend (stack decision)

- The roadmap commits to **FastAPI (Python)** for the backend. This makes the
  repo **polyglot** (TypeScript frontend + Python backend). Planned layout:

  ```
  EcoDataCenter/
  ├─ frontend/   # the current Vite/React/TS app (today it lives at the repo root)
  └─ backend/    # FastAPI app, /api/estimate, Python tests
  ```

  Moving the existing app into `frontend/` is itself a step to plan carefully
  (paths, docs, commands). Until then, the app remains at the repo root.
- `/api/estimate` should host the same deterministic model now in
  `src/data/demo.ts`; the frontend calls it and renders the response. Keep the
  current `computeMetrics` as the reference implementation so results match.

### Testing as the stack grows

- Frontend model tests today are a zero-dep Node script (`npm test`). When the
  calculation moves to Python (2A), add a parallel **Python** test suite (e.g.
  `pytest`) for the backend formulas; keep both green and in agreement.

### Data provenance (Phase 3+)

- As real datasets arrive (Open-Meteo, US Drought Monitor, USGS, EIA, EPA
  eGRID), the UI must clearly separate **observed/sourced** values from
  **modeled** estimates, and display dataset year + geographic resolution.
