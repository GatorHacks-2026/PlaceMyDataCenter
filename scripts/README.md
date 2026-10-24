# Research scripts

The EcoCompute research package is `scripts/ecocompute_research/`. Its file
responsibilities and step-by-step implementation order are in
[`docs/RESEARCH_PIPELINE_PLAN.md`](../docs/RESEARCH_PIPELINE_PLAN.md).

Point 1 contains evidence models (`models.py`), an offline Pine Island fixture
(`fixtures.py`), and a conservative flat contract adapter (`legacy.py`). It
does not fetch articles or run research yet. The current FastAPI application
remains in `backend/app/`; the supplied prototype remains at
`/Users/jaysuryaray/Downloads/input_extractor.py` until later steps integrate
its reusable parts.

From the repository root, after installing `backend/requirements-dev.txt`, run:

```sh
python -m pytest scripts/tests -q
```
