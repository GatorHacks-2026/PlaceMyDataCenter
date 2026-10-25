# Community Impact Pivot — Progress Log

> Historical progress through the initial pivot planning. For the implemented
> research pipeline and latest verification, see
> [RESEARCH_EVALUATION.md](RESEARCH_EVALUATION.md) and
> [web_progress.md](web_progress.md).

**Started:** 2026-10-24

**Status:** Planning and contract alignment; no pivot features implemented yet.

**Branch:** `community-impact-pivot`

This log records work toward the proposed community impact product in
`ROADMAP_2.md`. The original implementation history remains in `PROGRESS.md`.

## 2026-10-24 — Baseline secured

- Committed Phase 2A on `main` as `c51b114` (`feat(Phase 2A): Add FastAPI estimate service`).
- Created this branch from that commit. The existing `ROADMAP.md` and
  `PROGRESS.md` were kept for the teammate who has not reviewed the pivot.
- Reviewed the current React and FastAPI implementation against the new
  concept. The map, ZIP lookup, estimate engine, API request path, metric cards,
  and error handling can be reused. Proposal evidence, sourced environmental
  context, unknowns, community questions, and side-by-side scenarios are not
  implemented.
- Verification before the commit: frontend tests 8/8; backend tests 3/3;
  production build passed in the matching writable copy. The original checkout
  could not create Vite's temporary build file under the sandbox. The existing
  non-blocking MapLibre bundle-size warning remains.

## Current decisions

- Work on frontend, backend, and integration contracts in this branch while
  teammates prepare proposal extraction and environmental data.
- Preserve the original simulator and roadmap until the whole team decides on
  the product direction.
- Build one complete, source-backed proposal journey before adding broad
  ingestion or extra environmental categories.

## Open handoffs

1. Which real proposal and source documents will the team use for the first
   end-to-end example?
2. What structured fields, citations, and missing-value statuses will the
   proposal teammate deliver, and in what format?
3. What environmental datasets, geographic resolution, years, and source
   metadata will the data teammate deliver, and in what format?
4. Which reported capacity type, cooling assumptions, and water source details
   are available for that example?

## Next milestone

Complete Milestone 0 in `ROADMAP_2.md`: agree on the example and stable handoff
contracts. Backend response types and frontend report components follow those
contracts. Until then, existing demo factors and labels stay identified as
illustrative and must not be presented as real-project findings.
