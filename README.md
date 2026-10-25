# Data Center Lens

Data Center Lens helps residents investigate a proposed data center. It reviews supplied articles and public sources, maps an approximate project area, lets you place a proposed facility and home pin, and runs a preliminary site screening. Its figures are exploratory estimates, not measured impacts or permitting decisions.

## Quick start

Run these commands **from the repository root** on macOS, Linux, or WSL. You need Python 3.10+, Node.js 22+, npm, and `make`.

```sh
make setup
make dev
```

Open [http://127.0.0.1:5173/](http://127.0.0.1:5173/). The API documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Press **Ctrl+C** in the `make dev` terminal to stop both servers. Run `make setup` again when dependencies change.

The basic research flow can use Tavily's keyless search, subject to its free rate limits. You do **not** need an API key just to start the app. Some features need optional keys; see below.

### If you prefer two terminals

After `make setup`, run `make backend` in one terminal and `make frontend` in another. Vite sends `/api` requests to the backend on port 8000. The website runs on port 5173.

### Without Make

```sh
python3 -m venv backend/.venv
(cd backend && .venv/bin/python -m pip install -r requirements-dev.txt)
npm ci
```

Then run `PYTHONPATH=backend backend/.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` from the repository root. In a second terminal, run `npm run dev -- --host 127.0.0.1`.

## Optional API keys

Create a **root-level `.env`** file only for the features you want to enable. Git ignores this file. `.env.example` lists the supported variable names; never put real keys in that example or commit them.

| Variable | What it enables |
| --- | --- |
| `LLM_API_KEY` | Sentinel and Catalyst's Agentic Battle. Without it, the battle cannot start. |
| `EIA_API_KEY` | The EIA electricity data used by site screening. Without it, that layer may be incomplete. |
| `GEMINI_API_KEY` | Optional AI-assisted fact extraction. |
| `API_USGS_PAT` | Optional USGS access; the public water lookup can run without it. |
| `TAVILY_API_KEY` | Higher Tavily search limits; keyless search is the default. |

Brave search is an optional alternate provider. To use it, set `RESEARCH_SEARCH_PROVIDER=brave` and `BRAVE_SEARCH_API_KEY` in `.env`. Restart the backend after changing `.env`.

For scanned PDF text extraction, install Poppler and Tesseract on the backend machine. On macOS: `brew install poppler tesseract`. Text-based PDFs do not require OCR.

## Try the app

1. Enter a ZIP code, city, or state, then select **Explore proposal**.
2. Add an article URL, pasted text, or PDF. The research view shows reviewed sources, reported claims, and missing information. Location-only searches can discover candidate articles, but broad locations may need you to choose a specific project.
3. Open **Satellite map**. The outlined ZIP, city, or state is an approximate research area. Click **Place proposed facility** to mark a point; this is never assumed from a ZIP center. Optionally place your home to see straight-line distance.
4. Confirm an IT capacity and select **Run site screening**. If no unambiguous IT capacity was reported, use a clearly labeled hypothetical value.
5. After screening, open **Agentic Battle**. It needs `LLM_API_KEY` and shows the agents' messages as they arrive. You can print the final report as a PDF.

The 1-, 3-, and 5-mile map rings are distance guides, not risk zones. Regional electricity and water data, assumed equipment noise, and modeled emissions do not establish a facility's actual utility connection, water source, legal noise compliance, or local health effects.

## Checks and troubleshooting

```sh
make check       # frontend tests, production build, backend tests
make help        # list commands
```

- **`npm` or `node` not found:** install Node.js 22+ and reopen your terminal.
- **`python3` not found or too old:** install Python 3.10+; you can choose a specific executable with `make setup PYTHON=python3.12`.
- **Research or screening requests fail:** make sure the backend is running at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Read the backend terminal for request logs and errors.
- **Port 5173 or 8000 is already in use:** stop the older frontend or backend process before running `make dev` again.
- **Agentic Battle says the key is missing:** put `LLM_API_KEY` in the root `.env`, then restart the backend.
- **Satellite imagery is blank:** try the map's **Street** option; raster tiles require network access.

See [technical notes](docs/TECHNICAL.md), [research pipeline plan](docs/RESEARCH_PIPELINE_PLAN.md), and [web progress](docs/web_progress.md) for implementation details and current limitations.
