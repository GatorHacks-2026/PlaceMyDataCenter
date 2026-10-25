# Research pipeline evaluation

**Updated:** 2026-10-25
**Branch:** `research-evidence-contract`

## Offline results

Run from the repository root after installing `backend/requirements-dev.txt`:

```sh
PYTHONPATH=backend python -m pytest scripts/tests backend/tests -q
npm test
npm run build
```

The latest Python suite passed **100 tests**. The eight frontend model tests and
frontend production build passed. The build retains its MapLibre size warning.
The pipeline tests use controlled search results and fetched documents rather
than representing them as live research.

## ZIP research intake check

Research intake now resolves a supplied five-digit ZIP to city and state through
the public Zippopotam.us lookup before project matching and search. The result
retains the original ZIP, ZIP-area precision, and lookup provenance; it does
not treat the ZIP center as the facility address. A failed lookup remains
partial, and an explicitly supplied state that disagrees with the lookup is
rejected.

Offline tests cover the lookup response, an unknown ZIP, a mismatched state,
ZIP plus text project identification, and location-only candidate discovery.
The live lookup for example ZIP `55963` returned Pine Island, MN. Live article
discovery and extraction acceptance remain open below.

| Scenario | Observed behavior |
| --- | --- |
| Pine Island article plus another project source | Keeps 780 MW facility, 1,400 MW wind, 200 MW solar, and 300 MW battery separate; result is partial while Gemini is unconfigured. |
| Another state (synthetic Ashburn, Virginia project) | Retains Virginia project sources and filters an unrelated Minnesota lead. Synthetic text is only a regression fixture. |
| Inaccessible article | Returns no reviewed source or claim from the blocked page; candidate leads and access warning remain explicit. |
| Search outage | Preserves seed evidence and marks coverage partial. |
| Duplicate and unrelated pages | Collection tests reject duplicate text and wrong-project content. |
| Conflicting figures and syndicated reports | Reconciliation tests keep conflicts visible and require independent origins for verified status. |
| Scanned/empty PDF | Input tests report a partial no-text result. |

Scanned PDFs now use bounded OCR when Poppler and Tesseract are available; an
unreadable scan still returns a partial result.

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
is the next acceptance seed, with location `El Paso, TX`. An earlier live probe
fetched 9,951 characters and selected the Meta project. The result contained
one reviewed source and remained `partial` because no additional source was
collected. At that time, deterministic extraction reported 1,000 MW and 366 MW
as competing data-center capacities. The article instead describes a 1,000 MW
data center and a proposed 366 MW gas plant serving it. The classifier now
records the gas figure as `energy_plan.gas_generation_capacity_mw`, separate
from `electricity.capacity_mw`. Offline extraction and pipeline regressions
verify no false conflict. A live single-source rerun also returned 1,000 MW
data-center capacity and 366 MW gas-generation capacity with no conflicts.
It remained `partial` because search and Gemini extraction were unconfigured;
the project was labeled generically as a data center near El Paso rather than
attributing Meta as its developer.
It also yielded a $10 billion investment claim; the scope and date of that
figure need to be retained during comparison with other sources.

The [City of El Paso data center resource page](https://www.elpasotexas.gov/data-centers)
is a public reference for the same Meta/Wurldwide project. It distinguishes
the 366 MW McCloud gas plant from the data center and lists water allocations:
Tier I average/maximum 100,000/300,000 gallons per day; Tier II
750,000/1,000,000; and Tier III 1,500,000/2,500,000. It also describes a
$1.5 billion infrastructure development, a December 2023 agreement, tax
incentives, and jobs. This page was first inspected as a reference and was
later fetched by the pipeline through an explicit additional-source URL. The
$1.5 billion and $10 billion descriptions cannot be treated as a confirmed
conflict without checking their scope and as-of dates.

## Multi-source path without a search key

The pipeline now accepts up to five explicit additional public URLs with a seed
URL, text, or text-based PDF. It also treats relevant outgoing links in a seed
article as bounded leads. Each lead must pass the existing fetch, duplicate,
and project-relevance checks before appearing as a reviewed source. Skipped
URLs and access failures remain visible in limitations.

A live El Paso run supplied the Inside Climate News article and the City's
resource page. Both appeared as reviewed sources with separate URLs, without a
Brave or Gemini key. The result stayed `partial` because general web search was
unavailable and deterministic extraction has limited coverage. The article's
1,000 MW data-center and 366 MW gas-generation figures remained separate. The
City page's phased water allocations and $1.5 billion scoped investment were
not extracted into structured claims; that is the next accuracy issue.

The seed article's linked pages produced additional leads, but those tried in
this run were inaccessible or did not establish the target project under the
collector's checks. Following article links is bounded local discovery, not a
replacement for broad web search. Brave still needs a key, and the tested
Gemini account did not yield usable search results.

## Remaining acceptance work

State-only `Texas` plus the Inside Climate News URL now identifies the one
named Meta project in El Paso and reviews the article. A state containing
multiple candidate projects remains ambiguous. Location-only research needs
a configured search provider; the form explains this and suggests a URL, text,
or PDF when search is unavailable. The UI keeps skipped-link and provider
diagnostics in an optional collapsed section.

A temporary Brave test token was rejected by the Web Search endpoint as
`SUBSCRIPTION_TOKEN_INVALID`. It was removed locally and was never stored in
the repository. Broad automatic discovery therefore remains unverified.

The 2026-10-24 two-source rerun identified Meta, reviewed both the Inside
Climate News and City pages, and extracted the 1,000 MW data-center capacity,
366 MW gas plant, all six phase-specific water allocations, $10 billion
reported project value, and $1.5 billion infrastructure development. The
water tiers are distinct phase values; neither financial field is presented
as a like-for-like conflict. This is a validated two-source sample, not a
claim of complete recall across the web.

1. Configure a usable search provider with available quota for broader
   automatic discovery; explicit URLs and article links work without one.
2. Extend the live sample beyond the CNBC and El Paso runs to
   an accessible alternative Pine Island source and projects in another state.
   Inspect every major claim and the coverage limitations.
3. Measure provider latency/cost and move the new in-memory job queue to
   persistent storage before multi-worker deployment.

The frontend now polls bounded background jobs and offers a separate scenario
calculator using user-entered IT load and efficiency values. City research
places an approximate city marker; state-only research shows no facility
marker. Scanned PDF OCR works when Poppler and Tesseract are installed locally.

Passing offline tests does not establish live source recall, model extraction
quality, or full research coverage. A `complete` result should be assessed
against the actual reviewed source list before any downstream use.
