# Research scripts

`scripts/ecocompute_research/` is the research pipeline used by the FastAPI
routes in `backend/app/research.py`. It accepts a location with an article URL,
pasted text, a text-based PDF, or no seed document. A seed document can include
up to five additional public source URLs; article pages also supply relevant
outgoing links as candidate sources. Each candidate is fetched and checked
before it becomes reviewed evidence. The JSON route is `POST /api/research`;
PDF upload uses `POST /api/research/pdf` with repeatable `additional_urls` form
fields.

The flow is `intake` → project `identity` → web `discovery` and `collection` →
source-linked `fact_extractor` → `reconciliation` → `report`. `models.py` defines
the versioned result contract. `legacy.py` provides a conservative adapter for
older flat `activeSite` consumers. The original standalone extractor was a
baseline, not a dependency of these routes.

`intake.py` parses the supplied location and reads the seed text. A ZIP is
resolved by `zip_lookup.py` to city/state search context using Zippopotam.us;
the result keeps the submitted ZIP and ZIP-area precision. URL fetching and PDF
text extraction have size and access limits. Image-only pages use local
`pdftoppm` and `tesseract` when both are installed (up to 20 OCR pages); absent
OCR tools still yield a partial no-text result for fully scanned files.

Broader discovery uses Brave when `BRAVE_SEARCH_API_KEY` is configured. An experimental
Gemini Google Search provider can be selected with
`RESEARCH_SEARCH_PROVIDER=gemini` and `GEMINI_SEARCH_MODEL`; it requires a model
and grounding quota that actually work for the account. Extraction can use
`GEMINI_API_KEY` and `GEMINI_MODEL`, otherwise it falls back to deliberately
limited deterministic rules. Without usable search, results remain partial
even when explicit or article-linked sources were reviewed.

Install `backend/requirements-dev.txt`, then run from the repository root:

```sh
PYTHONPATH=backend python -m pytest scripts/tests backend/tests -q
```

The latest recorded suite passed 100 Python tests. The ZIP research path was
also checked in the browser with `55963` plus Pine Island seed text. See
[`docs/RESEARCH_EVALUATION.md`](../docs/RESEARCH_EVALUATION.md) for the remaining
live-service and extraction defects, and
[`docs/RESEARCH_PIPELINE_PLAN.md`](../docs/RESEARCH_PIPELINE_PLAN.md) for the
stage contracts and acceptance cases.
