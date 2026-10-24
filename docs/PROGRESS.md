# EcoCompute AI — Progress Log

> AI Data Center Sustainability Simulator. This file tracks what is **done**.
> For what's next, see `ROADMAP.md`. For how it works, see `TECHNICAL.md`.

Last updated: 2026-10-23

---

## Current status: Phase 2A COMPLETE ✅ (earlier phases below)

### Phase 2A — FastAPI backend foundation (2026-10-23)

- Added a tracked `backend/` folder in the same Git repository. The React app remains at the repository root; no Git history was moved.
- `POST /api/estimate` validates inputs with Pydantic and returns the same modeled metrics and assumptions as the prior TypeScript model. There is no database, authentication, or environmental API yet.
- The frontend now requests estimates from FastAPI on initial load and on Analyze. It shows a loading state, a useful error, and a retry button. Changing configuration cancels an in-flight estimate so old results cannot replace the current selection.
- Vite dev and preview proxy `/api` to `127.0.0.1:8000`. Production hosting must route `/api` to the backend.
- The original TypeScript `computeMetrics` remains as a reference implementation and its eight tests still pass; the UI no longer calls it.
- The API logs each estimate's timestamp, duration, validated request, and response in the backend terminal. `README.md` shows how to save these logs to the Git-ignored `backend/api.log` file.
- Verification: TypeScript and Vite build pass, eight frontend tests pass, three backend API tests pass, and a browser check confirmed Dry cooling updates the cards through the backend. The existing MapLibre bundle-size warning remains non-blocking.

Run the API and frontend using the commands in `README.md`.

---

### Phase 1B — ZIP / location search (2026-10-23)

Users can now analyze any US location by ZIP code, not just the three presets.

**Design decision (recorded):** we chose **Option B — a runtime geocoding API**
over a bundled local dataset. This is the project's **first external network
dependency**, deliberately crossing the earlier "no external APIs until Phase 3"
boundary. Still frontend-only (no backend).

- **Geocoder:** [Zippopotam.us](https://api.zippopotam.us/us/<zip>) — free,
  key-less, CORS-enabled, US ZIP support. Community-run, no SLA (acceptable for a
  demo; handled with full error states).
- **`src/data/geocode.ts`** (new): `isValidUsZip()` and `geocodeUsZip(zip, signal)`.
  Validates a 5-digit ZIP, fetches coordinates, and returns a `Location`
  (`id: zip-<zip>`, `source: 'search'`). Distinct error types —
  `ZipNotFoundError` (404 / no place) and `ZipLookupError` (network/parse/HTTP) —
  so the UI shows useful messages. Supports `AbortSignal` to cancel in-flight
  lookups. Never fabricates coordinates on failure.
- **`src/data/demo.ts`:** `Location` gained `source?: 'preset' | 'search'`;
  `DroughtRisk` now includes `'Unknown'`; added `DEFAULT_SEARCH_GRID_FACTOR` (400,
  demo). Searched sites use that placeholder grid factor and `droughtRisk:
  'Unknown'` until Phase 3 brings sourced per-location data.
- **`ConfigPanel.tsx`:** ZIP search box (numeric, 5-digit), Search button with a
  spinner, Enter-to-search, inline error text, a "Searched" badge on the selected
  location, and an "approximate ZIP centroid" disclaimer.
- **`App.tsx`:** keeps `searchedLocations` alongside presets, runs the lookup
  (with abort + de-dupe), selects the new site, marks results stale, and passes
  the combined list to the map.
- **`MapPanel.tsx`:** takes a `locations` prop (presets + searched). A
  marker-sync effect adds markers for sites that appear after init; selecting a
  site eases the 3D map to it. The 2D fallback projects any lat/lng onto the SVG
  (`projectToSvg`) so searched sites appear there too, and the drought color now
  handles `'Unknown'`.

**Behavior:** valid ZIP → new marker + selected site + map recenters, in both 3D
and 2D views; presets still work; invalid/unknown ZIP and network errors show
clear messages; water/electricity math is unaffected (location-independent),
carbon uses the demo placeholder grid factor, drought shows "Unknown".

**Verification** — `cmd /c "npm run build"` passes (BUILD_EXIT=0, 1580 modules,
tsc clean; only the non-blocking MapLibre chunk-size warning). `cmd /c "npm test"`
8/8 pass. Model tests unchanged and still green.

**Limitations** — depends on a third-party service reachable from the browser
(offline/blocked networks will error, by design). ZIP centroids are approximate.
Searched sites carry demo grid/drought placeholders until Phase 3. Only US ZIPs.

---

## Phase 1A COMPLETE ✅ (+ web-render fix, Phase 0 ✅ below)

### Phase 1A fix — WebGL/map fallback so it renders on the web (2026-10-23)

The Phase 1A build did not render in some browsers because MapLibre GL needs
WebGL, and WebGL failed to initialize in the target environment (e.g. disabled
GPU acceleration, a VM, or a browser shield), which crashed the map and left a
blank panel. An external pass (Antigravity) fixed this. Changes were confined to
**three files** — the calculation model, config panel, metrics panel, build
config, tests and styling were all left unchanged.

- **`src/components/MapPanel.tsx`** (main fix):
  - Added a safe `isWebGLAvailable()` check (uses `maplibregl.supported` when
    present, plus a canvas WebGL-context probe) that never throws.
  - Added a full **interactive 2D SVG fallback map** of the continental US with
    clickable site markers and per-site selector cards (showing grid factor and
    drought label). Used automatically when WebGL is unavailable.
  - MapLibre init is now wrapped in try/catch and listens for runtime `error`
    events; WebGL/context failures auto-switch to the 2D fallback instead of
    crashing. Cleanup is guarded against double-teardown errors.
  - Added a **2D ⇄ 3D toggle** (and a Retry control) so users can switch views.
- **`src/components/ErrorBoundary.tsx`**: added an optional `fallback` prop and a
  richer default view (now includes a "Reload application" button).
- **`src/App.tsx`**: wrapped `<MapPanel>` in an `ErrorBoundary` with a
  map-specific fallback, so a map failure degrades the panel instead of the whole
  app; also seeded `result` with an initial `computeMetrics(...)` so the metric
  cards show estimates on first load (no longer "—" until first Analyze).

**Verification (post-fix)** — `cmd /c "npm run build"` passes (EXIT=0, built in
~6s, only the non-blocking MapLibre chunk-size warning). `cmd /c "npm test"` 8/8
pass. Dev server serves on http://localhost:5173/.

**Note** — the metric cards now populate on load, so the Phase 0 "cards show —
until Analyze" behavior below no longer applies at startup; the stale banner
still appears after you change config.

### Phase 1A — Engineering calculations + UX polish (2026-10-23)

Replaced the illustrative Phase 0 formulas with transparent, deterministic
engineering estimates and added UX polish.

**Model** (annual; see `src/data/demo.ts` for documented units/assumptions):
- `IT_energy_MWh       = capacity_MW × 8760 × utilization`
- `Facility_energy_MWh = IT_energy_MWh × PUE`
- `Water_L             = IT_energy_MWh × 1000 × WUE_L_per_kWh`
- `Carbon_tonnes       = Facility_energy_MWh × grid_factor_kgCO2e_per_MWh / 1000`

Cooling presets (documented, editable in `COOLING_PRESETS`):
Evaporative PUE 1.2 / WUE 1.8 · Hybrid PUE 1.35 / WUE 0.9 · Dry PUE 1.5 / WUE 0.12.
Regional grid factors (kg CO₂e/MWh, demo): Gainesville 380, Phoenix 450, Seattle 120.

**Changes**
- Added **utilization** slider (30–100%, default 85%).
- `computeMetrics` now takes `AnalysisInput` and returns `AnalysisResult`
  (`metrics` + `assumptions`). Validates capacity/utilization/PUE/WUE and
  **throws on invalid input** (no silent zero coercion).
- Removed `waterStress` from physical water calc; water depends on IT energy
  and WUE only. Drought risk kept as a separate placeholder label.
- `Location` now carries `gridFactorKgPerMWh` (replaced `carbonFactor`/`waterStress`).
- UX: stale-results banner ("Configuration changed — click Analyze to update."),
  adaptive units (MWh/GWh, ML/GL, t/kt CO₂e), assumptions line under the cards,
  per-cooling PUE/WUE note in the config panel, and clear tags
  ("Modeled estimate" vs "Demo assumption"/"Placeholder").
- Replaced the temporary runtime overlay with a real **React error boundary**
  (`src/components/ErrorBoundary.tsx`).

**Tests** — `src/data/demo.test.ts`, zero extra deps (Node 22 built-in test
runner + `--experimental-strip-types`), run with `cmd /c "npm test"`.
Covers capacity & utilization scaling, PUE→facility energy, WUE→water,
water independent of location, carbon unit conversion, a known-value sanity
check, and invalid-input throwing. **8/8 pass.**

**Verification** — `cmd /c "npm run build"` passes (tsc clean; vite built 1579
modules; only a non-blocking "chunk > 500 kB" warning from MapLibre). `npm test`
8/8 pass. Note: `src/**/*.test.ts` is excluded from `tsconfig.json` so the app
build doesn't need `@types/node`.

**Limitations** — PUE/WUE/grid factors are plausible illustrative assumptions,
not measured site data; carbon/drought remain demo/placeholder. The 3D map needs
WebGL; where it's unavailable the app falls back to the 2D SVG map (which is a
stylized schematic, not a geographic projection). Map tiles still use public OSM.
No charts/ZIP/backend/API/DB/auth/AI (out of Phase 1A scope).

---

## Phase 0 COMPLETE ✅

A polished, functional, frontend-only prototype that runs locally in the
browser. No backend, no database, no AI, no external APIs yet (by design).

### What is implemented

- **Vite + React 18 + TypeScript** project, built manually (the interactive
  `npm create vite` scaffolder could not run non-interactively in this
  environment, so config + source files were authored directly).
- **Tailwind CSS v3** with a custom dark-navy / teal theme.
- **Responsive dashboard** (`src/App.tsx`):
  - Header: "EcoCompute AI" + subtitle "Smarter Infrastructure. Sustainable Future." + a "Phase 0 · Demo Data" badge.
  - Left panel (~60%): interactive **MapLibre GL** US map with clickable markers for Gainesville FL, Phoenix AZ, Seattle WA.
  - Right panel (~40%): selected location, IT capacity slider (10–300 MW, default 100), cooling selector (Evaporative / Hybrid / Dry), Analyze button.
  - Bottom: four metric cards — Annual Water Consumption, Annual Electricity Consumption, Carbon Emissions, Drought Risk.
- **Illustrative calculations** (`src/data/demo.ts`): water and electricity are
  computed from capacity + cooling + location factors. Carbon and drought are
  clearly labeled placeholders. Everything is tagged "Demo estimate" or
  "Placeholder" in the UI.
- **Interactivity**: clicking a marker selects a site; slider and cooling
  buttons update config state; **Analyze** recomputes and fills the metric cards.

### Verification performed

- `npm install` — succeeds (react, react-dom, maplibre-gl, lucide-react, tailwindcss, vite, typescript all present in node_modules).
- `npm run build` (`tsc && vite build`) — passes with **no TypeScript errors**; produces `dist/index.html` + hashed `dist/assets/index-*.css` and `index-*.js`.
- `npm run dev` — serves on http://localhost:5173/ and http://127.0.0.1:5173/.

### Bugs found and fixed during Phase 0

1. **Blank page via `localhost`** — Vite defaulted to a single loopback stack
   while the browser resolved `localhost` to the other (Windows IPv4 `127.0.0.1`
   vs IPv6 `::1`). Fix: `server: { host: true, port: 5173 }` in `vite.config.ts`.
2. **`removeChild` runtime error** — React StrictMode double-mounts in dev; its
   cleanup collided with MapLibre's own DOM teardown. Fix: MapLibre now renders
   into an **inner div created imperatively** inside `MapPanel`, so React never
   manages MapLibre's DOM children. See `src/components/MapPanel.tsx`.
3. Added a lightweight **runtime error overlay** in `src/main.tsx` so any
   client-side error renders on the page instead of a blank screen (useful for
   this headless-agent workflow; can be removed once a real error boundary is added).
4. **WebGL failure crashes entire dashboard (e.g. in Brave / VM / disabled GPU)** —
   When WebGL is disabled or blocked (such as Brave Shields or missing hardware acceleration),
   MapLibre GL failed during context creation (`Failed to initialize WebGL`), throwing an
   unhandled exception that caused the root `ErrorBoundary` to unmount the entire app and render
   a blank page with a red error card. Fix:
   - Added a safe `isWebGLAvailable()` pre-check in `src/components/MapPanel.tsx`.
   - Wrapped MapLibre instantiation in `try/catch` and added runtime error listeners to prevent
     crashing the component tree.
   - Built a sleek, fully-interactive 2D continental US vector map fallback with coordinate markers,
     hover tooltips, pulsing selected site indicators, and quick-select site cards.
   - Isolated `MapPanel` in its own section-level `ErrorBoundary` in `src/App.tsx`.
   - Pre-computed initial estimates on dashboard load so users immediately see valid data.

### Known, accepted Phase 0 behavior

- Metric cards show "—" until **Analyze** is clicked.
- After Analyze, changing config does **not** auto-refresh — click Analyze again.
  Phase 0 had no hint for this; **Phase 1A added a stale-results banner.**
- Map tiles come from the public OpenStreetMap tile server (no API key). Fine
  for a demo; a production app should use a proper tile provider / usage policy.

---

## Environment notes (important for the next agent)

- OS: **Windows**, shell: **PowerShell**, but PowerShell **script execution is
  disabled** (`npm.ps1` blocked). Run npm via `cmd /c "npm ..."` instead of
  `npm` directly.
- Terminal stdout echo is noisy/garbled in this environment. To read command
  output reliably, redirect to a file (`cmd /c "npm run build > out.log 2>&1"`)
  and open the file. An empty `tsc --noEmit` log means **no type errors**.
- Node v22.19.0, npm 10.9.3.
