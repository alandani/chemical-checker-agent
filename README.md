# Chempinski

Chempinski is a Chemical Price Checker for researchers and procurement teams.

A web app (React frontend, FastAPI backend) that answers one question for a researcher: **can I afford this compound, and should I buy it or make it?**

Enter a compound (drawn structure, SMILES, name or CAS), the quantity, minimum purity and budget. The agent checks, from cheapest to most speculative:

1. **Buy it.** Is it sold by one of the vendors, and for how much?
2. **Make it from a known route.** Is there a recorded synthesis? If so, price the starting materials.
3. **Make it from a predicted route.** If there's no known route, predict one with AiZynthFinder and price that.

It returns a report: a budget verdict with a short explanation, vendor prices, the synthesis route with a materials cost table, an option to edit assumptions and recalculate, and HTML/CSV export.

Useful for estimating experiment costs, planning grants and planning manufacturing.

---

## Quick start (local, no API key)

Requires Python 3.11+ and Node.js 20+.

```bash
# 1. Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # optional: add ANTHROPIC_API_KEY
python -m scripts.seed_demo       # creates data/chemchecker.db with sample data
uvicorn api.main:app --reload     # API on http://localhost:8000

# 2. Frontend (second terminal)
cd web
npm install
npm run dev                       # http://localhost:5173, proxies /api to :8000
```

For a single server, build the frontend once (`cd web && npm run build`) and FastAPI serves it at http://localhost:8000.

Open http://localhost:5173 and try:

| Input                                                                    | What it shows                                                       |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| `Topiramate`, 2 g, budget 300                                          | **Buy only**: it's in stock, so route search is skipped       |
| `Topiramate`, 10 g, budget 500, tick *"Also cost a synthesis route"* | Buy vs make, using the 2-step known route                           |
| SMILES `O=C(NCc1ccccc1)c1ccccc1`, 50 g, budget 200                     | **Not sold** by any vendor, so it's costed from a known route |

> The demo data (`data/demo/demo_data.json`) uses **fictional vendors with illustrative prices and yields**. The app labels these as "sample" everywhere they appear. Delete them or run `python -m scripts.seed_demo --no-demo` on a fresh database for real use.

Run the tests:

```bash
pytest
```

## Run with Docker (PostgreSQL + app + nightly worker)

```bash
cp .env.example .env    # add ANTHROPIC_API_KEY
docker compose up --build
```

This starts `db` (PostgreSQL 16), `seed` (creates tables and loads the demo data, then exits), `app` (API and built frontend on port 8000) and `worker` (refreshes prices nightly at 02:00). To include the headless browser for JavaScript-heavy vendor sites, run `docker compose build --build-arg WITH_BROWSER=true`.

---

## Architecture

```mermaid
flowchart TB
    U[Researcher] --> UI[React web app<br/>Ketcher drawing, live progress, report]
    UI -- REST + SSE --> API[FastAPI<br/>api/main.py]
    API
--> P[Pipeline orchestrator<br/>core/pipeline.py]
    P --> R[Resolver<br/>RDKit · PubChem]
    P --> PR[Pricing<br/>AUD per gram]
    P --> RT[Routes<br/>known · AiZynthFinder]
    P --> C[Cost model + explain]
    R --> DB[(PostgreSQL / SQLite<br/>compounds · offers · reactions · runs)]
    PR --> DB
    RT --> DB
    C --> LLM[Claude API]
    PR -- cache miss --> S[Scrapers<br/>httpx/Playwright + Claude Haiku]
    S --> V[Vendor sites]
    W[Worker<br/>nightly refresh] --> S
    S --> DB
```

### Pipeline state machine

Each state is a function in `core/pipeline.py` that updates a shared `RunState` and returns the next state. The run is saved to the database after every state, which makes the progress UI, resuming and History possible.

| State                | Does                                                                                                      | Next                                                                          |
| -------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `RESOLVE`          | Input → standard compound record (InChIKey) via local cache, RDKit, PubChem                              | `CHECK_MARKET`, or `NEEDS_INPUT` if not found or ambiguous                |
| `CHECK_MARKET`     | Fresh offers from the DB; if none, scrape enabled vendors in parallel (per-vendor timeout)                | `COST` if buyable and not comparing ("buy only"), else `FIND_KNOWN_ROUTE` |
| `FIND_KNOWN_ROUTE` | Chains recorded reactions backwards from the target                                                       | `PRICE_MATERIALS`, or `PREDICT_ROUTE` if none                             |
| `PREDICT_ROUTE`    | AiZynthFinder search; Claude ranks the top routes                                                         | `PRICE_MATERIALS`, or `COST` if no route                                  |
| `PRICE_MATERIALS`  | Works out the grams of each starting material (accounting for yields and equivalents) and prices each one | `COST`                                                                      |
| `COST`             | Cost to buy vs cost to make, compared with the budget                                                     | `EXPLAIN`                                                                   |
| `EXPLAIN`          | Claude writes 2–4 sentences from the computed numbers (template fallback)                                | `DONE`                                                                      |

Failures along the way are recorded as warnings on the run, so the report always renders. Only `NEEDS_INPUT` and `DONE` end a run.

### Cost model

```
grams of starting material = (target grams / target MW) / yield of each step × equivalents × MW
make cost  = Σ cheapest whole-pack purchase for each starting material × (1 + consumables margin)
buy cost   = cheapest whole-pack purchase of the target meeting minimum purity
verdict    = min(buy, make) ≤ budget
```

Unknown yields use the "assumed yield per step" setting (default 70%). An unpriced starting material is flagged and the make cost is marked incomplete; it's never treated as free. All prices are converted to AUD using live ECB rates (Frankfurter API), with approximate fallback rates if the API can't be reached.

---

### API

Interactive docs at http://localhost:8000/docs.

| Endpoint                                                                             | Purpose                                                                              |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| `POST /api/resolve`                                                                | Name, CAS or SMILES to a compound, or a list of candidates                           |
| `POST /api/runs`                                                                   | Start an analysis in the background, returns `run_id`                              |
| `GET /api/runs/{id}/events`                                                        | Server-Sent Events: one `stage` event per step, then `done` with the full result |
| `GET /api/runs/{id}`                                                               | Current state of a run                                                               |
| `POST /api/runs/{id}/recost`                                                       | Change quantity, budget, yield or margin and recalculate                             |
| `POST /api/runs/{id}/compound`                                                     | Pick a compound for a run that stopped at "needs input"                              |
| `GET /api/runs`                                                                    | History                                                                              |
| `GET /api/svg/molecule`, `/api/svg/reaction`                                     | RDKit drawings, light or dark theme                                                  |
| `GET /api/runs/{id}/export/report.html`, `.../offers.csv`, `.../materials.csv` | Exports                                                                              |
| `GET /api/admin/overview`, `POST /api/admin/scrape`, `POST /api/admin/demo`    | Data page                                                                            |

### Web UI

- **New analysis**: enter a name, CAS or SMILES, or draw the structure in Ketcher. The structure shows on a graph-paper plate so you can confirm it before running.
- **Report**: the stages show live while the run is in progress. The verdict is drawn as a titration scale: the budget is the endpoint, and the buy and make costs are plotted against it. Changing an assumption in the side panel (quantity, budget, yield, margin) recalculates the cost and moves the readings on the scale.
- **History** and **Data**: past runs, vendor health, on-demand vendor search, and sample data.
- Light and dark themes (follows the system setting, with a toggle in the sidebar).

## Project layout

```
api/
  main.py               FastAPI routes: resolve, runs (+ SSE progress), recost, SVG drawings, exports, admin
  runs.py               runs the pipeline in a background thread and collects stage events
web/                    React + TypeScript + Tailwind frontend (Vite)
  src/pages/            Analyze · Report · History · Data
  src/components/       TitrationScale (budget verdict), StageTrack, RouteSteps, tables, StructureEditor (Ketcher)
core/
  models.py             Pydantic models (Query, Compound, Offer, Route, RunState, ...)
  pipeline.py           state machine
  resolver.py           RESOLVE (RDKit + PubChem PUG REST)
  pricing.py            offer lookup, on-demand scraping, normalisation, cheapest purchase
  routes.py             known routes + AiZynthFinder
  cost.py               starting-material quantities + cost breakdown
  explain.py            Claude summary with template fallback
  report.py             HTML report and CSV exports
  db.py / repository.py SQLAlchemy schema and data access
  chem.py, units.py, fx.py, llm.py, config.py
scrapers/
  vendors.py            the 11 vendors from the deck
  generic.py            fetch search page → Claude Haiku extracts offers as JSON
  registry.py           vendor key → scraper; add custom scrapers here
scripts/
  seed_demo.py          create tables, register vendors, load sample data
  load_reactions.py     load a USPTO-style reaction CSV
  scrape.py             scrape one compound from the CLI
worker/scheduler.py     nightly refresh (APScheduler)
data/demo/              sample data for offline demos
tests/                  pytest suite (runs offline on the sample data)
```

---

## Setting up real data

### 1. Vendor scraping

All 11 vendors from the deck are listed in `scrapers/vendors.py`. **None of the search URLs have been tested against the live sites yet.** For each vendor you want to use:

1. Open the vendor's site, search for a CAS number (e.g. `97240-79-4`), and copy the real search URL into `search_url` with `{q}` in place of the term.
2. Set `requires_js=True` if prices only appear after JavaScript runs, and install the browser: `pip install playwright && playwright install chromium`.
3. Test it: `python -m scripts.scrape 97240-79-4 --vendor <key>`.
4. Once it works, set `verified=True` and add the key to `ENABLED_VENDORS` in `.env`.

The generic scraper sends the page text to Claude Haiku, which returns structured offers (pack, price, currency, purity, quote-only). That's why `ANTHROPIC_API_KEY` is needed for live prices. If a site needs more than one page (product sub-pages, pagination), subclass `GenericSearchScraper` and register it in `scrapers/registry.py`.

Check each vendor's terms of use and robots.txt before scraping, keep request rates low, and prefer an official API or data feed where one exists.

### 2. Known reactions (USPTO)

Load any CSV with a reaction SMILES column (`reactants>reagents>products`; atom maps are stripped automatically), or with separate `reactants` and `product` columns:

```bash
python -m scripts.load_reactions data/uspto_50k.csv --rxn-col rxn_smiles --limit 50000
```

Optional columns: `yield`, `conditions`, `reference`. Publicly available USPTO extracts (e.g. USPTO-50k) and the Open Reaction Database both work once exported to CSV.

### 3. Route prediction (AiZynthFinder, optional)

```bash
pip install aizynthfinder
download_public_data data/aizynth        # public USPTO model + ZINC stock (several GB)
echo "AIZYNTH_CONFIG=data/aizynth/config.yml" >> .env
```

Without this, the pipeline skips prediction and adds a note to the report. The model loads once per process (`core/routes.py`). Searches are capped at `AIZYNTH_TIME_LIMIT_S` (default 90 s).

---

## Configuration (`.env`)

| Variable                    | Default                             | Purpose                                                                                                      |
| --------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `ANTHROPIC_API_KEY`       | –                                  | Price extraction, route ranking and summaries. Without it, the app uses cached/sample data and template text |
| `CLAUDE_MODEL_REASONING`  | `claude-sonnet-5-5`               | Route ranking and summary                                                                                    |
| `CLAUDE_MODEL_EXTRACTION` | `claude-haiku-5-5`                | Pulling offers out of vendor pages                                                                           |
| `DATABASE_URL`            | `sqlite:///data/chemchecker.db`   | e.g. `postgresql+psycopg://user:pass@host/db`                                                              |
| `ENABLE_LIVE_SCRAPING`    | `true`                            | Turn off for offline demos                                                                                   |
| `ENABLED_VENDORS`         | `bldpharm,enamine,medchemexpress` | Vendor keys from `scrapers/vendors.py`                                                                     |
| `OFFER_MAX_AGE_DAYS`      | `7`                               | Cached offers older than this are re-scraped                                                                 |
| `SCRAPE_TIMEOUT_S`        | `30`                              | Per-vendor timeout                                                                                           |
| `AIZYNTH_CONFIG`          | –                                  | Path to AiZynthFinder `config.yml`                                                                         |

## Known limitations / next steps

- Vendor search URLs need checking against the live sites (see above). Some vendors hide prices behind a login or quote request; these show as "Request quote".
- Pack sizes sold by volume (mL/L) can't be compared per gram without a density, so they're stored but not priced. Adding densities for common solvents would fix this.
- Solvents and reagents that don't end up in the product are covered by the consumables margin, not priced individually.
- PDF export is "download HTML, then print to PDF" to avoid system dependencies. WeasyPrint can be added for server-side PDFs.
- Competitor reference: ChemCupid (Japanese market). Where this project differs: multiple vendors across regions, costing via synthesis routes, and a budget verdict.
