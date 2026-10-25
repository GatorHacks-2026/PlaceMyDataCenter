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

## Gemini grounding trial with a temporary key

A user-authorized temporary Gemini key authenticated successfully against the
Google models endpoint. On 2026-10-24, a direct `gemini-2.5-flash:generateContent`
request returned HTTP 404 with Google's message that this model is no longer
available to new users. `gemini-2.5-flash-lite` returned the same kind of 404.
A `gemini-3.8-flash` request with Google Search grounding returned HTTP 429
`RESOURCE_EXHAUSTED` and pointed to plan and quota limits. No grounded source
URLs or claims were obtained. The temporary key was not saved in the repo.

An opt-in Gemini Google Search adapter now has mocked request and response
tests. Set `RESEARCH_SEARCH_PROVIDER=gemini` and `GEMINI_SEARCH_MODEL` only
after checking that the account can use the chosen model and grounding quota.
The adapter treats generated prose as a lead description; only cited URLs are
passed to the normal source collector, which fetches and checks page content.
This trial does not satisfy the live acceptance criteria.

## Remaining acceptance work

1. Configure a search provider with available quota (`BRAVE_SEARCH_API_KEY`, or
   an account and model that can run Gemini Google Search grounding) and run
   from a network that can reach the providers and public source pages.
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
