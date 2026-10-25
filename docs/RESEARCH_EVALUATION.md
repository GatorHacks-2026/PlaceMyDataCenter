# Research pipeline evaluation

**Date:** 2026-10-24
**Branch:** `research-evidence-contract`

## Offline results

Run from the repository root after installing `backend/requirements-dev.txt`:

```sh
PYTHONPATH=backend python -m pytest scripts/tests backend/tests -q
npm test
npm run build
```

The Python suite passed **65 tests**. The frontend production build passed.
The pipeline tests use controlled search results and fetched documents rather
than representing them as live research.

| Scenario | Observed behavior |
| --- | --- |
| Pine Island article plus another project source | Keeps 780 MW facility, 1,400 MW wind, 200 MW solar, and 300 MW battery separate; result is partial while Gemini is unconfigured. |
| Another state (synthetic Ashburn, Virginia project) | Retains Virginia project sources and filters an unrelated Minnesota lead. Synthetic text is only a regression fixture. |
| Inaccessible article | Returns no reviewed source or claim from the blocked page; candidate leads and access warning remain explicit. |
| Search outage | Preserves seed evidence and marks coverage partial. |
| Duplicate and unrelated pages | Collection tests reject duplicate text and wrong-project content. |
| Conflicting figures and syndicated reports | Reconciliation tests keep conflicts visible and require independent origins for verified status. |
| Scanned/empty PDF | Input tests report a partial no-text result. |

## Live check attempted

The supplied [CNBC Pine Island article](https://www.cnbc.com/2026/10/19/how-data-centers-are-reshaping-americas-aging-grid-pine-island-minnesota-google.html)
was passed directly to `run_research` with `Pine Island, MN`. In this execution
environment, the article hostname could not be resolved and
`BRAVE_SEARCH_API_KEY` was absent. The returned result was `partial`, with zero
reviewed sources, zero claims, and explicit access and configuration warnings.
This is a correct failure report, not a successful live article evaluation.
`GEMINI_API_KEY` was also absent, so model extraction quality was not measured.

## Remaining acceptance work

1. Configure `BRAVE_SEARCH_API_KEY` and `GEMINI_API_KEY` in the backend process
   and run from a network that can reach the providers and public source pages.
2. Evaluate the supplied CNBC URL, one accessible alternative account of Pine
   Island, and projects in at least two other states. Record which source URLs
   were reviewed, rejected, or inaccessible and inspect every major claim.
3. If CNBC remains inaccessible, paste article text through the text mode and
   keep the pasted copy labeled as user supplied. Check that independently
   retrieved sources support or disagree with each material claim.
4. Review provider latency/cost and whether longer runs need a persistent job
   endpoint. The current request is bounded but synchronous.

Passing offline tests does not establish live source recall, model extraction
quality, or full research coverage. A `complete` result should be assessed
against the actual reviewed source list before any downstream use.
