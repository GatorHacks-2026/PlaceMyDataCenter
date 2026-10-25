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
cd backend && .venv/bin/python -m pytest tests -q
```

The backend exposes `POST /api/estimate`, `POST /api/research`, and `POST /api/research/pdf`; interactive API documentation is at <http://127.0.0.1:8000/docs>. The research panel accepts an article URL, pasted text, text-based PDF, or location only. Set `BRAVE_SEARCH_API_KEY` for the default web discovery and `GEMINI_API_KEY` for model extraction. An experimental Google Search grounding provider can be selected with `RESEARCH_SEARCH_PROVIDER=gemini` and `GEMINI_SEARCH_MODEL`, but requires account access and quota. Without usable search, results show partial coverage. ZIP search still calls the public Zippopotam.us service from the browser.

Research claims and sources appear separately from the simulator's modeled estimates. See [research plan](docs/RESEARCH_PIPELINE_PLAN.md) and [evaluation](docs/RESEARCH_EVALUATION.md) for scope and current live-service limitations.

## See API requests and results

The backend terminal logs each estimate's validated JSON request and JSON response. Uvicorn also logs the method, path, and HTTP status. To keep a local copy while you test, start it from `backend/` with:

```sh
.venv/bin/uvicorn app.main:app --reload --port 8000 2>&1 | tee -a api.log
```

Then change a setting and click **Analyze**. Open `backend/api.log` or run `tail -f api.log` from `backend/`. The log file is ignored by Git. Stop the server with Ctrl+C when done.

See [progress](docs/PROGRESS.md), [roadmap](docs/ROADMAP.md), and [technical notes](docs/TECHNICAL.md).
