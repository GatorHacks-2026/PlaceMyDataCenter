# EcoCompute AI — Architecture & Module 1 Implementation Summary

**Last Updated:** October 24, 2026  
**Project Direction:** Citizen-First Data Center Fact-Checker, Environmental Impact Simulator & Statewide County Recommender  
**Completed Deliverables:**
- Interactive Frontend Prototype: `frontend/ecocompute_input_auditor.html`
- Production FastAPI Extraction Module: `backend/services/input_extractor.py`

## 1. Project Vision & Hackathon Narrative

When companies propose hyperscale AI and cloud data centers, press releases highlight capital investment and construction jobs while frequently omitting decision-critical resource demands—such as peak summer water consumption, cooling tower architecture, indirect power-plant water draw, backup diesel generator counts, and grid transmission cost-sharing—often citing trade secrets or non-disclosure agreements (as seen in [The Dalles, Oregon water records dispute](https://www.datacenterdynamics.com/en/news/we-now-know-how-much-water-googles-oregon-data-centers-use-after-city-drops-lawsuit-against-journalists/)).

**EcoCompute AI** empowers local residents, journalists, and city council members to:
1. **Audit Any Proposal or Location:** Paste a news article, paste a live URL, upload a City Council PDF, or enter only a US ZIP code, City, or State.
2. **Expose Withheld Data:** Automatically flag every omitted engineering and socioeconomic metric in red badges.
3. **Run Independent Physics Checks:** Calculate bounded **Direct On-Site Water + Indirect Power-Plant Water** ([LBNL methodology](https://datacenters.lbl.gov/modeling-forecasting)), electricity demand, and [EPA eGRID](https://www.epa.gov/egrid) carbon emissions, translated into human-scale equivalents (*Olympic swimming pools, households' daily water, homes powered, and gas cars added*).
4. **Simulate Alternatives & Better Counties:** Test cooling trade-offs (*Evaporative vs. Hybrid vs. Closed-Loop Dry Air*) in a Citizen Playground and rank the top 3–5 alternative counties in the same state using Jaysurya’s 5-factor County Simulator.
5. **Take Civic Action:** Generate evidence-backed Town Hall questions to bring to City Council hearings before tax abatements or water agreements are approved.

## 2. Five-Person Parallel Team Division

| Teammate | Module Ownership | Primary Responsibilities | Consumes / Produces |
| :--- | :--- | :--- | :--- |
| **Person 1** | **Geospatial, Satellite Map & Buffer Rings** (`src/components/Map/`) | MapLibre satellite view + 2D US map fallback, 1/3/5-mile residential proximity rings, [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) terrain overlay, and water station markers. | Reads `lat`, `lon`, `zip_code`, `is_statewide_mode` from `activeSite`. |
| **Person 2** | **Physics Truth Engine & Citizen Playground** (`backend/engine/physics.py`) | `/api/estimate` endpoint, [LBNL Direct + Indirect Water](https://datacenters.lbl.gov/modeling-forecasting) formulas, Water vs. Carbon trade-off curves, and Human Equivalency converters. | Reads `estimated_mw`, `cooling_type`, `egrid_lb_mwh` from `activeSite`. |
| **Person 3** | **Live Environmental & Grid APIs** (`backend/services/env_data.py`) | `/api/environment` endpoint fetching [Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api) summer peak temperatures, [USGS Water Services](https://waterservices.usgs.gov/docs/) river/well gauges, [U.S. Drought Monitor](https://droughtmonitor.unl.edu/) D0–D4 history, and [EIA](https://www.eia.gov/opendata/) rates. | Reads `lat`, `lon`, `zip_code`, `county`, `state` from `activeSite`. |
| **Person 4** | **Input Ingestion, Gemini Auditor & Battle Card** (`backend/services/input_extractor.py`) | **Built in Module 1:** Multi-modal input router (Text, Live URL, PDF, Manual Location), Proxy MW calculator, Withheld-Data detector, and Town Hall Question generator. | **Produces** the master `activeSite` JSON contract for Teammates 1, 2, 3, and 5. |
| **Person 5** | **Dashboard Charts & Statewide County Simulator** (`src/components/CountySimulator/`) | Water vs. Carbon bar chart, Drought timeline, `localStorage` Saved Sites, and **Jaysurya’s 5-Factor County Recommender** ranking the best counties in the state. | Reads `state`, `missing_fields`, and physics arrays. |

## 3. Step-by-Step Logic Built in Module 1 (Input & Extraction Pipeline)

### Stage 1: Multi-Modal Input Ingestion (4 Input Paths)

| Input Tab | Frontend Implementation (`ecocompute_input_auditor.html`) | Backend Implementation (`input_extractor.py`) |
| :--- | :--- | :--- |
| **1. Paste Article Text** | Reads raw text directly from `<textarea id="articleTextInput">` and sends it to Stage 2. | Receives raw string payload and passes it to `extract_with_gemini_or_fallback()`. |
| **2. Paste Live URL** | Calls `scrapeLiveUrlAndAudit()`: fetches clean article text via [Jina Reader](https://jina.ai/reader/) (`https://r.jina.ai/<url>`) with automatic fallback to [AllOrigins CORS Proxy](https://allorigins.win/) + `DOMParser` `<p>` tag extraction, copies scraped text into Tab 1 for verification, and audits it. | `extract_text_from_url()` fetches HTML via `httpx`, strips `<script>/<style>/<nav>` via `BeautifulSoup`, joins `<p>` tags, and falls back to `https://r.jina.ai/<url>`. |
| **3. Upload Real PDF** | Calls `extractRealPdfFile()`: uses **[Mozilla PDF.js](https://mozilla.github.io/pdf.js/)** (`pdf.min.js`) in the browser to read binary `.pdf` files (`file.arrayBuffer()`), extracts text across pages via `page.getTextContent()`, and audits the extracted text. | `extract_text_from_pdf()` reads binary PDF bytes via `pypdf.PdfReader` and concatenates text across all pages. |
| **4. Manual ZIP / City / State** | Reads any 5-digit US ZIP code, any US City name, or any of the 50 US States from the form (plus optional MW, Sq Ft, or $ Investment) and jumps straight to Stage 3. | Passes manual form fields directly into `build_active_site_contract()`. |

### Stage 2: Structured Claim Extraction (`extractWithGeminiIfKeyPresent` & `parseArticleText`)

Once raw text is obtained from Stage 1, the engine extracts a standardized dictionary of claims:
1. **Live Gemini 2.5 Flash Mode (When `GEMINI_API_KEY` is provided):** Calls `gemini-2.5-flash` with `responseMimeType: "application/json"` to extract location, scale, cooling, water, and socioeconomic promises.
2. **Universal 50-State NLP/Regex Mode (Default / Zero-Key Mode):**
   - **5-Digit ZIP Detection:** Extracts 5-digit US postal codes (`\b\d{5}\b`), filtering out calendar years (`2015–2035`).
   - **All 50 US States + City/County Detection:** Scans against all 50 full state names and 2-letter postal abbreviations (`US_STATES_MAP`) to capture patterns like `"in New Albany, Ohio"`, `"Granbury, Hood County, Texas"`, or `"Reno, NV"`.
   - **Engineering & Financial Claims:** Extracts `stated_mw` (and converts `GW` to `MW`), `building_sqft`, `capex_millions` (converting `$ Billion` to `$ Million`), `acreage`, `cooling_type` (`evaporative`, `hybrid`, `dry_air`, `liquid`, or `unspecified`), `claimed_water_gpd`, and `permanent_jobs`.
   - **Greenwashing & Spin Detection:** Captures vague phrases (`"sustainable design"`, `"state-of-the-art cooling"`, `"minimal water impact"`, `"trade secret"`, `"water-positive"`).

### Stage 3: Universal 50-State Geolocation Cascade (`resolveLocationCascade`)

Works even when the user provides **only** a ZIP code, **only** a City, or **only** a State:
1. **If a 5-digit ZIP code is present:** Queries the live **[Zippopotam.us API](https://zippopotam.us/) (`GET https://api.zippopotam.us/us/{zip}`)** to retrieve the exact City, State, Latitude, and Longitude (with an offline cache fallback).
2. **Else if a City name is present:** Queries the live **[Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api) (`GET https://geocoding-api.open-meteo.com/v1/search?name={city}`)**, filters to `country_code == "US"` and matching state, and retrieves exact coordinates, County (`admin2`), primary ZIP code, and population.
3. **Else if ONLY a State is selected:** Geocodes the state center and sets `is_statewide_mode = true` to trigger **Jaysurya’s Statewide County Recommender**.
4. **50-State Grid Carbon Mapping:** Maps the resolved 2-letter state code against `STATE_EGRID` to attach the state's [EPA eGRID](https://www.epa.gov/egrid) carbon intensity rate (`lb CO₂/MWh`).

### Stage 4: Proxy Megawatt (MW) Estimation Math (`computeProxyMw`)

Because news articles frequently omit Megawatts, the engine applies an ordered proxy hierarchy so downstream calculators never fail:
- **Priority 1 (Stated MW):** If `stated_mw > 0`, use `stated_mw` directly.
- **Priority 2 (From Building Sq Ft):** `estimated_mw = (building_sqft / 10,000) * 3.5` (for AI workloads) or `* 2.5` (for standard cloud).
- **Priority 3 (From Capital Investment $M):** `estimated_mw = capex_millions / 10.0` (based on the ~$10M per MW industry construction benchmark).
- **Priority 4 (From Land Acreage):** `estimated_mw = acreage * 0.8`.
- **Priority 5 (Location-Only Default):** Defaults to `100 MW` (*Standard Hyperscale Baseline*) and enables 1-click Citizen Playground scale buttons for **25 MW (Small Edge)**, **100 MW (Typical Hyperscale)**, and **300 MW (Mega AI Campus)**.

### Stage 5: Withheld-Data Red Flags, LBNL Physics Preview & Battle Card Questions

- **"What They Told You vs. What They Hid" Scorecard:** Every extracted claim is listed in the green **Disclosed / Inferred** column. Every `null` or undisclosed critical parameter (`peak_water_gpd`, `cooling_type`, `infrastructure_payer`, `backup_generators`) generates a red **WITHHELD** alert explaining the local risk.
- **Physics Mismatch Alert:** If a proposal uses vague green phrases (e.g., *"minimal water impact"*) while leaving `cooling_type` unspecified, the auditor triggers a **Transparency & Physics Alert**.
- **LBNL Direct + Indirect Water & Human Equivalents (`updatePhysicsPreview`):** Calculates annual IT energy (`MW × 8,760 hrs × 0.75 utilization × PUE`), on-site cooling tower evaporation (**Direct Water**), regional thermoelectric power-plant evaporation (**Indirect Water**), and [EPA eGRID](https://www.epa.gov/egrid) Scope 2 carbon, converting results into **Olympic Swimming Pools/year**, **Share of Town Water (%)**, **Homes' Water & Power Equivalents**, and **Gas Cars Added**.
- **Town Hall Battle Card Generator:** Automatically turns every missing field into a specific, copyable City Council hearing question tailored to the target city and county.

## 4. Shared Team JSON Contract (`activeSite`)

Every run of Module 1 outputs this standardized JSON structure for Teammates 1, 2, 3, and 5:

```json
{
  "input_mode": "text",
  "zip_code": "43054",
  "city": "New Albany",
  "county": "Licking / Franklin County",
  "state": "OH",
  "lat": 40.0812,
  "lon": -82.8088,
  "is_statewide_mode": false,
  "egrid_lb_mwh": 1160,
  "estimated_mw": 210,
  "scale_source": "Inferred from 600,000 sq ft (3.5 MW per 10k sq ft)",
  "cooling_type": "evaporative",
  "missing_fields": [
    "stated_mw",
    "peak_water_gpd",
    "cooling_type",
    "infrastructure_payer",
    "backup_generators"
  ]
}
```
