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

The latest Python suite passed **75 tests**. The frontend production build passed.
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

A later run with permitted network access fetched 6,634 characters of article
text. The first live parse found the project but misattributed the article's
generic 25 MW and 1,000 MW examples as competing Pine Island capacities. That
was fixed by requiring local project context for data-center capacity claims,
with regression tests. The corrected run identified Google's proposed Pine
Island project and reported 780 MW data-center capacity, 1,400 MW wind, 200 MW
solar, and 300 MW battery power from the one fetched CNBC article. It produced
no capacity conflict. Coverage remained `partial`: no additional source was
retrieved, Gemini 2.5 search was unavailable to the tested account, and model
extraction fell back to deterministic rules. Water, cooling, tariff, generator,
and infrastructure-payer fields remained unreported in the structured output.

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

## El Paso live probe and reference source

The [Inside Climate News article about Meta's El Paso project](https://insideclimatenews.org/news/24092026/el-paso-electric-only-considered-gas-to-power-meta-data-center/)
is the next acceptance seed, with location `El Paso, TX`. A live probe fetched
9,951 characters and selected the Meta project. The result contained one
reviewed source and remained `partial` because no additional source was
collected. Deterministic extraction reported 1,000 MW and 366 MW as competing
data-center capacities and produced a false conflict. The article instead
describes a 1,000 MW data center and a proposed 366 MW gas plant serving it.
It also yielded a $10 billion investment claim; the scope and date of that
figure need to be retained during comparison with other sources.

The [City of El Paso data center resource page](https://www.elpasotexas.gov/data-centers)
is a public reference for the same Meta/Wurldwide project. It distinguishes
the 366 MW McCloud gas plant from the data center and lists water allocations:
Tier I average/maximum 100,000/300,000 gallons per day; Tier II
750,000/1,000,000; and Tier III 1,500,000/2,500,000. It also describes a
$1.5 billion infrastructure development, a December 2023 agreement, tax
incentives, and jobs. This page was inspected as a reference, but it has not
yet been retrieved by the research pipeline in a multi-source run. The
$1.5 billion and $10 billion descriptions cannot be treated as a confirmed
conflict without checking their scope and as-of dates.

The pipeline currently accepts one seed URL and discovers further URLs through
the selected search provider. It does not follow links from the seed page.
Brave could not run without a key, and the temporary Gemini grounding trial
returned no usable search results. Giving the pipeline this article alone
therefore does not currently demonstrate automatic cross-source scraping.

## Remaining acceptance work

1. Fix the El Paso 366 MW classification and add an offline regression test
   that keeps data-center capacity separate from generation serving the site.
2. Enable a usable discovery path: configure a search provider with available
   quota (`BRAVE_SEARCH_API_KEY`, or an account and model that can run Gemini
   Google Search grounding), or support an explicit additional-source URL.
   Run from a network that can reach public source pages.
3. Rerun El Paso with the article and city page. Verify the reviewed source
   list, phase-specific water claims, investment scope, and absence of a false
   MW conflict. Record rejected and inaccessible URLs as well as accepted ones.
4. Extend the live sample beyond the one-source CNBC run and El Paso probe to
   an accessible alternative Pine Island source and projects in another state.
   Inspect every major claim and the coverage limitations.
5. Review provider latency/cost and whether longer runs need a persistent job
   endpoint. The current request is bounded but synchronous.

Passing offline tests does not establish live source recall, model extraction
quality, or full research coverage. A `complete` result should be assessed
against the actual reviewed source list before any downstream use.
