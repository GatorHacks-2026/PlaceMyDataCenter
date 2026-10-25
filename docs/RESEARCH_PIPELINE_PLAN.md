# EcoCompute research pipeline plan

**Status:** Points 1–3 implemented; points 4–5 code and offline checks implemented, live provider checks pending.

## Goal

Given a location and an article URL, pasted text, or a text-based PDF, identify the
specific US data center project; discover relevant public sources; extract and
reconcile source-backed claims; and return a cited summary and structured result.
Location-only input should return candidate projects when a single project cannot
be identified. The article is a starting point, not the sole evidence source.

This plan extends the existing React/FastAPI application. The current
`POST /api/investigations/preview` remains a preview until the research endpoint
is implemented. The simulator's demo assumptions must never be presented as
facts about a researched project.

## Working example: Google Pine Island

Start with the CNBC article supplied by the user:

<https://www.cnbc.com/2026/10/19/how-data-centers-are-reshaping-americas-aging-grid-pine-island-minnesota-google.html>

The target is Google's proposed Pine Island, Minnesota facility. The article
also discusses broader grid issues, so claims about other facilities or the
industry must not be assigned to Pine Island. The case contains several MW
figures with different meanings: approximately 780 MW for the proposed data
center in CNBC's coverage, and 1,400 MW wind, 200 MW solar, and 300 MW battery
power in Google's announcement. They must remain separate claims, with their
source, subject, status, and context. The proposed Xcel electric service
agreement and related Minnesota regulatory material are research targets;
proposed terms must not be labeled approved.

### Baseline defects observed in the supplied extractor

The separate `/Users/jaysuryaray/Downloads/input_extractor.py` is useful
starting code, but it is not integrated into this backend. In local tests:

- A short CNBC-style snippet produced `stated_mw=780`, without saying what
  capacity that value measures.
- Text from Google's announcement produced `stated_mw=200`, incorrectly
  selecting the solar figure as the facility's power demand.
- A reordered example containing `1,900 MW` produced `stated_mw=900` because
  the regex does not handle comma-formatted numbers.
- Unresolved location input produced Gainesville, Florida coordinates.
- The local backend environment lacks BeautifulSoup and pypdf. A direct CNBC
  fetch failed in this sandbox; that is not evidence that a configured backend
  cannot access the article.

The prototype also lacks automatic URL discovery, project matching, source
records, claim reconciliation, and a complete `ActiveSiteContract` builder.

## Planned code layout

Place new research code in a Python package under `scripts/ecocompute_research/`.
Keep the FastAPI route in `backend/app/` as a thin adapter. Establish package
installation/import configuration before connecting the route.

| Planned file | Responsibility |
| --- | --- |
| `scripts/ecocompute_research/models.py` | Versioned Pydantic input, source, claim, conflict, missing-field, and result types. |
| `scripts/ecocompute_research/intake.py` | Validate input; reuse and improve URL, text, PDF, and location extraction. |
| `scripts/ecocompute_research/identity.py` | Identify one project or return ranked candidates and ambiguity. |
| `scripts/ecocompute_research/discovery.py` | Generate bounded queries and call a configurable web search provider. |
| `scripts/ecocompute_research/collection.py` | Fetch, deduplicate, clean, and record HTML/PDF sources. |
| `scripts/ecocompute_research/facts.py` | Extract typed, source-linked claims and normalize units. |
| `scripts/ecocompute_research/reconciliation.py` | Separate phases and capacity types; retain unresolved conflicts. |
| `scripts/ecocompute_research/estimates.py` | Configurable, explicitly provisional engineering proxies. |
| `scripts/ecocompute_research/report.py` | Missing-field audit, neutral questions, and cited summary. |
| `scripts/ecocompute_research/pipeline.py` | Orchestrate the stages and report partial/failed progress. |
| `backend/app/research.py` | FastAPI request validation and research endpoint. |
| `backend/tests/test_research_*.py` | Offline fixtures, unit tests, and API tests. |

These are planned boundaries, not files to create all at once. Reuse safe parts
of the supplied extractor rather than copying its defaults or treating its
summary document as proof that a function exists.

## Implementation sequence

Complete and review one point before starting the next. Record the result and
any changes to this plan after each point.

### 1. Contract and baseline fixture

- Define project identity, location precision, source metadata, and a claim
  structure with value, unit, subject, capacity kind where relevant, date,
  phase, evidence excerpt, and source ID.
- Represent `reported`, `verified`, `estimated`, `conflicting`, and `not_found`
  explicitly. Reserve `verified` for consistent independent evidence.
- Add a small, offline Pine Island fixture with 780/1,400/200/300 MW claims.
- Define a compatibility adapter for downstream `activeSite` consumers. The
  old contract must not force fabricated ZIP, county, coordinates, or MW.

**Done when:** A validated result can hold all four MW figures without
confusion, and missing fields remain null. No web or AI call is needed for the
test.

**Implementation:** `scripts/ecocompute_research/models.py` defines the
versioned evidence contract; `fixtures.py` contains the offline Pine Island
example; `legacy.py` projects only unambiguous values into nullable flat
`activeSite` fields. `scripts/tests/test_research_contract.py` checks MW subject
separation, source references, independent verification origins, conflicts,
null unknowns, and JSON round trips. The fixture cites an accessible report
quoting CNBC for 780 MW because the supplied CNBC article was not fetched.
This point has no API or live research behavior yet.

### 2. Dependable input and location handling

- Integrate the useful URL and PDF intake routines as separate functions. Add
  required dependencies. Introduce Gemini and deterministic claim extraction
  in point 5, once subjects and source references can be validated; the
  prototype's bare-number regex would mislabel Pine Island figures.
- Support URL plus location, text plus location, PDF plus location, and
  location-only input. Validate URL schemes and hosts, content size, PDF size,
  redirects, and timeouts before external fetching.
- Remove the Gainesville, fabricated county, dummy ZIP, and US-centroid
  fallbacks. Return unresolved or approximate locations honestly.
- Return a clear partial result when article access fails; permit pasted text
  or another accessible source as an input path.

**Done when:** All four input paths have offline tests, failed fetches are
explained, and unknown location details are not invented.

**Implementation:** `intake.py` validates and routes all four modes;
`location.py` parses US state, ZIP, city/state, county/state, and address/state
without supplying coordinates or county guesses; `url_fetch.py` checks public
URLs and redirects, bounds downloads, and reports access failures; `pdf_text.py`
extracts text-based PDFs and reports scanned/empty PDFs; `html_text.py` removes
common page chrome. `scripts/tests/test_intake.py` covers these paths offline,
including a generated text PDF with pypdf. The fetcher rejects local and
private addresses, but deployment still needs network egress controls against
DNS changes after validation. No live CNBC fetch or FastAPI research route is
part of this point.

### 3. Project identification

- Extract project name, developer/operator, aliases, location, and dates from
  the seed input.
- Match source mentions to the same facility, not merely the same company or
  state. Return candidates when a state-wide or multi-project input is
  ambiguous.

**Done when:** The Pine Island article selects Pine Island without absorbing
other Google projects or general grid claims.

**Implementation:** `identity.py` extracts conservative project candidates
from seed sentences, records explicit developer/operator/alias/date details,
and compares each candidate with the user's location. A city match selects
one facility; multiple same-state candidates remain ambiguous for a state-only
input. Generic grid discussion and location mismatches do not become a chosen
project. This is a deterministic first pass; more varied article language may
need structured extraction in point 5. `scripts/tests/test_identity.py` covers
Pine Island, same-company different-site mentions, ambiguity, and mismatch.

### 4. Web discovery and source collection

- Choose and configure a real search provider. Search project identity plus
  utility, water, permitting, environmental, financial, and community terms.
- Prioritize company, city/county, utility, and regulator records; preserve
  independent news reporting as separately attributed evidence.
- Deduplicate URLs and near-identical text, score project relevance, and
  enforce source, query, time, retry, cache, and rate limits.
- Store title, URL, publication date if known, retrieval time, content type,
  access status, and text/evidence references for each source.
- Respect access restrictions; do not misrepresent a blocked page as reviewed.

**Done when:** A configured run discovers relevant sources beyond the input,
and unavailable search produces an explicitly partial result.

**Implementation:** `discovery.py` builds bounded project-specific queries and
uses the Brave Web Search API when `BRAVE_SEARCH_API_KEY` is set. It deduplicates
URLs and scores leads against the facility location. `collection.py` fetches
bounded sources, retries transient failures, caches results within a run,
rejects unrelated facilities and duplicate text, and records retrieval time
and source URL. `scripts/tests/test_discovery_collection.py` exercises the
provider request shape, outage behavior, project filtering, deduplication,
and collection failures with offline transports. The implementation uses the
[Brave Web Search API reference](https://api-dashboard.search.brave.com/api-reference/web/search/get).
No Brave key is available in this checkout, so live discovery remains an
acceptance check. Search snippets are leads, not verified evidence.

### 5. Typed fact extraction

- Extract claims source by source with Gemini where configured and a limited
  deterministic fallback. Validate model output against the schema.
- Classify MW by subject: data center load, IT capacity, facility capacity,
  grid connection, wind, solar, battery power, and unknown. Preserve the
  original sentence and reported units.
- Cover project, electricity, water, environment, financial, and community
  categories without turning broad regional facts into site disclosures.
- Fix comma-formatted numbers and distinguish numbers with the same unit but
  different meaning.

**Done when:** The Pine Island fixture never treats 200, 300, 1,400, or 1,900
MW as the data center's 780 MW capacity; unsupported fields remain unknown.

**Implementation:** `facts.py` provides a deliberately narrow regex fallback
for explicitly contextualized MW, daily water, investment, and permanent jobs.
`gemini.py` sends one bounded source chunk at a time to a configurable Gemini
model, requests JSON, and rejects claims whose excerpt is absent from the
source or whose MW value/subject contradicts its excerpt. `fact_extractor.py`
uses the fallback when Gemini is unavailable. Offline tests cover Pine Island
MW separation, multi-project articles, a model misclassification, and model
failure. The model adapter follows the [Gemini structured output reference](https://ai.google.dev/gemini-api/docs/structured-output?lang=web).
No Gemini key is available in this checkout, so live extraction quality has
not been assessed. The deterministic fallback does not claim comprehensive
environmental or tariff extraction.

### 6. Reconciliation, estimates, and report

- Compare claims by subject, date, phase, proposed/approved state, capacity
  kind, and source independence. Keep genuine disagreements visible.
- Keep proxy MW formulas configurable and label their assumptions. A baseline
  scenario is a user assumption, not a project-specific finding.
- Generate a cited summary, missing-information audit, and neutral questions
  for residents. Say `not found in reviewed sources` unless evidence supports
  a stronger statement.

**Done when:** Each significant statement in the report has evidence or an
estimate label; conflicting cost and tariff claims are attributed separately.

### 7. API and frontend integration

- Add a research API with validation and a path toward progress/job retrieval.
- Show source-backed results apart from the simulator's demo metrics. Preserve
  `POST /api/investigations/preview` until the new flow replaces it safely.
- Feed downstream modules through a validated adapter, including capacity
  kind and source/provenance checks.

**Done when:** One article plus location produces inspectable sources, claims,
unknowns, and a summary in the app without presenting demo values as facts.

### 8. End-to-end evaluation

- Use Pine Island and additional projects in other states. Mock external
  services in routine tests; use a small, documented live evaluation separately.
- Check inaccessible articles, duplicate coverage, unrelated projects,
  contradictory figures, scanned PDFs, and search-provider outages.

**Done when:** The live evaluation finds relevant additional sources where
available, reports its research coverage and limitations, and passes the
offline regression suite.

## Decisions before their corresponding implementation point

- Select the search provider and acceptable per-investigation cost/latency
  before point 4.
- Decide whether the first API run is synchronous or uses a background job
  before point 7; design the result schema for either path in point 1.
- Review compatibility needs with the teammates consuming `activeSite` before
  finalizing its adapter in point 1.

## Next action

Review this plan, then implement **point 1 only**: the evidence contract and
offline Pine Island fixture. Do not start discovery or frontend changes until
that contract is reviewed.
