# EcoCompute AI

A data center sustainability simulator. The React dashboard shows modeled annual water, electricity, and carbon estimates for a selected US location, capacity, utilization, and cooling type. Regional grid factors and drought labels are demo assumptions, not measured site data.

## Run locally

Start the API in one terminal (Python 3.10+):

```sh
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

For scanned PDF OCR on macOS, install the local tools with `brew install poppler tesseract`.

Start the frontend in another terminal (Node 22+):

```sh
npm install
npm run dev
```

Open <http://localhost:5173/>. Vite proxies `/api` to the local FastAPI server. For a production build, `npm run build` creates `dist/`; deployment must route `/api` to the backend as well.

## Check the project

```sh
npm test
npm run build
PYTHONPATH=backend backend/.venv/bin/python -m pytest scripts/tests backend/tests -q
```

The backend exposes `POST /api/estimate`, synchronous `POST /api/research` and `POST /api/research/pdf`, background `POST /api/research/jobs` and `POST /api/research/jobs/pdf`, `GET /api/research/jobs/{id}`, and `POST /api/research/scenario`; interactive API documentation is at <http://127.0.0.1:8000/docs>. The research panel uses background jobs and accepts an article URL, pasted text, PDF, or location only. With a seed article or document, users may provide up to five additional public source URLs. For article URLs, the backend also checks relevant links in the article. Scanned PDFs need `pdftoppm` (Poppler) and `tesseract` installed on the backend host. Set `BRAVE_SEARCH_API_KEY` for broader web discovery and `GEMINI_API_KEY` for model extraction. An experimental Google Search grounding provider can be selected with `RESEARCH_SEARCH_PROVIDER=gemini` and `GEMINI_SEARCH_MODEL`, but requires account access and quota. Without usable search, results show partial coverage even when supplied or linked sources are reviewed.

Research claims and sources appear separately from the simulator's modeled estimates. A project-specific scenario needs explicit IT load and efficiency inputs; carbon stays unknown without a supplied grid factor. The map's ZIP search uses Zippopotam.us from the browser; research intake also resolves ZIPs through that service on the backend to find city/state search context while retaining ZIP-area precision. City research uses the public Nominatim service for an approximate city marker, with a backend cache and one-request-per-second limit. State-only results show no facility marker. The public Nominatim service has a [usage policy](https://operations.osmfoundation.org/policies/nominatim/) and must be replaced or self-hosted for heavier use. Background jobs are in-memory and need a persistent queue for multi-worker deployment. See [research plan](docs/RESEARCH_PIPELINE_PLAN.md) and [evaluation](docs/RESEARCH_EVALUATION.md) for scope and current live-service limitations.

## See API requests and results

The backend terminal logs each estimate's validated JSON request and JSON response. Uvicorn also logs the method, path, and HTTP status. To keep a local copy while you test, start it from `backend/` with:

```sh
.venv/bin/uvicorn app.main:app --reload --port 8000 2>&1 | tee -a api.log
```

Then change a setting and click **Analyze**. Open `backend/api.log` or run `tail -f api.log` from `backend/`. The log file is ignored by Git. Stop the server with Ctrl+C when done.

See [progress](docs/PROGRESS.md), [roadmap](docs/ROADMAP.md), and [technical notes](docs/TECHNICAL.md).
