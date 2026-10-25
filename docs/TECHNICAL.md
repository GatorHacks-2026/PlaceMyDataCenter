# Data Center Lens — Technical Description

> How the current codebase (through Phase 2A) is structured and how the pieces
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
| API          | FastAPI + Pydantic (Python)             |

The frontend calls FastAPI for modeled estimates. ZIP geocoding still calls
Zippopotam.us directly from the browser in `src/data/geocode.ts`. There are no
environmental data APIs, database, authentication, or AI yet.

## Project layout

```
PlaceMyDataCenter/
├─ index.html              # Vite entry, mounts #root
├─ vite.config.ts          # React plugin + /api proxy to localhost:8000
├─ tsconfig.json           # strict; includes src + vite.config.ts
├─ tailwind.config.js      # custom navy/teal palette
├─ postcss.config.js       # tailwindcss + autoprefixer
├─ package.json            # scripts: dev / build / preview
├─ backend/
│  ├─ requirements.txt     # runtime Python packages
│  ├─ requirements-dev.txt # backend tests
│  ├─ app/main.py          # POST /api/estimate + validation + formulas
│  └─ tests/test_estimate.py
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
      ├─ estimate.ts       # /api/estimate client + response validation
      ├─ geocode.ts        # Phase 1B: US ZIP -> Location via Zippopotam.us (external API)
      └─ demo.test.ts      # deterministic model tests (node --test, excluded from build)
```

## State & data flow (Phase 2A)

All state lives in `App.tsx` and flows down via props (no state library needed):

```
App  ── location, searchedLocations, capacity, utilization, cooling,
        result, error, analyzing, stale, zipInput, zipSearching, zipError (useState)
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

- Changing marker / capacity / utilization / cooling updates state, marks
  results stale, and cancels an in-flight estimate.
- Initial load and **Analyze** call `requestEstimate()` → `POST /api/estimate`.
  On success, the API's metrics and assumptions replace the prior result. A
  failed request shows an error and Retry analysis; prior results remain visible.
  `src/data/estimate.ts` checks the response shape before rendering it.
- `MetricsPanel` renders "—" while `result` is `null`, otherwise adaptive units
  plus an "Assumptions used" line (utilization, PUE, WUE, grid factor).

## Estimate API (Phase 2A)

`backend/app/main.py` accepts the existing `AnalysisInput` shape in JSON and
returns the existing `AnalysisResult` shape. Pydantic rejects out-of-range,
non-finite, missing, and unknown values with HTTP 422. The model uses the same
8760-hour year, cooling PUE/WUE presets, and grid factor input as
`src/data/demo.ts`. The frontend calls only the API; the TypeScript calculation
remains for reference and parity tests. The backend does not call external APIs.

Vite dev and preview proxy `/api` to `http://127.0.0.1:8000`, so local browser
requests stay on one origin. Production deployment must provide the same route
or configure a suitable API origin and CORS policy. Run both processes using
the commands in `README.md`.

For each successful estimate, FastAPI logs a UTC timestamp, HTTP status,
calculation duration, validated input JSON, and output JSON through Uvicorn's
logger. Uvicorn's access log records method and path. The `README.md` command
uses `tee` to save console output to `backend/api.log` (ignored by Git). Only
the estimate payload is logged; authentication headers are not logged.

## The calculation (Phase 1A — modeled, documented)

Implemented in `backend/app/main.py`, with `src/data/demo.ts` retained as the
reference model. Transparent deterministic estimates (plausible
assumptions, not measured site data). Annual:

- `IT_energy_MWh       = capacity_MW × 8760 × utilization`
- `Facility_energy_MWh = IT_energy_MWh × PUE`
- `Water_L             = IT_energy_MWh × 1000 × WUE_L_per_kWh`
- `Carbon_tonnes       = Facility_energy_MWh × grid_factor_kgCO2e_per_MWh / 1000`

- Cooling presets (`COOLING_PRESETS`, editable): PUE + WUE per cooling type.
- Location carries `gridFactorKgPerMWh` (demo regional) + `droughtRisk` label.
- **Water does not use any water-stress factor**; it depends on IT energy and
  WUE only. Drought risk is a separate placeholder label.
- FastAPI validates ranges (capacity 10–300 MW, utilization 0.3–1.0,
  grid factor ≥ 0) before computing. Invalid JSON inputs return HTTP 422.
- Returns `AnalysisResult = { metrics, assumptions }` so the UI can show exactly
  which assumptions produced the numbers.

### Tests

`src/data/demo.test.ts` — zero extra deps, Node 22 built-in runner:
`npm test`. Covers scaling (capacity, utilization, PUE, WUE), water
independence from location, carbon conversion, a known-value check, and
invalid-input throwing. `src/**/*.test.ts` is excluded from `tsconfig.json`.
`backend/tests/test_estimate.py` tests the API result shape, known values,
cooling and location behavior, and HTTP 422 validation using pytest.

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

## Commands

See `README.md` for the two-terminal setup. Run FastAPI on port 8000 and Vite
on port 5173. The production build and Vite preview still need the backend
running for estimates. On the earlier Windows environment, PowerShell blocked
`npm.ps1`; use `cmd /c "npm ..."` there.

## Gotchas for the next agent

- Don't re-run the interactive `npm create vite`; the project already exists.
- Keep `server.host: true` or the browser may show a blank page (IPv4/IPv6).
- Error handling now uses `ErrorBoundary.tsx` (the temporary overlay is gone).
- Carbon/drought stay labeled DEMO/PLACEHOLDER until real data lands (Phase 3).
- `npm test` needs Node 22+ (`--experimental-strip-types`); it adds no deps.
- `backend/.venv/` is ignored by Git; `backend/` source is tracked in this repo.

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

### Phase 2A — FastAPI backend ✅ BUILT (2026-10-23)

- The TypeScript frontend remains at the repo root. FastAPI lives in the
  tracked `backend/` folder. `/api/estimate` hosts the deterministic model.

### Testing as the stack grows

- Frontend reference-model tests are a zero-dep Node script (`npm test`). The
  parallel Python API suite uses pytest. Keep both green and in agreement.

### Data provenance (Phase 3+)

- As real datasets arrive (Open-Meteo, US Drought Monitor, USGS, EIA, EPA
  eGRID), the UI must clearly separate **observed/sourced** values from
  **modeled** estimates, and display dataset year + geographic resolution.
