# EcoCompute AI — Development Roadmap

**Last updated:** 2026-10-23

**Development principle:** Implement one small phase, verify, update documentation, STOP, and wait for approval.

## Phase 0 — Frontend Prototype ✅ COMPLETE
- Responsive dashboard, interactive US map, 2D SVG fallback.
- Three demo locations, configuration controls, metric cards.
- Verified working prototype.

## Phase 1A — Engineering Calculations & UX ✅ COMPLETE
- Deterministic energy, water, and carbon calculations.
- Utilization slider, cooling presets, validation.
- Stale-results indicator, adaptive units, assumption labels.
- Error boundaries, WebGL fallback, automated tests (8/8).

## Phase 1B — ZIP Code & Location Search ✅ COMPLETE (2026-10-23)
**Goal:** Analyze user-selected locations anywhere in the United States.

Decision: resolved ZIPs via a **runtime geocoding API** (Zippopotam.us) —
**Option B**, the project's first external network dependency. Still
frontend-only. (Details in `PROGRESS.md`.)

Scope (all done):
- [x] Search by 5-digit US ZIP code.
- [x] Resolve ZIP to approximate coordinates via a public ZIP lookup service.
- [x] Select the searched location.
- [x] Update map marker, selected location, and configuration (marks stale).
- [x] Preserve existing demo calculations and labels.
- [x] Support both 2D fallback and MapLibre modes.
- [x] Handle invalid ZIPs, failed lookups, and loading states.

Acceptance (met):
- [x] Valid ZIP selects a location and moves the map.
- [x] Existing preset markers continue working.
- [x] Both map modes support selected locations.
- [x] Invalid ZIPs display useful errors.
- [x] Build and tests pass (8/8).

Out of scope (unchanged): Live environmental data, backend, database, AI,
geospatial watershed analysis.

## Phase 2A — Backend Foundation ⬜
**Goal:** Introduce a minimal API without changing the frontend experience.

Scope:
- FastAPI backend.
- `/api/estimate` endpoint.
- Move deterministic calculations server-side.
- Validate inputs and responses.
- Handle loading, failure, and retry states.

Acceptance:
- Existing frontend works with backend calculations.
- Formula tests pass.
- No regression in map or location search.

## Phase 2B — Saved Sites ⬜
**Goal:** Enable repeated use before implementing authentication.

Scope:
- Save, view, rename, and delete site configurations.
- Use browser localStorage initially.
- Restore saved configurations.
- Compare saved configurations with current inputs.

Acceptance:
- Saved sites persist after page refresh.
- Users can reopen and reanalyze sites.
- No login required.

## Phase 3A — Historical Weather ⬜
**Goal:** Integrate the first real environmental dataset.

Scope:
- Open-Meteo historical weather through FastAPI.
- Temperature and rainfall trends.
- Source dates, units, loading and error states.

Acceptance:
- Selected coordinates produce real historical weather charts.
- Demo calculations remain distinguishable from observations.

## Phase 3B — Drought Intelligence ⬜
**Goal:** Add historical drought exposure.

Scope:
- U.S. Drought Monitor data.
- Geographic matching and historical D0–D4 classifications.
- Drought history visualization.

Acceptance:
- Selected locations show sourced drought information.
- Missing or coarse-resolution data is clearly labeled.

## Phase 3C — Water Intelligence ⬜
**Goal:** Add local water-monitoring evidence.

Scope:
- USGS monitoring locations.
- Groundwater and streamflow observations.
- Station distances, timestamps, and data quality.

Acceptance:
- Users can inspect nearby stations.
- No unsupported claim about available water supply.

## Phase 3D — Energy & Carbon ⬜
**Goal:** Replace regional demo carbon assumptions with sourced estimates.

Scope:
- EIA electricity statistics.
- EPA eGRID emissions factors.
- Annual electricity cost and operational emissions estimates.

Acceptance:
- Energy and carbon results have traceable sources.
- Dataset year and geographic resolution are displayed.

## Phase 3E — Scenario Comparison ⬜
**Goal:** Compare infrastructure configurations.

Scope:
- Compare cooling technologies, capacity, and locations.
- Water, electricity, emissions, and cost trade-offs.
- Baseline-versus-alternative visualization.

Acceptance:
- At least three scenarios can be compared.
- Assumptions remain consistent between comparisons.

## Phase 4A — Environmental Monitoring ⬜
**Goal:** Turn saved sites into recurring-use assets.

Scope:
- Refresh environmental observations for saved sites.
- Store historical snapshots.
- Highlight changes since the previous analysis.

Acceptance:
- Users can see what changed over time.
- Historical measurements and modeled estimates remain separate.

## Phase 4B — AI Explanations ⬜
**Goal:** Explain environmental trade-offs.

Scope:
- Gemini integration through backend.
- Evidence-grounded scenario summaries.
- Uncertainty and missing-data explanations.

Acceptance:
- AI uses computed results and source records.
- No unsupported numerical claims.
- Calculations work when AI is unavailable.

## Phase 5 — Deployment & Hardening ⬜
- PDF reports.
- Production deployment.
- Reliable map tile provider.
- Security, integration tests, monitoring.
- Authentication only if required.
- End-to-end hackathon demonstration.

**Rule:** Do not implement any phase without explicit approval. Update PROGRESS.md, ROADMAP.md, and TECHNICAL.md after each completed phase.