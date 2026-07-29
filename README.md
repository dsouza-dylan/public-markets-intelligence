# 📈 Public Markets Intelligence

A live financial comps pipeline pulling SEC EDGAR filings for 41 large-cap public companies. Computes annual and LTM (Last Twelve Months) revenue, margins, and valuation multiples — refreshed weekly and served via a Streamlit dashboard.

## ✨ Features

- Annual comps with YoY revenue growth and within-sector percentile rankings
- LTM comps using the standard investment banking formula: Most Recent Annual + Current YTD − Prior Year Same Period YTD
- Valuation multiples — P/E and Price/Revenue — pulled live from Yahoo Finance
- Sector filtering, company deep-dive view, and company logos

## 📊 Data

- **SEC EDGAR XBRL API** — 10-K annual and 10-Q quarterly filings, free with no API key
- **Yahoo Finance** (`yfinance`) — live market cap and share price
- Companies covered: AAPL, MSFT, GOOGL, META, AMZN, NVDA, TSLA, JPM, GS, BAC, JNJ, PFE, UNH, XOM, CVX, WMT, MCD, and 38 more across Technology, Finance, Healthcare, Energy, Retail, Industrial, and Telecom

## 🛠️ Built with

- **Ingestion** — Python, requests, yfinance
- **Warehouse** — DuckDB (local) / MotherDuck (cloud)
- **Transformation** — dbt Core with staging → mart layering
- **Orchestration** — Apache Airflow (local) / GitHub Actions (cloud, weekly schedule)
- **Frontend** — Streamlit, Plotly

## 🏗️ Architecture

```
SEC EDGAR API + Yahoo Finance
          │
          ▼
   ingest_sec.py
   ingest_market_cap.py
          │
          ▼
   DuckDB / MotherDuck (raw schema)
          │
          ▼
        dbt
   staging/ → marts/
   (LTM formula, margins, multiples, percentiles)
          │
          ▼
   Streamlit dashboard
```

## 🚀 Running locally

```bash
pip install -r requirements.txt
cp vc_dbt/profiles.yml.example vc_dbt/profiles.yml
# edit profiles.yml and set path to your local .duckdb file

python ingest_sec.py
python ingest_market_cap.py
cd vc_dbt && dbt run && cd ..
streamlit run app.py
```

## ☁️ Deployment

Deployed with MotherDuck (cloud DuckDB) + Streamlit Community Cloud. GitHub Actions runs the full pipeline every Monday at 8am UTC — no manual intervention required.

## 🧑‍💻 Author

Built by Dylan Dsouza.
