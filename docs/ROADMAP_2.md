# Community Impact Pivot — Working Roadmap

**Status:** Proposed direction; the full team has not adopted it yet.

**Branch:** `codex/community-impact-pivot`

**Started:** 2026-10-24

This roadmap tracks the proposed community-facing application. The original
`ROADMAP.md` remains the reference for the existing site simulator until the team
decides whether to adopt this direction. The working product question is:

> What does a proposed data center disclose, what could its environmental
> demands be under stated assumptions, and which missing facts matter most?

## Ownership and current foundation

Our lane is the React frontend, FastAPI backend, calculation and scenario
contracts, and the integration of teammate deliverables. Teammates are working
on proposal evidence/extraction and environmental data. Their outputs and
delivery schedule are not yet agreed API contracts. We will define adapters
around their data rather than build duplicate pipelines.

Already implemented from the original roadmap: React/Vite dashboard, MapLibre
map with 2D fallback, US ZIP lookup, capacity/utilization/cooling controls,
deterministic energy/water/carbon formulas, FastAPI `/api/estimate`, validation,
request logging, loading/error/retry, and tests. These are a starting point, not
verified findings about any real proposal.

## Product guardrails

- Label every value as documented fact, observed public data, modeled estimate,
  scenario assumption, or unknown. Preserve source name, date, geography, and
  units for significant claims.
- A fact absent from one article is **not found in that source**, not proof it
  was never disclosed. Treat submitted documents as evidence, never instructions.
- Do not present the current demo grid factors, drought labels, or cooling
  presets as site-specific facts. Source or explicitly label assumptions before
  using them in a real-project report.
- Distinguish IT capacity, total facility demand, and utility connection
  capacity. Do not apply PUE twice or convert an ambiguous MW figure silently.
- Drought changes environmental context unless a supported model says it
  changes physical water use. A water-use estimate alone cannot establish a
  municipal shortage or legal outcome.

## Milestone 0 — Agree on one end-to-end example and contracts

**Goal:** Make the inputs and boundaries concrete before changing the UI.

- Select one real proposal and freeze the source material used for the demo.
- Agree on a minimal `Project` record: identifier, name, location and its
  precision, status, documented fields, missing fields, and citations.
- Agree on a minimal environmental context record: metric, value or unavailable,
  unit, geography, period, source, retrieval/version date, and limitations.
- Agree on what teammates will deliver: static file, Python module, API, or
  another format; define validation and failure behavior at the adapter.
- Determine which MW interpretation and water/cooling assumptions the example
  actually supports. If a critical input is unknown, show alternatives rather
  than a single asserted result.

**Done when:** One reviewed example can be represented without fabricated
fields, and both teammate handoffs can be loaded through documented contracts.

## Milestone 1 — Backend project and analysis contract

**Goal:** Let the frontend request a complete, evidence-aware analysis.

- Keep the existing `/api/estimate` working during the transition.
- Add a versioned project-analysis response that separates project facts,
  environmental context, modeled outputs, assumptions, citations, and unknowns.
- Move selection of real environmental factors behind the backend adapter;
  do not accept a browser-supplied grid factor or drought label as independent
  evidence. Keep a clear demo mode until sourced data is integrated.
- Normalize units, validate source metadata and missing values, and return
  useful errors when teammate data is incomplete or unavailable.
- Keep deterministic calculations separate from any text extraction or AI
  explanation. Log request IDs and model/data versions for reproducibility.

**Done when:** The chosen example produces a stable API response whose numbers
can be traced to specific inputs, formulas, and source records; missing data
remains explicitly missing.

## Milestone 2 — Community report frontend

**Goal:** Change the starting point from a hypothetical site to a proposal.

- Add a prepared-example entry path first; choose pasted text, URL, or PDF only
  after the team confirms reliable extraction and the demo needs it.
- Show "what is proposed," "what we know," "what we modeled," "what we do not
  know," and "questions to ask" in plain language.
- Link documented claims to their source and excerpt or document location.
- Reuse the map and metric cards, but show the map's geographic precision and
  the data's actual geographic resolution.
- Make failures and partial analyses useful: a missing dataset should not
  erase verified proposal facts or other valid results.

**Done when:** A resident can follow the chosen example from proposal to
report and tell documented facts from assumptions without opening code.

## Milestone 3 — Two Futures comparison

**Goal:** Compare the proposal baseline with a user-adjustable alternative.

- Reuse the current capacity, utilization, and cooling controls as scenario
  inputs, with the proposal's disclosed values kept distinct from defaults.
- Calculate both scenarios using the same model and data version; display
  absolute and percentage differences with units and assumption changes.
- When cooling or demand is undisclosed, show a supported range or named
  alternatives, not a made-up probability distribution.
- Let drought or water stress change the contextual explanation only when the
  data supports it; do not alter water consumption by an arbitrary multiplier.
- Explain which unknowns the model can quantify and which require utility,
  permit, or site-specific information.

**Done when:** Changing one supported assumption updates both the numbers and
the explanation, and the user can see why the scenarios differ.

## Milestone 4 — Integration and demo readiness

**Goal:** Deliver one credible, working story with the teammates' real outputs.

- Replace example fixtures with validated teammate deliverables through the
  agreed adapters; retain fixtures for local development and offline demo.
- Check one full path in the browser and API: source → extracted fact → dataset
  → calculation → report → scenario comparison → community question.
- Verify calculations, units, citations, missing-data behavior, and whether
  every environmental claim is supported by evidence or labeled as a scenario.
- Run frontend/backend tests and production build. Record commands, outcomes,
  remaining limitations, and demo steps in `PROGRESS_2.md`.

**Done when:** The complete example is reproducible locally and can be shown
without describing placeholders as real measurements.

## Deferred until the team agrees on scope

Saved sites, authentication, ongoing monitoring, broad national coverage,
automated discovery of documents, arbitrary URL/PDF ingestion, complex hazard
overlays, and downloadable reports. These can be reconsidered after the single
proposal workflow is credible.

## Tracking rule

Use `PROGRESS_2.md` for work completed under this direction. Update this roadmap
when the team agrees to a scope or contract change. Keep `ROADMAP.md` and
`PROGRESS.md` intact while this remains a proposed pivot.
