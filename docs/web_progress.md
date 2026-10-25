# Web App Progress — Frontend and Backend

**Status:** Current map work is recorded first; historical preview progress
follows. Research coverage is tracked in `RESEARCH_PIPELINE_PLAN.md` and
`RESEARCH_EVALUATION.md`.

**Current checkout:** `main`

Record completed work from `web.md` here. Individual tasks below may be done
without the whole phase being complete. Do not mark a phase complete until its
remaining tasks and "Done when" condition are verified.

## 2026-10-25 — Data Center Lens naming

- Renamed the visible app, browser title, PDF branding, and API docs to
  **Data Center Lens**. Updated package metadata and the current documentation
  titles. Existing import paths and the GitHub repository URL remain in place.

## 2026-10-25 — Warm light theme and guided entry

- Added a light theme with linen surfaces, pine and sage accents, clay alerts,
  and a persistent light/dark switch in the top header. Light is the default
  for new visitors; the existing dark palette remains available.
- Added a centered location question and a clear path into research before the
  neighborhood map. The same ZIP, city, or state input still feeds the existing
  research flow; screening and research behavior did not change.
- Kept the research-area, home-distance, and ring-explanation cards beside the
  satellite map. Moved the longer screening-data and facility-size cards below
  the whole map row so they no longer leave a blank area under the map.
- Verified the frontend production build and 15 frontend tests. Visual review
  remains for a browser with screen access.

## 2026-10-25 — Screening-grounded Agentic Battle

- Added live per-turn progress to the battle job and frontend. The existing
  polling API now returns completed messages and the current stage, so users
  can read the discussion while later agent calls run. Messages are labeled
  provisional until the unchanged script's final number check completes.
- Replaced the frontend's fixed debate, fixed scores, and prewritten verdict
  with a backend job that uses a completed site-screening result. The app shows
  the generated Sentinel/Catalyst conversation, bottom lines, full report, and
  any numbers the script could not match to its inputs.
- Source-linked claims from a completed research job in the same state are
  included in the agents' briefing. Only unambiguous reported permanent jobs
  and investment can populate the script's optional economic inputs; claims
  without evidence or marked conflicting are excluded.
- Added an adapter for the team's unchanged `dc_debate_agents.py` script. It
  passes site-screening values and assumptions while keeping the state energy
  proxy distinct from actual grid connection capacity. The deterministic
  screening verdict remains incomplete because capacity, water rights, and
  local noise law are not verified.
- Configured the supplied model key in the local, Git-ignored `.env`; the key
  is not in source control. Added LangChain dependencies and in-memory battle
  jobs with queue limits. The browser can print or save the generated report
  as PDF.
- Verified a live model request, a normal seven-message debate using sample
  screening data, the frontend production build, and 109 Python tests. One
  number in the sample debate was flagged as unverified, as intended. The full
  map-to-screening-to-battle path remains to be checked interactively.

## 2026-10-25 — Free keyless web discovery

- Added Tavily Search as the default source-lead provider using its free keyless API. A private Tavily key can raise limits; Brave and Gemini remain optional providers.
- City or resolved-ZIP location-only input may automatically investigate one candidate after fetching its page and checking project identity. Broad areas return candidate article links for the user to choose. Search snippets alone are never reported as reviewed evidence.
- Added explicit handling for keyless rate limits, offline provider and pipeline checks, and updated research intake copy.

## 2026-10-25 — Screening-grounded Playground

- Moved Playground beneath the satellite site screening and removed the separate demo Playground view.
- Playground waits for a completed screening, then uses its facility IT capacity, utilization, PUE, WUE, and available grid emissions factor as the baseline for backend scenario comparisons.
- Alternative capacity, utilization, PUE, WUE, and illustrative cooling presets compare modeled annual facility electricity, water consumption, and grid electricity carbon. Alternative average demand and peak water need are also shown beside the screened EIA proxy and assumed USGS flow threshold. These observations remain fixed context, not site-specific supply or local impact measurements.
- Changing the map inputs or pins clears the previous screening and Playground comparison. The fixed distance rings retain their distance-only meaning.

## 2026-10-25 — USGS and modeled noise map overlays

- Preserved latitude and longitude for analyzed USGS gauges in the water
  collector, and returned them with distance, dry-period flow, and which gauge
  was used for the screening comparison. No coordinates are invented when a
  gauge has no geometry.
- Returned the existing calculator's modeled night-noise threshold distance
  separately from the home-pin reading. The map now draws a dashed purple
  contour for that distance and a dashed cyan outline for the USGS gauge
  search radius. It plots the analyzed gauges and can zoom to the search area.
  The fixed 1/3/5-mile guides remain explicitly separate.
- Shared the map's facility-size input with site screening, separate from the
  illustrative Playground. Changing the input or pins clears stale screening
  overlays until screening runs again. A home pin cannot be placed at virtually
  the same point as the facility.
- Verified frontend build, targeted backend tests, a live FastAPI screening
  response with eight plotted Atlanta-area gauges and a 2.783-mile modeled
  noise contour, and the browser flow from research to map overlays. The
  gauge search area is not an impact boundary; modeled noise depends on
  assumed equipment and a comparison threshold.

## 2026-10-25 — Live screening API configuration

- Added backend startup loading for a root `.env` file, kept out of Git, and
  documented the EIA and USGS environment variables in `.env.example`.
- Configured the local backend with the provided keys. A live FastAPI screening
  job for a hypothetical 100 MW Atlanta site returned EIA electricity data
  (2024-09 through 2026-08) and a USGS discharge gauge with a 2025-10-25
  through 2026-10-25 sample. All four layers returned; water, carbon, and
  noise still depend on stated model assumptions. The EIA state energy proxy
  is not grid interconnection capacity, and the nearby gauge is not a water
  right or confirmed facility supply.
- Corrected the audit summary so pasted text is distinguished from public URLs.
  When no public URL was reviewed, the audit now says so prominently and
  reports if Brave discovery was unavailable. The frontend production build
  passed after this change.
- Brave search and Gemini extraction are not configured in the current local
  `.env`; pasted text alone cannot independently discover sources.

## 2026-10-25 — Site outline and calculation integration

- Added approximate ZIP (Census ZCTA) and state outlines from Census TIGERweb.
  City research can use a simplified OpenStreetMap city polygon when the
  geocoder supplies one. A ZIP entered by the user is marked as an unverified
  search area unless a reviewed project ZIP is found. The outline guides
  placement; it is not the facility location. A facility pin outside the
  available outline gets a warning.
- Connected the user-placed facility and optional home pins to a new site
  screening form. Only one sourced, non-conflicting **IT capacity** claim may
  prefill the form. Otherwise users explicitly choose a hypothetical IT MW.
- Added bounded background site-screening jobs behind FastAPI. The adapter
  runs the team's `Data_Center_backend.py` power, water, carbon, and noise
  calculations without changing research claims. It resolves the pin's state
  via Census, separates unavailable layers, and returns input assumptions,
  source labels, metrics, and limitations. Missing EIA key leaves power
  `not_checked`; no home pin leaves noise `not_checked`.
- Corrected the standalone USGS collector for the `[longitude, latitude]`
  geometry returned by `dataretrieval` when GeoPandas is absent. A live public
  USGS run returned eight Atlanta-area gauges.
- Verified the frontend build, 15 frontend tests, 102 Python tests, and live
  Census ZIP/state/point lookups. Browser checks covered a Texas article to
  El Paso city outline, ZIP 79901 as an explicitly unverified search area,
  pin placement, and a partial screening. An Atlanta run returned live USGS
  river data with a modeled water need; electricity stayed `not_checked`
  without an EIA key and noise stayed `not_checked` without a home pin.

## 2026-10-25 — Article-centered satellite distance view

- Removed the two ZIP comparison inputs from Playground. Research location
  remains in the shared intake field.
- A project-associated ZIP centers the satellite map on an approximate ZIP
  area; city and state research results center on broader approximate areas.
  None is silently treated as an exact facility coordinate.
- Users place a proposed facility and home on the satellite map. The app shows
  straight-line distance and fixed red 0–1, yellow 1–3, and blue 3–5 mile
  guides. These are proximity bands, not measured environmental effects.
- Added a satellite-view facility-size slider linked to Playground IT capacity.
  The rings stay fixed until a supported impact model can vary them.
- Verified the frontend build and 13 frontend tests. A live pasted-text
  research run identified Pine Island, MN, centered the map on its approximate
  city area, and kept the facility point unplaced. Browser placement of both
  pins produced a distance result. Playground has no ZIP inputs.

## 2026-10-25 — Citizen auditor frontend, first slice

- Reworked the dashboard shell using the supplied HTML as visual inspiration:
  compact header and shared location input, an article/PDF intake drawer,
  four evidence-count summary cards, and Map / Audit / Playground views.
- Added an Audit view driven by the existing research response. It shows
  source-linked claims, scoped missing information, conflicts, reviewed
  sources, copyable town hall questions, and optional full research narrative.
- Kept the MapLibre satellite map and illustrative simulator. The audit cards
  say "not found in reviewed sources" rather than implying information was
  withheld, and simulator values remain separate from project claims.
- A live pasted-text run for Pine Island, MN produced one reviewed source, one
  reported capacity claim, five tracked gaps, and tailored questions. The map
  still showed an approximate city center after switching views. Frontend
  build and 12 data tests passed.
- The next slices are human-scale impact views, cooling comparison charts,
  local environmental context adapters, and county ranking. No environmental
  or county fixture data was added in this slice.

## 2026-10-25 — Optional neighborhood distance view

- Kept MapLibre and added a default USGS imagery view with a Street switch.
- Added explicit user placement of a hypothetical site point and a home point.
  Geodesic 1-, 3-, and 5-mile guides and the displayed home distance are map
  exploration only, not claimed noise, water, or health impact zones.
- Placed points are local UI state, cleared on a new research result or selected
  location. Research intake, project matching, source collection, claims, and
  API contracts are unchanged. City/ZIP area centers are not silently used as
  facility coordinates; state-only research still has no facility marker.
- Verified 10 frontend tests, the production build, and 100 Python tests,
  including the state/article research regressions.
- The map now occupies a full row at every screen width. Research and simulator
  controls sit below it; on wide screens those two panels can share a row.

## 2026-10-25 — Separate project and resident ZIP comparison

- Split the simulator's project ZIP input from the research location text, and
  added a second ZIP input for the resident. The resident ZIP does not alter
  project matching, claims, or simulator factors.
- A selected research result fills the project ZIP only when its selected
  project has a ZIP; the user's search-area ZIP alone is not used. Users may
  choose a hypothetical project ZIP when none is available.
- Both ZIPs resolve through the existing public lookup. The map shows
  approximate ZIP centers, geodesic distance guides, and a center-to-center
  comparison. It does not claim a home is inside an impact zone from ZIPs.
- Verification: 12 frontend tests, a production build, and the existing Python
  research suite. The new frontend regression covers the search-ZIP versus
  project-ZIP distinction.

## 2026-10-24 — Research branch update

- `research-evidence-contract` now has a `ResearchPanel` in the active dashboard
  with location plus URL, pasted text, text-based PDF, or location-only input.
  `POST /api/research` and `POST /api/research/pdf` run the bounded research
  pipeline. The earlier investigation preview route remains available but is
  no longer the visible entry path.
- The research result shows project candidates, reviewed sources, source-linked
  claims, conflicts, missing fields, summary, and coverage limitations apart
  from the simulator's demo metrics.
- ZIP research resolves the user's ZIP to city/state search context while
  retaining the original ZIP and ZIP-area precision. Browser verification with
  `55963` plus Pine Island text identified the project and reported one sourced
  780 MW claim. Coverage correctly stayed partial without configured search or
  model providers.
- Verification after the ZIP fix: 80 Python tests passed; TypeScript and the
  frontend build passed. The then-open El Paso defect and multi-source
  discovery acceptance are recorded in `RESEARCH_EVALUATION.md`.

## 2026-10-24 — El Paso capacity classification fix

- Added a separate gas-generation claim so the proposed 366 MW plant is not
  compared with the 1,000 MW Meta data center as facility capacity.
- Added offline deterministic, model-output validation, and full pipeline
  regressions. The Python suite passed 84 tests. A live single-source El Paso
  rerun returned the two correctly separated figures with no conflict. It
  remained partial; multi-source discovery and developer attribution remain open.

## 2026-10-24 — Multi-source path without a search key

- The research form and both API input types accept up to five additional
  public source URLs. URL seed pages also supply bounded, project-relevant
  links as candidate sources. The collector still fetches, checks relevance,
  rejects duplicate text, and reports skipped URLs with reasons.
- A live El Paso run reviewed the article and the City of El Paso resource
  page with no Brave or Gemini key. The result remained partial: automatic
  general web search is not available, and the city page's phased water and
  investment details were not extracted into claims yet.
- Verification: 91 Python tests, 8 frontend model tests, and a frontend build
  passed. The existing MapLibre bundle warning remains non-blocking.

## 2026-10-24 — El Paso accuracy, scenario, map, and longer jobs

- A live two-source rerun identified Meta in El Paso, kept the 1,000 MW data
  center separate from the 366 MW gas plant, and extracted the City's Tier
  I–III average and maximum water allocations. The City's $1.5 billion
  infrastructure description and the article's $10 billion project value
  have separate fields and cited excerpts. Distinct water phases are explained
  differences, not unresolved contradictions.
- Added a research-specific scenario endpoint and form. Users enter IT MW,
  utilization, PUE, WUE, and optional grid emissions. No reported facility
  capacity is silently converted into IT load. The old simulator cards are
  explicitly illustrative and clear when their selected location changes.
- A selected city research result uses a cached, rate-limited city geocode to
  select an approximate map marker. State-only research removes the active
  marker and labels the broad area. The marker never claims to be a parcel.
- Added bounded background research jobs with queued/running/complete status;
  the frontend polls the result. Jobs are in-memory in this local prototype.
- PDF extraction can OCR image-only pages using local `pdftoppm` and
  `tesseract`, capped at 20 OCR pages. Both tools were installed/available in
  this development environment and a real scanned PDF produced extracted
  text. Deployment must provide the tools too.
- Remaining provider dependency: broad automatic web search still needs a
  working Brave key or a Gemini account with usable search quota. Explicit
  URLs and article-linked sources work without one. Broader live accuracy
  across other projects remains an evaluation task.

## 2026-10-24 — State-level article input

- Reproduced a user report: `Texas` plus the Inside Climate News El Paso URL
  returned no project because the article said "in northeast El Paso" rather
  than "El Paso, Texas". State-only identification now accepts a named city and
  developer when the same sentence identifies the state; two different Texas
  projects still return ambiguity. A live rerun with `Texas` and the article
  reviewed the source and identified Meta's El Paso project.
- The form now explains that a broad state works with a source naming one
  project, and that location-only discovery needs a configured search
  provider. Pasting only a URL into the text mode gives a direct correction.
- If location-only research has no search provider, the result is failed with
  a specific instruction to add an article, text, or PDF.

## 2026-10-24 — Source coverage display and provider test

- The research panel now keeps optional skipped-link and provider diagnostics
  collapsed by default. Reviewed sources and cited claims remain visible.
- A temporary Brave test token was checked against the official Web Search
  endpoint. Brave returned `SUBSCRIPTION_TOKEN_INVALID`; no search access was
  enabled, and the temporary local token file was removed. No token was saved
  in the repository.

## Existing foundation available before V1

- React/Vite dashboard, map and 2D fallback, ZIP search, capacity/utilization/
  cooling controls, modeled metric cards, and error states.
- FastAPI `POST /api/estimate` with Pydantic validation, deterministic model,
  and request/response logging. The frontend calls this endpoint.
- Phase 2A was committed on `main` as `c51b114`; the pivot branch builds on it.
- Existing verification recorded in `PROGRESS_2.md`: 8 frontend tests, 3 backend
  tests, and a production build passed before V1 planning.

## 2026-10-24 — Location and document preview

- Revised the V1 flow to accept one location plus one pasted document. Article
  discovery and Two Futures are future work. Updated `web.md` accordingly.
- Added a React investigation panel beside the existing map. It accepts ZIP,
  `City, ST`, or state input and one document, offers a clearly fictional
  example, and shows an expandable preview after submission.
- Added `POST /api/investigations/preview` in FastAPI. It validates the
  location and document length, returns location precision and the submitted
  text, and explicitly marks extraction and environmental context as awaiting
  integration. It does not invent facts or calculate project-specific impacts.
- Changing an input clears a stale preview and cancels an in-flight request.
- Added backend tests for supported location types, invalid/ambiguous input,
  document round-trip, and padded-short-text validation.
- Verification: frontend production build and 8/8 existing frontend tests
  passed; backend test suite passed 5/5. In the browser, the fictional sample
  submitted and expanded correctly, and city-only input returned a useful
  validation error. The existing large MapLibre bundle warning remains
  non-blocking.

## 2026-10-24 — Proposed-location ZIP lookup fix

- Confirmed that typing a ZIP into the investigation panel previously had no
  visible effect because only the separate simulator ZIP search was connected
  to the map, and investigation preview required document text.
- Added a `Locate ZIP on map` action to the investigation panel, available
  without a document. Enter also triggers it for a valid five-digit ZIP.
  It uses the existing ZIP lookup, selects the approximate centroid on the
  map, and shows loading, success, or error feedback.
- Browser verification: `10001` selected New York City with coordinates
  `40.7484, -73.9967`; `00000` showed a not-found error. Production build
  passed. City/state map resolution is still open.

## 2026-10-24 — Synchronized ZIP search fields

- Proposed location and Search by US ZIP now share the same ZIP query. Typing
  in either field updates the other; selecting a ZIP from either search updates
  the selected-location heading and map marker.
- Selecting a map marker updates Proposed location too. City/state text leaves
  the ZIP-only search field empty until a ZIP is entered.
- Browser verification: `10001` in Proposed location appeared in the lower ZIP
  field and selected New York City; `98101` entered in the lower field appeared
  above and selected Seattle. Frontend build and 8/8 tests passed.

## Still open

- **Phase 0:** Review and improve the visual boundary between the existing
  simulator's demo metrics and the new investigation preview.
- **Phase 1:** Decide whether a clear/reset control is needed; resolve
  city/state coordinates later when a geographic provider is chosen.
- **Phase 2:** Add sourced fact/unknown/conflict cards and a normalized
  extraction response after agreeing on the teammate contract.
- **Phase 3:** ZIP lookup is connected; city/state map resolution, location
  correction, and backend geographic provenance remain open.
- **Phases 4–6:** Teammate integration, project-specific metrics, community
  questions, and full team review remain open.

The text above this paragraph preserves the preview-era phase review. The
current research branch is tracked in the research plan and evaluation.

## Next task

Configure a usable search provider, then evaluate additional projects and
source recall. Move in-memory jobs to a persistent queue before multi-worker
deployment.
