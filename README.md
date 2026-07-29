# Public Markets Intelligence Pipeline

A data engineering pipeline that ingests live SEC EDGAR filings and surfaces annual and LTM (Last Twelve Months) financial comps for 20 large-cap public companies via a Streamlit dashboard.

## Architecture

```
SEC EDGAR API
     │
     ▼
ingest_sec.py          ← pulls 10-K (annual) + 10-Q (quarterly YTD) via XBRL API
     │
     ▼
DuckDB (raw schema)
  raw.sec_financials
  raw.sec_quarterly
     │
     ▼
dbt (vc_dbt)
  staging/
    stg_sec_financials   ← clean annual metrics + derived margins
    stg_sec_quarterly    ← clean quarterly YTD metrics
  marts/
    mart_public_company_comps   ← annual comps with YoY growth + sector percentiles
    mart_ltm_comps              ← LTM = Annual + Current YTD − Prior Year YTD
     │
     ▼
Streamlit + Plotly (app.py)
  Tab 1: Annual Comps
  Tab 2: LTM Comps
     │
     ▼
Airflow (Docker)        ← orchestrates ingest → dbt on a weekly schedule
```

## Tech Stack

| Layer | Tool |
|---|---|
| Ingestion | Python + requests (SEC EDGAR XBRL API) |
| Warehouse | DuckDB |
| Transformation | dbt Core + dbt-duckdb |
| Orchestration | Apache Airflow (Docker Compose) |
| Frontend | Streamlit + Plotly |

## Data Source

[SEC EDGAR XBRL API](https://www.sec.gov/cgi-bin/browse-edgar) — free, no API key required. Pulls `us-gaap` facts (revenue, net income, operating income) from 10-K and 10-Q filings.

Companies covered: AAPL, MSFT, GOOGL, META, AMZN, NVDA, TSLA, JPM, GS, BAC, JNJ, PFE, UNH, XOM, CVX, WMT, MCD, BA, V, MA

## LTM Formula

Standard investment banking LTM calculation:

```
LTM = Most Recent Annual (10-K)
    + Current YTD Quarter (10-Q)
    − Prior Year Same Period YTD (10-Q)
```

Implemented in `vc_dbt/models/marts/mart_ltm_comps.sql`.

## Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Configure dbt profile**

Copy `vc_dbt/profiles.yml.example` to `vc_dbt/profiles.yml` and update the path:
```bash
cp vc_dbt/profiles.yml.example vc_dbt/profiles.yml
```
Edit `vc_dbt/profiles.yml` and set `path` to the absolute path where you want the DuckDB file created.

**3. Ingest data**
```bash
python ingest_sec.py
```

**4. Run dbt transformations**
```bash
cd vc_dbt
dbt run
dbt test
```

**5. Launch the dashboard**
```bash
streamlit run app.py
```

## Automated Scheduling (Airflow)

To run the pipeline automatically every week via Airflow + Docker:

```bash
cd airflow
docker-compose up -d
```

Then open [http://localhost:8080](http://localhost:8080) (admin / admin). The `vc_pipeline` DAG runs `@weekly` — trigger it manually first to confirm everything works, then leave it running.

> Note: Docker Desktop must be running on your machine for the scheduled runs to execute.
