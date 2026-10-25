# Research scripts

The EcoCompute research package is `scripts/ecocompute_research/`. Its file
responsibilities and step-by-step implementation order are in
[`docs/RESEARCH_PIPELINE_PLAN.md`](../docs/RESEARCH_PIPELINE_PLAN.md).

Point 1 contains evidence models (`models.py`), an offline Pine Island fixture
(`fixtures.py`), and a conservative flat contract adapter (`legacy.py`). It
does not run research yet. Point 2 adds validated intake (`intake.py`), place
parsing (`location.py`), bounded URL fetching (`url_fetch.py`), HTML cleaning
(`html_text.py`), and text PDF extraction (`pdf_text.py`). URL access failures
return a partial intake result. This code is not connected to FastAPI yet.
The current FastAPI application
remains in `backend/app/`; the supplied prototype remains at
`/Users/jaysuryaray/Downloads/input_extractor.py` until later steps integrate
its reusable parts.

Point 3 adds `identity.py`, which extracts location-matched project candidates
from seed text and returns ambiguity when the input does not identify one site.

Point 4 adds `discovery.py` and `collection.py`. Set `BRAVE_SEARCH_API_KEY` in
the environment to use the Brave Web Search API. Without it, discovery returns
a partial result with no invented URLs. Search and collection limits are
arguments to their entry functions. A live provider check still requires a key.

Point 5 adds conservative regex extraction (`facts.py`) and optional Gemini
extraction (`gemini.py`), coordinated by `fact_extractor.py`. Set
`GEMINI_API_KEY` to enable it; `GEMINI_MODEL` selects the model and defaults to
`gemini-3.8-flash`. Each retained claim cites an excerpt from its source.

From the repository root, after installing `backend/requirements-dev.txt`, run:

```sh
python -m pytest scripts/tests -q
```

For example, `read_input(IntakeRequest(mode="text", location="Pine Island, MN",
article_text="..."))` returns the seed text and a city-level location with
unknown coordinates. The URL and PDF modes need the dependencies listed in
`backend/requirements.txt`.
