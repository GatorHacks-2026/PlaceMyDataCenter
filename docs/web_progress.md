# Web App Progress — Frontend and Backend

**Status:** Phase 0 partial; Phase 1 partial; Phase 2 partial; Phases 3–6 not started.

**Branch:** `community-impact-pivot`

Record completed work from `web.md` here. Individual tasks below may be done
without the whole phase being complete. Do not mark a phase complete until its
remaining tasks and "Done when" condition are verified.

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

## Still open

- **Phase 0:** Review and improve the visual boundary between the existing
  simulator's demo metrics and the new investigation preview.
- **Phase 1:** Decide whether a clear/reset control is needed; resolve
  city/state coordinates later when a geographic provider is chosen.
- **Phase 2:** Add sourced fact/unknown/conflict cards and a normalized
  extraction response after agreeing on the teammate contract.
- **Phases 3–6:** No phase-level implementation yet. Map synchronization,
  teammate integration, project-specific metrics, community questions, and
  full team review remain open.

The first coding pass crossed Phase 0–2 task boundaries before the phase-by-
phase review. No further feature phase should begin until the current phase is
finished, recorded here, and reviewed.

## Next task

Finish and review **Phase 0** only: make the simulator and investigation
outputs unmistakably separate. Then proceed one phase at a time.
