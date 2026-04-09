# FL Outbreak Tracker — Project Context

## What This Is

A public health surveillance dashboard for Florida vaccine-preventable diseases (VPDs). It pulls case data from official state sources, cross-references with NLP-extracted signals from local news articles, and visualises everything on an interactive county-level choropleth map. The intended audience is anyone who wants to understand disease trends across Florida counties — public health researchers, journalists, or informed citizens.

---

## Core Design Philosophy

- **One screen, full picture.** The main page is a single dashboard. Everything useful — map, filters, county KPIs, source articles — is reachable without navigating away.
- **Show your sources.** Case data can be murky. The app surfaces *where* each signal came from (FL CHARTS, DOH surveys, news articles) so users can verify manually.
- **Layered context, not just numbers.** A raw case count means little without vaccination rate context. Both are shown together so a spike can be read against immunity coverage.
- **Click to dig in, hover to scan.** The map is a navigation surface: hover gives quick stats, clicking a county opens a detail panel with full KPIs and article links.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 16 + TimescaleDB (via Docker) |
| ORM / Migrations | SQLAlchemy (async) + Alembic |
| Backend API | FastAPI (Python, async) |
| Scrapers | httpx + BeautifulSoup (FL CHARTS, RSS news feeds) |
| NLP signals | Regex/keyword classifier (designed to swap for spaCy/BERT later) |
| Frontend | Next.js 16 (App Router, Turbopack), React 19 |
| Map | D3.js v7 — `geoAlbersUsa` projection, SVG choropleth |
| Data fetching | SWR (stale-while-revalidate hooks) |
| Styling | Tailwind CSS v4 |
| GeoJSON source | Plotly's US Census TIGER dataset (FIPS in top-level `id` field, not `properties`) |

---

## Data Sources

| Source | What it provides | Status |
|---|---|---|
| FL Health CHARTS (`flhealthcharts.gov`) | County-level annual VPD case counts | Scraper built; CHARTS URL has changed — needs endpoint update |
| FL DOH School Immunization Survey | Annual vaccination/exemption rates by county and facility type | Seeded with synthetic data (3 years: 2022–2024, realistic Gaussian variance); real scraper TBD |
| Local FL news RSS feeds | Free-text outbreak signals extracted via NLP | Scraper built (8 FL sources); seeded with 20 sample articles |
| Seed data (synthetic) | Fills gaps while real scrapers are being fixed | 1,507 disease case rows, 2,412 vaccination rate rows, 10 outbreak alerts, 20 article signals |

**Note on CHARTS scraper (v2):** The old `Chapt7.T7_2` single-report endpoint is gone. The portal now uses per-disease DataViewer pages keyed by a `cid` parameter. The scraper has been rewritten accordingly:
- URL: `https://www.flhealthcharts.gov/ChartsReports/rdPage.aspx?rdReport=NonVitalIndNoGrpCounts.DataViewer&cid=<ID>`
- Disease CIDs: Measles=129, Mumps=155, Rubella=157, Pertussis=156, Varicella=8633, Hepatitis A=154, Hepatitis B=8659, Meningococcal=8662, Haemophilus Influenzae=167, Tetanus=168, Diphtheria=161, Polio=162
- Strategy: GET page → extract `rdCSRFKey` CSRF token → POST with `county` + `county_year=""` → parse HTML table `dtChartDataGrid_CountsOnly`
- Data is in the HTML (not AJAX). Table columns: Data Year | County Count | FL Count
- Run `python -m backend.scrapers.fl_charts --dry-run` to verify parsing before a full run
- Run `python -m backend.scrapers.fl_charts` for a full ingest (12 diseases × 67 counties, async batched)

**Vaccination data note:** `vaccination_rates` stores one survey per year per county/disease (not monthly). The 3 seeded years (2022, 2023, 2024) are used for the YoY vaccination trend line in the county panel. YoY records are preserved intentionally for trend analytics.

---

## Database Models

```
County              67 FL counties, FIPS, population, centroid lat/lng
Disease             12 vaccine-preventable diseases, ICD-10, herd threshold %, R₀
DiseaseCase         Case counts per county/disease/date — TimescaleDB hypertable
VaccinationRate     Annual survey results per county/disease/facility type
                    (survey_year INTEGER — one row per year/county/disease)
NewsArticle         Raw articles from RSS feeds (url, title, source, body_text)
ArticleSignal       NLP-extracted signals: county, disease, case count, confidence
OutbreakAlert       Threshold breach alerts (watch / warning / emergency)
```

**Important migration note:** `disease_cases` uses a composite PK `(id, report_date)` — required by TimescaleDB because the hypertable partitions on `report_date`, and all unique indexes must include the partition key.

---

## API Endpoints

```
GET /counties/                              All 67 counties
GET /counties/{fips}                        Single county
GET /diseases/                              All 12 tracked diseases
GET /diseases/{id}                          Single disease
GET /cases/                                 Individual case records (filterable)
GET /cases/summary                          Aggregated totals per county for choropleth
                                              → returns total_cases, confirmed_total, probable_total
GET /cases/trend/{fips}                     Monthly case time-series for one county
GET /cases/age-breakdown/{fips}             Case counts by age group for one county
GET /cases/acquisition-breakdown/{fips}     Case counts by acquisition type for one county
GET /vaccination-rates/summary              Avg vaccination rate per county (for map layer)
GET /vaccination-rates/county/{fips}        Per-disease vaccination rates (latest year)
GET /vaccination-rates/county/{fips}/trend  YoY vaccination trend [{survey_year, vaccinated_pct}]
GET /news/signals                           Article signals joined with article metadata
GET /alerts/                                Active outbreak alerts (filterable by county/severity)
POST /alerts/generate                       Scan cases+vacc data and create new alerts
```

All case and vaccination endpoints accept `disease_id`, `date_from`, `date_to` query params.
All routes require `Authorization: Bearer <API_KEY>` when `API_KEY` env var is set (disabled in dev).

---

## Frontend Structure

```
app/
  page.tsx                  Main dashboard — state orchestration hub
  login/page.tsx            Password gate page (blue-900 header, centered form)
  api/login/route.ts        POST: validates password, sets httpOnly session cookie
  middleware.ts             Redirects unauthenticated requests to /login
  analytics/
    page.tsx                Analytics route — disease/county selectors + AnalyticsChart
  components/
    FilterBar.tsx            Disease dropdown + MonthRangeSlider
    MonthRangeSlider.tsx     Single merged range track with two overlaid thumbs (CSS:
                               MonthRangeSlider.css); pointer-events: none on inputs,
                               auto on thumb pseudo-elements
    FloridaMap.tsx           D3 SVG choropleth — Cases / Vaccination Rate toggle
                               + alert ring overlays (watch/warning/emergency)
                               Vaccination layer uses d3.scaleDiverging pivoting at
                               herd_threshold_pct (red→amber→green)
    CountyDetailPanel.tsx    Slide-out panel: Active Alerts, Cases KPIs (with YoY Δ%
                               badge), trend chart, age breakdown bars, acquisition pills,
                               vacc table (with YoY Δ% badge), news links
    TrendSparkline.tsx       Dual-axis D3 chart: red case trend (left) + green vacc YoY
                               trend (right) + amber herd threshold dotted line; hover
                               tooltips on both lines; last month always pinned on X axis
    AnalyticsChart.tsx       Full-width D3 chart for /analytics: cases line + vacc dots
                               + herd threshold dotted line; dual-axis; hover crosshair;
                               responsive via viewBox="0 0 800 400" width="100%"
    Tooltip.tsx              Hover tooltip (cases or vacc % depending on layer mode)
    Legend.tsx               Colour scale legend with dynamic label + optional amber
                               "Herd" tick marker (vaccination layer only)
  hooks/
    useMapData.ts            SWR hooks: useCounties, useDiseases, useCasesSummary,
                               useVaccinationSummary, useCountyVaccRates, useCountyVaccTrend,
                               useNewsSignals, useAlerts, useCaseTrend,
                               useAgeBreakdown, useAcquisitionBreakdown
  lib/
    api.ts                   Typed fetch functions + all TypeScript interfaces
```

---

## UI/UX Design Decisions

### Map layers
The choropleth has two modes toggled by pill buttons above the map:
- **Cases** — white→red sequential scale, domain = [0, max cases]
- **Vaccination Rate** — white→green sequential scale, domain = [min%, max%]
- Alert ring overlays drawn on top of fill: amber (watch), orange (warning), red pulsing dot (emergency)

### County detail panel
Clicking any county (on map or in the table below) slides in a panel from the right with:
1. **Active Alerts** — severity badges + metric description (shown only when alerts exist)
2. **Cases box row** — Total / Confirmed / Probable for the current filter window
3. **Case Trend chart** — Dual-axis D3 sparkline:
   - Red line (left axis): monthly case counts with area fill
   - Green line (right axis): vaccination rate YoY trend (survey_year → Jul 1 of that year)
   - Amber dotted line: herd immunity threshold (static reference)
   - Hover tooltip on both lines: date + case count + vacc % (if available)
   - Last month always shown on X axis in red bold
4. **Age Breakdown** — horizontal bars per age group
5. **Acquisition type** — percentage pills (Community / Travel / Unknown)
6. **Vaccination rate table** — Overall bar + per-disease sortable table
7. **News signals** — Article titles as hyperlinks, outlet, date, NLP confidence

### Date filter
A dual-thumb month range slider covers the most recent 24 months. Moving the sliders converts to `date_from` / `date_to` ISO strings that drive all API calls.

### County table
The table below the map includes Confirmed, Probable, Per-100k, Vaccination %, and Alert severity columns. Clicking a row opens the same county detail panel.

---

## Completed Items (v2 Plan)

| Item | Status |
|---|---|
| Outbreak alerts backend (alert_engine, /alerts/ router) | ✅ Done |
| Alert seed data (10 alerts across all severities) | ✅ Done |
| Trend endpoint `/cases/trend/{fips}` | ✅ Done |
| Age breakdown endpoint `/cases/age-breakdown/{fips}` | ✅ Done |
| Acquisition breakdown endpoint `/cases/acquisition-breakdown/{fips}` | ✅ Done |
| Vaccination YoY trend endpoint `/vaccination-rates/county/{fips}/trend` | ✅ Done |
| Alert ring overlays on map (watch/warning/emergency) | ✅ Done |
| County panel — Active Alerts section | ✅ Done |
| County panel — TrendSparkline with dual axes + hover tooltips | ✅ Done |
| County panel — Age breakdown bars | ✅ Done |
| County panel — Acquisition type pills | ✅ Done |
| Header alert count badge | ✅ Done |
| Alert column in county table | ✅ Done |
| Basic auth — API key middleware (backend) | ✅ Done |
| Basic auth — Next.js password gate + login page | ✅ Done |
| News scraper — 5 additional FL sources added | ✅ Done |
| News scraper — disease ID cache loaded at startup | ✅ Done |
| Docker cron service (cron_runner.py + Dockerfile.scraper) | ✅ Done |
| requirements.txt for reproducible Docker builds | ✅ Done |
| Herd-immunity diverging colour scale on vaccination map layer | ✅ Done |
| Month range slider — single track with two overlaid thumbs | ✅ Done |
| County panel — YoY Δ% badges (vaccination rate + case count) | ✅ Done |
| Analytics / BI chart view (`/analytics` route) | ✅ Done |

## Known Gaps / Future Ideas

| Topic | Notes |
|---|---|
| CHARTS scraper — test & tune | Run `--dry-run` to verify HTML parsing and county_name spelling against live portal; adjust if needed |
| Real vaccination data | Build `backend/scrapers/fl_doh_vacc.py` to pull real FL DOH school immunization exports; replace synthetic seed |
| News scraper live run | Run `python -m backend.scrapers.news_feed` against live feeds; verify signals stored correctly |
| NLP upgrade | Swap the regex classifier in `backend/nlp/classifier.py` for spaCy NER (`en_core_web_sm`) |
| News deduplication | Contextualise signals against existing records by date window to avoid double-counting the same outbreak |

---

## Running Locally

```bash
# 1. Start database
docker compose up -d          # TimescaleDB on port 5432

# 2. Backend
source venv/bin/activate
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Frontend
cd frontend && npm run dev    # http://localhost:3000
# Login: any password (DASHBOARD_PASSWORD not set = dev mode)

# One-time DB setup (already done)
alembic upgrade head
python scripts/seed_counties.py
python scripts/seed_vaccination_rates.py   # 2022–2024, 67 counties, 12 diseases
python scripts/seed_article_signals.py
python scripts/seed_alerts.py              # 10 alerts (watch/warning/emergency)
```

**GitHub auth:** Uses `gh` CLI (`gh auth login` — browser OAuth). `git push origin main` works after that. Remote: `https://github.com/J-Ballista/fl-outbreak-tracker.git`.

**Auth in dev:** Set `API_KEY` in `.env` (backend) and `DASHBOARD_PASSWORD` in `frontend/.env.local` to enable. Leave unset for open dev access.

**Important — backend restart:** `uvicorn --reload` does NOT always auto-reload when new route files are added. After adding new endpoints, always explicitly kill and restart uvicorn:
```bash
pkill -f "uvicorn backend.api.main"
source venv/bin/activate
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Symptom of stale backend: new endpoints return `{"detail":"Not Found"}` (404).
