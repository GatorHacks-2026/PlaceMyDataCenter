# EcoCompute research pipeline plan

**Status (2026-10-25):** Points 1–7 are implemented, including background
research jobs, local PDF OCR, a separate project scenario, and approximate
city/state map placement. Point 8 has 100 passing Python tests, eight frontend
tests, a production build, and live Pine Island and two-source El Paso checks.
Broader automatic discovery and recall across more projects remain unverified
without a working search subscription.

An optional Gemini Google Search provider was added after point 8. It is
explicitly selected with `RESEARCH_SEARCH_PROVIDER=gemini`; it is not a
validated replacement for Brave yet because the tested account cannot use
2.5 Flash and lacks 3.8 grounding quota. See the evaluation record.

## Goal

Given a location and an article URL, pasted text, or a PDF, identify the
specific US data center project; discover relevant public sources; extract and
reconcile source-backed claims; and return a cited summary and structured result.
Location-only input should return candidate projects when a single project cannot
be identified. The article is a starting point, not the sole evidence source.

This plan extends the existing React/FastAPI application. The current
`POST /api/investigations/preview` remains a preview; the separate
`POST /api/research` and `POST /api/research/pdf` endpoints now expose the
research pipeline. The simulator's demo assumptions must never be presented
as facts about a researched project.

The frontend now uses background `/api/research/jobs` endpoints with polling.
An explicit `/api/research/scenario` route computes modeled energy and water
only from user-entered IT capacity, utilization, PUE, and WUE. The optional
carbon result also requires a user-entered grid emissions factor. City map
placement uses an approximate, cached, rate-limited geocode; it is never a
facility coordinate. Image-only PDF pages use local OCR when Poppler and
Tesseract are available.

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

The later live CNBC run fetched the article and kept the 780 MW facility,
1,400 MW wind, 200 MW solar, and 300 MW battery figures separate. It remained
partial because no independent source was collected and model extraction fell
back to deterministic rules. The first live parse had also treated generic
25 MW and 1,000 MW examples as Pine Island capacities; that defect was fixed
with a project-context check and a regression test.

## Live acceptance case: Meta in El Paso

Use the [September 24, 2026 Inside Climate News article](https://insideclimatenews.org/news/24092026/el-paso-electric-only-considered-gas-to-power-meta-data-center/)
as the seed URL with `El Paso, TX` or `Texas`. Cross-check it against the
[City of El Paso data center resource page](https://www.elpasotexas.gov/data-centers)
and the city's linked agreements. The article describes a 1,000 MW Meta data
center and a proposed 366 MW McCloud gas plant serving it. The city page
separately reports phased water allocations, a 2023 development agreement,
incentives, and jobs. Its $1.5 billion infrastructure description and the
article's $10 billion project description need source, scope, and date context
before they can be compared as investment claims.

The first live probe mislabeled the 366 MW gas plant as data-center capacity;
that classifier defect was fixed. A later two-source run reviewed the article
and City page, identified Meta, kept the 1,000 MW data center separate from
the 366 MW gas plant, extracted all six Tier I–III water allocations, and kept
the City's $1.5 billion infrastructure description separate from the
article's $10 billion project value. The result remains `partial` because
general search and model extraction are unavailable in the current setup.
The article's "northeast El Paso" wording also exposed a state-only matching
bug; `Texas` plus the URL now identifies the project. Texas without a source
requires a working search provider and returns an explicit instruction when
none is configured. A temporary Brave token was rejected by the provider as
invalid and was not retained.

**Acceptance checks for this case:**

1. Fetch and identify the Meta project from the article without assigning
   unrelated El Paso projects or general data-center facts to it.
2. Record 1,000 MW as reported data-center capacity and 366 MW as proposed
   gas-generation capacity. Do not create a conflict between those subjects.
3. Collect the city page as a separate, cited source through the explicit
   additional-source input; keep inaccessible pages and search failures
   available in optional coverage details.
4. Preserve the city's Tier I/II/III average and maximum water values with
   their phase and measure; do not collapse them into one unqualified number.
5. Keep the $1.5 billion and $10 billion investment descriptions attributed
   to their sources and scopes until their relationship is established.

## Baseline defects observed in the supplied extractor

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

## Code layout

Research code is in `scripts/ecocompute_research/`; the FastAPI route in
`backend/app/` is a thin adapter. The package is installed for backend imports.

| File | Responsibility |
| --- | --- |
| `scripts/ecocompute_research/models.py` | Versioned Pydantic input, source, claim, conflict, missing-field, and result types. |
| `scripts/ecocompute_research/intake.py` | Validate input; reuse and improve URL, text, PDF, and location extraction. |
| `scripts/ecocompute_research/identity.py` | Identify one project or return ranked candidates and ambiguity. |
| `scripts/ecocompute_research/discovery.py` | Generate bounded queries and call a configurable web search provider. |
| `scripts/ecocompute_research/collection.py` | Fetch, deduplicate, clean, and record HTML/PDF sources. |
| `scripts/ecocompute_research/facts.py`, `gemini.py`, `fact_extractor.py` | Extract typed, source-linked claims and normalize units. |
| `scripts/ecocompute_research/reconciliation.py` | Separate phases and capacity types; retain unresolved conflicts. |
| `scripts/ecocompute_research/estimates.py` | Configurable, explicitly provisional engineering proxies. |
| `scripts/ecocompute_research/report.py` | Missing-field audit, neutral questions, and cited summary. |
| `scripts/ecocompute_research/pipeline.py` | Orchestrate the stages and report partial/failed progress. |
| `backend/app/research.py` | FastAPI request validation and research endpoint. |
| `backend/tests/test_research_*.py` | Offline fixtures, unit tests, and API tests. |

The implementation also has separate modules for location, URL and PDF intake,
HTML cleanup, grounded search, and the legacy result adapter. The supplied
extractor served as a baseline, not as a source of unverified defaults.

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
extracts text-based PDFs and can OCR scanned pages with local Poppler and
Tesseract tools; unreadable PDFs return a partial result. `html_text.py` removes
common page chrome. `scripts/tests/test_intake.py` covers these paths offline,
including a generated text PDF with pypdf. The fetcher rejects local and
private addresses, but deployment still needs network egress controls against
DNS changes after validation. No live CNBC fetch or FastAPI research route is
part of this point.

**Later ZIP integration:** `zip_lookup.py` resolves a user-supplied ZIP to
city/state search context through Zippopotam.us. Research results retain the
original ZIP, ZIP-area precision, and lookup provenance; the resolved city does
not assert a facility address. Lookup failures stay partial and an explicit
ZIP/state mismatch is rejected. Offline tests cover these paths, and a live
lookup of `55963` returned Pine Island, MN.

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
No Brave key is available in this checkout, so provider-based live discovery
remains an acceptance check. Search snippets are leads, not verified evidence.
A later keyless path accepts up to five explicit source URLs and considers
relevant outgoing links from a seed article. These URLs pass the same collector
checks; they do not provide broad web search or imply complete coverage.

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
The El Paso case must also distinguish the data-center load from generation
built to serve it.

**Implementation:** `facts.py` provides a deliberately narrow regex fallback
for explicitly contextualized MW, daily water, investment, and permanent jobs.
`gemini.py` sends one bounded source chunk at a time to a configurable Gemini
model, requests JSON, and rejects claims whose excerpt is absent from the
source or whose MW value/subject contradicts its excerpt. `fact_extractor.py`
uses the fallback when Gemini is unavailable. Offline tests cover Pine Island
MW separation, multi-project articles, a model misclassification, and model
failure. The model adapter follows the [Gemini structured output reference](https://ai.google.dev/gemini-api/docs/structured-output?lang=web).
No Gemini key is stored in this checkout. A temporary-key trial could not
run the configured Gemini extraction model, so live model extraction quality
has not been assessed. The deterministic fallback does not claim comprehensive
environmental or tariff extraction. A later change added a distinct
gas-generation claim and El Paso regressions for deterministic extraction,
model-output validation, and the pipeline.

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

**Implementation:** `reconciliation.py` merges identical values across
independent origins, retains incompatible figures, and explains explicitly
different phases without averaging. `estimates.py` implements configurable
preliminary MW proxies and keeps the 100 MW baseline as a scenario rather than
a project fact. `report.py` generates a cited, neutral summary and questions
for information not found in reviewed sources. Offline tests cover independent
versus syndicated support, unresolved and phase-specific MW figures, null
capacity despite a proxy, and cited summary language. Live source quality
still depends on points 4–5 being configured and evaluated.

### 7. API and frontend integration

- Add a research API with validation and a path toward progress/job retrieval.
- Show source-backed results apart from the simulator's demo metrics. Preserve
  `POST /api/investigations/preview` until the new flow replaces it safely.
- Feed downstream modules through a validated adapter, including capacity
  kind and source/provenance checks.

**Done when:** One article plus location produces inspectable sources, claims,
unknowns, and a summary in the app without presenting demo values as facts.

**Implementation:** `pipeline.py` connects intake, identity, discovery,
collection, extraction, reconciliation, estimates, and reporting. The bounded
synchronous `POST /api/research` and `POST /api/research/pdf` routes expose all
four input modes. URL, text, and PDF modes also accept additional source URLs.
`ResearchPanel.tsx` presents project candidates, reviewed sources,
source-linked claims, conflicts, unknowns, and optional coverage details
separately from the simulator. The existing preview route remains available.
Python packaging installs the research scripts for the backend. The frontend
uses bounded in-memory research jobs with status polling; synchronous routes
remain available. `POST /api/research/scenario` calculates a separate modeled
scenario only from explicit IT-load and efficiency inputs. City and state
research results are positioned on the map at approximate area centers, never
as claimed facility coordinates. Persistent jobs remain a deployment task.

### 8. End-to-end evaluation

- Use Pine Island and additional projects in other states. Mock external
  services in routine tests; use a small, documented live evaluation separately.
- Check inaccessible articles, duplicate coverage, unrelated projects,
  contradictory figures, scanned PDFs, and search-provider outages.

**Done when:** The live evaluation finds relevant additional sources where
available, reports its research coverage and limitations, and passes the
offline regression suite.

**Evaluation:** `scripts/tests/test_pipeline.py` covers Pine Island, a
synthetic Virginia project, provider outage, inaccessible articles, Texas
state-level input, and no-provider guidance. The rest of the suite covers
duplicate and unrelated sources, capacity classification, phase-specific
claims, conflicts, and scanned PDF OCR. The latest recorded checks passed 100
Python tests, eight frontend tests, and a frontend build. The live CNBC run
extracted four distinct power figures from one source. The two-source El Paso
run extracted the scoped financial and phased water figures described above.
Point 8 still needs broader live source-recall and provider evaluation before
it is fully accepted; see `docs/RESEARCH_EVALUATION.md`.

## Earlier implementation decisions

- Select the search provider and acceptable per-investigation cost/latency
  before point 4.
- The API keeps synchronous routes while the frontend uses in-memory
  background jobs; use a persistent queue before multi-worker deployment.
- Review compatibility needs with the teammates consuming `activeSite` before
  finalizing its adapter in point 1.

## Next action

Configure a working search subscription and evaluate automatic discovery on
more than one project. Inspect every collected source and claim before marking
the pipeline complete. Keep optional source-access diagnostics available
without making them the main report content.
