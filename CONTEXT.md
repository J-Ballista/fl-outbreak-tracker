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
| FL DOH School Immunization Survey | Annual vaccination/exemption rates by county and facility type | Seeded with synthetic data (realistic variance); real scraper TBD |
| Local FL news RSS feeds | Free-text outbreak signals extracted via NLP | Scraper built (Orlando Sentinel, Miami Herald, Tampa Bay Times, etc.); seeded with 20 sample articles |
| Seed data (synthetic) | Fills gaps while real scrapers are being fixed | 1,507 disease case rows, 2,412 vaccination rate rows, 20 article signals |

**Note on CHARTS scraper:** The report path `Chapt7.T7_2` now redirects to an AppError page — the FL CHARTS portal has changed its URL scheme. The scraper logic and CSV parsing are correct; only the endpoint URL needs updating once the new path is found on the CHARTS site.

---

## Database Models

```
County              67 FL counties, FIPS, population, centroid lat/lng
Disease             12 vaccine-preventable diseases, ICD-10, herd threshold %, R₀
DiseaseCase         Case counts per county/disease/date — TimescaleDB hypertable
VaccinationRate     Annual survey results per county/disease/facility type
NewsArticle         Raw articles from RSS feeds (url, title, source, body_text)
ArticleSignal       NLP-extracted signals: county, disease, case count, confidence
OutbreakAlert       Threshold breach alerts (watch / warning / emergency) — future
```

**Important migration note:** `disease_cases` uses a composite PK `(id, report_date)` — required by TimescaleDB because the hypertable partitions on `report_date`, and all unique indexes must include the partition key.

---

## API Endpoints

```
GET /counties/                         All 67 counties
GET /counties/{fips}                   Single county
GET /diseases/                         All 12 tracked diseases
GET /diseases/{id}                     Single disease
GET /cases/                            Individual case records (filterable)
GET /cases/summary                     Aggregated totals per county for choropleth
                                         → returns total_cases, confirmed_total, probable_total
GET /vaccination-rates/summary         Avg vaccination rate per county (for map layer)
GET /vaccination-rates/county/{fips}   Per-disease vaccination rates for one county
GET /news/signals                      Article signals joined with article metadata
                                         → includes article_url (clickable source link)
```

All case and vaccination endpoints accept `disease_id`, `date_from`, `date_to` query params.

---

## Frontend Structure

```
app/
  page.tsx                  Main dashboard — state orchestration hub
  components/
    FilterBar.tsx            Disease dropdown + MonthRangeSlider
    MonthRangeSlider.tsx     Dual-thumb slider over 24 rolling months
    FloridaMap.tsx           D3 SVG choropleth — Cases / Vaccination Rate toggle
    CountyDetailPanel.tsx    Slide-out panel: KPIs, vacc rates, news article links
    Tooltip.tsx              Hover tooltip (cases or vacc % depending on layer mode)
    Legend.tsx               Colour scale legend with dynamic label
  hooks/
    useMapData.ts            SWR hooks: useCounties, useDiseases, useCasesSummary,
                               useVaccinationSummary, useCountyVaccRates, useNewsSignals
  lib/
    api.ts                   Typed fetch functions + all TypeScript interfaces
```

---

## UI/UX Design Decisions

### Map layers
The choropleth has two modes toggled by pill buttons above the map:
- **Cases** — white→red sequential scale, domain = [0, max cases]
- **Vaccination Rate** — white→green sequential scale, domain = [min%, max%]

### County detail panel
Clicking any county (on map or in the table below) slides in a panel from the right with:
1. **Cases box row** — Total / Confirmed / Probable for the current filter window
2. **Vaccination rate bar** — Overall avg with progress bar; amber warning if < 90%; per-disease table with colour-coded %s (green ≥ 90, amber 85–90, red < 85)
3. **News signals list** — Article titles as hyperlinks to source URLs, outlet name, publish date, extracted case count, NLP confidence badge

### Date filter
A dual-thumb month range slider covers the most recent 24 months. Moving the sliders converts to `date_from` / `date_to` ISO strings that drive all API calls. "From" and "To" labels show the selected month/year.

### County table
The table below the map now includes Confirmed, Probable, Per-100k, and Vaccination % columns. Clicking a table row opens the same county detail panel as clicking the map.

---

## Known Gaps / Future Ideas

| Topic | Notes |
|---|---|
| CHARTS scraper fix | Find the updated report URL on `flhealthcharts.gov` and update `CHARTS_REPORT_PARAMS` in `backend/scrapers/fl_charts.py` |
| Real vaccination data | Build a scraper for the actual FL DOH school immunization PDFs/exports to replace synthetic seed data |
| News scraper live run | The `news_feed.py` scraper is functional — run it against live RSS feeds and confirm signals are stored correctly |
| Outbreak alerts | `OutbreakAlert` model and router are stubbed but not surfaced in UI — could add a banner or badge on counties with active alerts |
| Age group breakdown | `DiseaseCase.age_group` field exists; could add a bar chart in the county panel showing case distribution by age |
| Acquisition type | `DiseaseCase.acquisition` (community / travel / unknown) is stored but not visualised |
| Trend sparkline | A small time-series line per county in the panel would show whether cases are rising or falling |
| Real-time alerts | Subscribe to FL DOH weekly VPD report emails and ingest them via a cron job |
| Authentication | Currently no auth — add if the dashboard moves to a production environment with private data |
| NLP upgrade | Swap the regex classifier in `backend/nlp/classifier.py` for a spaCy NER model for better entity extraction from news text |
| Herd-immunity colour scale | Vaccination map layer should colour counties relative to each disease's herd immunity threshold — dark green = well above, light green = just above, light red = just below, dark red = significantly below. Use `disease.herd_threshold_pct` as the pivot point. |
| News deduplication | When an article signals a disease, contextualise it against existing records by allegation target and date window to avoid double-counting the same outbreak across multiple articles. |
| Expand news sources | Current seed articles used fake/removed URLs. Need a broader, more robust source strategy — e.g. Google News RSS for disease+state queries, CDC health advisory feeds, Florida Health News, and verified local outlets. Seed articles should be replaced with real crawled content. Reference search: `measles miami site:*.com` style queries surface many valid FL sources. |
| Month slider UX | Replace the current two separate From/To sliders with a single range bar that has two draggable endpoints (standard range slider pattern). Visual should show the selected span highlighted between the two handles. |
| County panel — YoY analytics | In the county detail panel, add year-over-year change for each disease: vaccination rate YoY Δ%, confirmed case count YoY Δ, and YoY % change. Compare most recent survey/report year vs. the prior year. |
| Analytics / BI chart view | Add a second view accessible either from a tab above the map or from inside the county panel. Shows a time-series line/bar chart for vaccination rates and case counts across the 12 diseases. Dropdowns for disease, county, and metric. Include a horizontal dotted reference line per disease showing the herd immunity vaccination % threshold as a benchmark. |

---

## Running Locally

```bash
# 1. Start database
docker compose up -d          # TimescaleDB on port 5432
                              # (existing container: fl-outbreak-db)

# 2. Backend
source venv/bin/activate
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Frontend
cd frontend && npm run dev    # http://localhost:3000

# One-time DB setup (already done)
alembic upgrade head
python scripts/seed_counties.py
python scripts/seed_vaccination_rates.py
python scripts/seed_article_signals.py
# + inline disease seed (see conversation history)
```

**Docker note:** The `docker-compose.yml` tries to start a container named `fl_outbreak_db` but port 5432 is already used by the pre-existing `fl-outbreak-db` container (same image, same DB). Use that container directly — no need to run `docker compose up` again unless that container is stopped.

**GitHub auth:** Uses `gh` CLI (`gh auth login` — browser OAuth). Plain `git push origin main` works after that. No SSH keys or PATs needed. Remote is `https://github.com/J-Ballista/fl-outbreak-tracker.git`.
