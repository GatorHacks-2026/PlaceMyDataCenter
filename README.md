# EcoCompute AI

A data center sustainability simulator. The React dashboard shows modeled annual water, electricity, and carbon estimates for a selected US location, capacity, utilization, and cooling type. Regional grid factors and drought labels are demo assumptions, not measured site data.

ata Center Lens is a web-based transparency tool designed to expose the true resource footprint of local data centers. Stripping away corporate PR, it empowers everyday citizens with a straightforward utility tool to investigate real-world environmental impacts right in their backyards.

## What it does

Pinpoint Facilities: Explore an interactive geospatial map to locate data centers in your area.

Extract Resource Data: Pull comprehensive real-world metrics on water consumption, electric consumption utilization, remaining capacity, noise levels, carbon emissions, and overall environmental impact.

Agentic Battle: Consult an interactive AI agent powered by Gemma that weighs corporate claims against real-world resource costs in a balanced, data-driven breakdown.

Export Instant Reports: Synthesize findings on the fly and generate a clean, citizen-ready PDF report for community advocacy and review.

## How we built it

Mapping & Data Pipeline: Integrated geospatial mapping to overlay local facility locations with resource data, utilizing the US EIA (Energy Information Administration) API to fetch regional electric consumption metrics and the USGS (U.S. Geological Survey) to analyze local water consumption and available rivers.

Balanced Analysis Engine & LLM: Powered by Gemma, we programmed the Live Agent to evaluate multi-faceted arguments, contrasting corporate sustainability messaging with ground-truth resource impacts.

Automated PDF Export: Implemented quick-generation tools to package investigation findings into portable, professional reports.

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

The backend exposes `POST /api/estimate`; interactive API documentation is at <http://127.0.0.1:8000/docs>. ZIP search still calls the public Zippopotam.us service from the browser.

## See API requests and results

The backend terminal logs each estimate's validated JSON request and JSON response. Uvicorn also logs the method, path, and HTTP status. To keep a local copy while you test, start it from `backend/` with:

```sh
.venv/bin/uvicorn app.main:app --reload --port 8000 2>&1 | tee -a api.log
```

Then change a setting and click **Analyze**. Open `backend/api.log` or run `tail -f api.log` from `backend/`. The log file is ignored by Git. Stop the server with Ctrl+C when done.

See [progress](docs/PROGRESS.md), [roadmap](docs/ROADMAP.md), and [technical notes](docs/TECHNICAL.md).
