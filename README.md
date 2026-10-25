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

The backend exposes `POST /api/estimate`, synchronous `POST /api/research` and `POST /api/research/pdf`, background `POST /api/research/jobs` and `POST /api/research/jobs/pdf`, `GET /api/research/jobs/{id}`, and `POST /api/research/scenario`; interactive API documentation is at <http://127.0.0.1:8000/docs>. The research panel uses background jobs and accepts an article URL, pasted text, PDF, or location only. With a seed article or document, users may provide up to five additional public source URLs. For article URLs, the backend also checks relevant links in the article. Scanned PDFs need `pdftoppm` (Poppler) and `tesseract` installed on the backend host. Search defaults to Tavily's free keyless Search API; it requires no account or key but has rate limits. A free `TAVILY_API_KEY` raises those limits. Search results are only candidate leads until the backend fetches and reviews a page. City or ZIP location-only searches can automatically investigate one identified candidate; broad searches return candidate articles to choose from. No `.env` file is needed for keyless research. For optional private keys, create a single `.env` file at the repository root; the backend loads it on startup and Git ignores it. Supported entries include `TAVILY_API_KEY` (higher search limits), `GEMINI_API_KEY` (model extraction), `EIA_API_KEY` (electricity screening), and `API_USGS_PAT` (optional USGS access). Brave and Gemini search remain optional alternates via `RESEARCH_SEARCH_PROVIDER=brave` with `BRAVE_SEARCH_API_KEY`, or `RESEARCH_SEARCH_PROVIDER=gemini`. Without usable search, results show partial coverage even when supplied or linked sources are reviewed.

Research claims and sources appear separately from the simulator's modeled estimates. A project-specific scenario needs explicit IT load and efficiency inputs; carbon stays unknown without a supplied grid factor. The map's ZIP search uses Zippopotam.us from the browser; research intake also resolves ZIPs through that service on the backend to find city/state search context while retaining ZIP-area precision. City research uses the public Nominatim service for an approximate city marker, with a backend cache and one-request-per-second limit. State-only results show no facility marker. The public Nominatim service has a [usage policy](https://operations.osmfoundation.org/policies/nominatim/) and must be replaced or self-hosted for heavier use. Background jobs are in-memory and need a persistent queue for multi-worker deployment. See [research plan](docs/RESEARCH_PIPELINE_PLAN.md) and [evaluation](docs/RESEARCH_EVALUATION.md) for scope and current live-service limitations.

The map defaults to USGS satellite/aerial imagery and can switch to a street map. A research result with a project-associated ZIP centers the map on that approximate ZIP area; city and state results use broader approximate centers. None of these area centers becomes a facility point. Click **Place proposed facility** and choose a point on the map, then click **Place my home** and choose another point. The panel reports their straight-line distance and a fixed 0–1, 1–3, 3–5, or beyond-5-mile band. The 1-, 3-, and 5-mile circles are distance guides, not measured environmental impacts or verified facility boundaries. Placed points are cleared when a new research result or map location is selected and are never sent to the research pipeline.

The Playground now appears below the satellite site screening. After a screening run, it takes that facility pin, IT capacity, utilization, PUE, WUE, and available grid emissions factor as its baseline. Users can compare another capacity or cooling assumption through the backend scenario endpoint. The comparison also places alternative average demand and peak water need beside the screening's fixed EIA energy proxy and assumed USGS flow threshold. Those regional readings are not site-specific utility or water supplies. The scenario results are modeled facility electricity, water consumption, and grid electricity carbon, not measured local impacts. Cooling presets are illustrative. Changing the map's IT-capacity input makes it hypothetical and clears the previous screening and comparison until screening runs again. The fixed distance rings do not change. The research location field in the header still accepts a ZIP or city/state.

After research, the satellite map draws the best available approximate area outline: a Census ZIP Code Tabulation Area (ZCTA), a city polygon from the existing geocoder, or a Census state outline. A search ZIP without a project-associated ZIP is explicitly labeled as an unverified search area. A ZCTA is only an approximation of a USPS ZIP area, and some ZIPs have no matching polygon. The user places the facility pin inside the researched area when possible; the pin, rather than the area center, supplies site coordinates for **Run site screening**. A home pin adds a distance-based noise estimate. Only an unambiguous sourced IT-capacity claim prefills the screening size; otherwise the user confirms a hypothetical IT capacity. Screening jobs call the standalone `Data_Center_backend.py` model via FastAPI and show each layer's source, assumptions, and limitations. Configure `EIA_API_KEY` for the EIA electricity layer; the public USGS water lookup can run without `API_USGS_PAT`. The screening flags are exploratory indicators, not permitting decisions: state generation minus sales is not grid interconnection capacity, a nearby river is not a verified water supply, and noise equipment levels are assumed.

After screening, the satellite map draws a dashed cyan outline for the USGS gauge search radius, markers for gauges with coordinates, and a dashed purple contour for the modeled distance to an assumed night noise threshold. The yellow gauge marker identifies the gauge used in the water comparison; cyan markers show the other analyzed gauges. **View USGS search area** zooms to that outline. Gauge markers and their flow values do not identify a facility water source. The noise contour uses assumed equipment levels and a comparison threshold; it is not measured sound or a legal boundary. The fixed 1-, 3-, and 5-mile guides remain separate.

## See API requests and results

The backend terminal logs each estimate's validated JSON request and JSON response. Uvicorn also logs the method, path, and HTTP status. To keep a local copy while you test, start it from `backend/` with:

```sh
.venv/bin/uvicorn app.main:app --reload --port 8000 2>&1 | tee -a api.log
```

Then change a setting and click **Analyze**. Open `backend/api.log` or run `tail -f api.log` from `backend/`. The log file is ignored by Git. Stop the server with Ctrl+C when done.

See [progress](docs/PROGRESS.md), [roadmap](docs/ROADMAP.md), and [technical notes](docs/TECHNICAL.md).
