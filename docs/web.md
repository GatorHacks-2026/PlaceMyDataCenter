# Web App Plan — Location and Document Flow

**Branch:** `community-impact-pivot`

**Scope:** Our React frontend and FastAPI backend. The user provides one
location and one pasted document. Teammates are building extraction and
environmental-factor logic; this plan gives their outputs stable places to
connect later. Two Futures is future work.

## V1 user journey

1. The user arrives at the existing dashboard and map. The old simulator
   remains available and labeled as a demo.
2. The user enters the most precise location they know: a five-digit ZIP,
   `City, ST`, or a state name/abbreviation. They paste one document as text.
3. The app validates both inputs, shows the interpreted location precision,
   and offers an expandable investigation preview.
4. The expanded view shows the submitted text and separate places for
   extracted facts, environmental context, modeled impacts, and unanswered
   questions. Sections without team logic say they are unavailable.
5. Once extraction and factors are integrated, the same view can display
   sourced facts and supported calculations. A user can correct or supply
   missing inputs without turning them into purported document facts.

**V1 input copy:** "Proposed location" with placeholder "ZIP, city and state,
or state"; "Document text" with placeholder "Paste one announcement, article,
or proposal excerpt here." Links and uploads are later options.

## Rules that protect accuracy

- A state is a broad search area, a city is approximate, and a ZIP is an
  approximate postal area. None is a verified project parcel, watershed, or
  utility territory. Do not move the map to an invented site coordinate.
- A missing field in one document means "not found in this document," not
  "never disclosed." Separate documented, user-entered, assumed, modeled,
  and unknown values.
- Until the extraction module is connected, do not claim to have read facts
  from arbitrary pasted text. The document preview can work while extraction
  and environmental context explicitly say "awaiting integration."
- The existing demo carbon factors, drought labels, and cooling presets are
  not project-specific evidence. Do not copy demo metrics into a project
  report as real findings.
- Treat pasted text as untrusted data, never instructions. Limit its size and
  avoid putting full document bodies in request logs.

## Phase 0 — Keep the current application usable

**Status: Partial.** The entry panel is in place; visual separation between
the simulator's default numbers and investigation results still needs review.

**Frontend**

- [x] Keep map, ZIP lookup, configuration controls, and simulator visible.
- [x] Add a separate investigation panel within the current dashboard.
- [ ] Make the distinction between simulator results and investigation
  results even clearer after project-specific results exist.

**Backend**

- [x] Keep `POST /api/estimate` working.

**Done when:** The first screen has both the map and new input path, and the
existing simulator still works.

## Phase 1 — Accept and validate one location plus one document

**Status: Partial.** Intake and validation work; the listed reset and location
resolution tasks remain open.

**Frontend**

- [x] Provide location input, pasted-text field, length feedback, submit,
  loading/error state, and a fictional example to try the UI.
- [x] Clear a prior preview and cancel its request when either input changes.
- [ ] Add a clear/reset control if team testing shows it is needed.

**Backend**

- [x] Add `POST /api/investigations/preview` with validated location and
  document text. V1 limits text to 20,000 characters.
- [x] Recognize ZIP, `City, ST`, and state input and return an explicit
  precision label. Reject ambiguous city-only input rather than guessing.
- [x] Return submitted text and section statuses without fabricated facts.
- [ ] Add a location resolver for city/state coordinates when we decide which
  geographic provider to use. Reuse existing ZIP lookup where suitable.

**Done when:** Valid inputs yield a preview and invalid/ambiguous inputs yield
clear errors, with no false project facts.

## Phase 2 — Expandable investigation view

**Status: Partial.** The document preview expands; sourced fact cards and the
teammate extraction contract are still open.

**Frontend**

- [x] Show a compact preview with Expand/Collapse analysis.
- [x] Show submitted text, interpreted location, and honest extraction/context
  waiting states in the expanded section.
- [ ] Add typed cards for facts, source excerpts, unknowns, and conflicts when
  the extractor's output contract is available.
- [ ] Make a partial response useful if one integrated service fails.

**Backend**

- [ ] Agree on a normalized extraction adapter with teammates: field name,
  value, unit, source span/document reference, status, and confidence or
  verification state. Keep missing values explicit.
- [ ] Add a versioned investigation response for extracted facts and errors
  without changing the intake contract.

**Done when:** Users can expand a result and tell submitted text, extracted
facts, and unavailable sections apart.

## Phase 3 — Link location to the map

**Status: Not started.**

**Frontend**

- [ ] For ZIP input, resolve the approximate ZIP centroid and select it on
  the existing map. Show a useful message if lookup fails.
- [ ] For city/state input, move the map only after the backend returns a
  resolved geographic location; for state input, retain state-level labeling.
- [ ] Allow the user to correct the location if extraction finds a different
  or more precise place in the document.

**Backend**

- [ ] Return resolved coordinates only with the location's actual precision
  and data source. Keep the user's original input alongside the resolution.

**Done when:** Map movement never implies more precise knowledge than the
location evidence provides.

## Phase 4 — Connect extraction and environmental factors

**Status: Not started.**

- [ ] Replace the extraction waiting state through a small adapter around the
  teammate module; preserve source spans, conflicting claims, and unknowns.
- [ ] Add environmental context records with value, unit, geography, period,
  source, and limitations through a separate adapter.
- [ ] Show loading, partial, unavailable, and retry states for each section.
- [ ] Never merge values from distinct projects merely because they share a
  city or state. If the document/location mismatch, ask the user to resolve it.

**Done when:** A submitted document can yield traceable facts and context;
missing teammate output leaves the rest of the preview usable.

## Phase 5 — Model only supported impacts

**Status: Not started.**

- [ ] Distinguish IT capacity, facility demand, and connection capacity.
  Require an explicit IT-capacity assumption before using the current model
  if the document does not establish it.
- [ ] Reuse the deterministic FastAPI calculations, return the exact inputs,
  model version, units, and assumptions, and mark scenario values as such.
- [ ] Show water/electricity estimates only where the inputs and model support
  them. Keep unsupported carbon, drought, local water supply, and rate impacts
  unavailable rather than filling them with demo factors.
- [ ] Write a few reviewed community questions tied to the actual unknowns.

**Done when:** A user can trace every displayed number or question to its
evidence, assumption, or explicit uncertainty.

## Phase 6 — Team review and verification

**Status: Not started.** Targeted checks of the intake slice do not count as
the full end-to-end review in this phase.

- [ ] Test ZIP, city/state, state-only, city-only, invalid location, short/long
  document, backend failure, changed inputs, and partial integration.
- [ ] Check narrow screens, map fallback, and original simulator behavior.
- [ ] Run relevant frontend/backend tests and production build. Record results
  and teammate feedback in `web_progress.md`.

**Done when:** The team can follow the whole location-and-document path and
identify the adapter inputs their modules need to provide.

## Later

Document URLs/uploads, multiple documents, automatic article discovery,
Two Futures, saved investigations, authentication, and report export can be
planned after the first complete investigation works.

## Tracking

Check off tasks only after implementation and mark a phase complete only after
its open tasks and "Done when" condition are verified. Finish the current phase,
record the result in `web_progress.md`, and stop for review before starting the
next phase. Some Phase 1 and 2 tasks were built early; complete and review
Phase 0 before doing more feature work. The other roadmap and progress files
remain higher-level or historical context.
