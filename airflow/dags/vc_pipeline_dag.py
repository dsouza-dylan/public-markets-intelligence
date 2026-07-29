from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timezone, timedelta
import duckdb
import requests
import time

HEADERS = {"User-Agent": "VC Pipeline Project research@vc-pipeline.com"}

COMPANIES = {
    "AAPL":  "0000320193", "MSFT":  "0000789019", "GOOGL": "0001652044",
    "META":  "0001326801", "AMZN":  "0001018724", "NVDA":  "0001045810",
    "TSLA":  "0001318605", "JPM":   "0000019617", "GS":    "0000886982",
    "BAC":   "0000070858", "JNJ":   "0000200406", "PFE":   "0000078003",
    "UNH":   "0000731766", "XOM":   "0000034088", "CVX":   "0000093410",
    "WMT":   "0000104169", "MCD":   "0000063754", "BA":    "0000012927",
    "V":     "0001403161", "MA":    "0001141391",
}

SECTORS = {
    "AAPL": "Technology",    "MSFT": "Technology",    "GOOGL": "Technology",
    "META": "Technology",    "AMZN": "E-Commerce",    "NVDA":  "Technology",
    "TSLA": "Automotive",    "JPM":  "Finance",        "GS":    "Finance",
    "BAC":  "Finance",       "JNJ":  "Healthcare",     "PFE":   "Healthcare",
    "UNH":  "Healthcare",    "XOM":  "Energy",         "CVX":   "Energy",
    "WMT":  "Retail",        "MCD":  "Food & Beverage","BA":    "Aerospace",
    "V":    "Finance",       "MA":   "Finance",
}

REVENUE_TAGS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
]

def get_annual_metric(facts, tags):
    for tag in tags:
        if tag in facts.get("us-gaap", {}):
            entries = facts["us-gaap"][tag]["units"].get("USD", [])
            annual = [e for e in entries if e.get("form") == "10-K" and e.get("fp") == "FY"]
            if annual:
                return {e["fy"]: e["val"] for e in annual}
    return {}

def get_quarterly_ytd(facts, tags):
    for tag in tags:
        if tag in facts.get("us-gaap", {}):
            entries = facts["us-gaap"][tag]["units"].get("USD", [])
            quarterly = [
                e for e in entries
                if e.get("form") == "10-Q"
                and e.get("fp") in ("Q1", "Q2", "Q3")
                and "start" in e and "end" in e
            ]
            if quarterly:
                return quarterly
    return []

def ingest_sec():
    import pandas as pd
    annual_records = []
    quarterly_records = []

    for ticker, cik in COMPANIES.items():
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print(f"  Failed {ticker}: HTTP {resp.status_code}")
            continue

        data = resp.json()
        facts = data.get("facts", {})
        company_name = data.get("entityName", ticker)
        sector = SECTORS.get(ticker, "Other")

        rev     = get_annual_metric(facts, REVENUE_TAGS)
        net_inc = get_annual_metric(facts, ["NetIncomeLoss"])
        op_inc  = get_annual_metric(facts, ["OperatingIncomeLoss"])
        assets  = get_annual_metric(facts, ["Assets"])

        all_years = sorted(set(rev) | set(net_inc) | set(op_inc))
        for year in [y for y in all_years if y >= 2019]:
            annual_records.append({
                "ticker": ticker, "company_name": company_name, "sector": sector,
                "fiscal_year": year, "revenue": rev.get(year),
                "net_income": net_inc.get(year), "operating_income": op_inc.get(year),
                "total_assets": assets.get(year),
            })

        q_rev = get_quarterly_ytd(facts, REVENUE_TAGS)
        q_ni  = get_quarterly_ytd(facts, ["NetIncomeLoss"])
        q_op  = get_quarterly_ytd(facts, ["OperatingIncomeLoss"])

        q_rev_idx = {(e["fy"], e["fp"]): e for e in q_rev}
        q_ni_idx  = {(e["fy"], e["fp"]): e for e in q_ni}
        q_op_idx  = {(e["fy"], e["fp"]): e for e in q_op}

        for fy, fp in [(fy, fp) for fy, fp in set(q_rev_idx) | set(q_ni_idx) if fy >= 2019]:
            rev_entry = q_rev_idx.get((fy, fp), {})
            quarterly_records.append({
                "ticker": ticker, "company_name": company_name, "sector": sector,
                "fiscal_year": fy, "period": fp,
                "period_start": rev_entry.get("start") or q_ni_idx.get((fy, fp), {}).get("start"),
                "period_end":   rev_entry.get("end")   or q_ni_idx.get((fy, fp), {}).get("end"),
                "ytd_revenue":    rev_entry.get("val"),
                "ytd_net_income": q_ni_idx.get((fy, fp), {}).get("val"),
                "ytd_op_income":  q_op_idx.get((fy, fp), {}).get("val"),
            })

        print(f"  {ticker}: {len([y for y in all_years if y >= 2019])} annual, {len(quarterly_records)} quarterly cumulative")
        time.sleep(0.15)

    df_annual    = pd.DataFrame(annual_records)
    df_quarterly = pd.DataFrame(quarterly_records)

    con = duckdb.connect("/opt/airflow/vc_pipeline.duckdb")
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE OR REPLACE TABLE raw.sec_financials AS SELECT * FROM df_annual")
    con.execute("CREATE OR REPLACE TABLE raw.sec_quarterly  AS SELECT * FROM df_quarterly")
    rows = len(df_annual) + len(df_quarterly)
    con.close()
    print(f"SEC ingest complete: {rows} total rows")
    return rows

def ingest_market_cap():
    import yfinance as yf
    import pandas as pd

    tickers = list(COMPANIES.keys())
    records = []
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            records.append({
                "ticker":             ticker,
                "market_cap":         info.get("marketCap"),
                "current_price":      info.get("currentPrice") or info.get("regularMarketPrice"),
                "shares_outstanding": info.get("sharesOutstanding"),
                "as_of":              pd.Timestamp.now().date().isoformat(),
            })
        except Exception as e:
            print(f"  {ticker}: failed — {e}")

    df = pd.DataFrame(records)
    con = duckdb.connect("/opt/airflow/vc_pipeline.duckdb")
    con.execute("CREATE OR REPLACE TABLE raw.market_cap AS SELECT * FROM df")
    rows = len(df)
    con.close()
    print(f"Market cap ingest complete: {rows} rows")
    return rows

def log_pipeline_run(**context):
    sec_rows = context["ti"].xcom_pull(task_ids="ingest_sec") or 0
    mkt_rows = context["ti"].xcom_pull(task_ids="ingest_market_cap") or 0
    rows = sec_rows + mkt_rows
    con = duckdb.connect("/opt/airflow/vc_pipeline.duckdb")
    con.execute("CREATE SCHEMA IF NOT EXISTS pipeline_metadata")
    con.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_metadata.runs (
            run_at TIMESTAMP,
            status VARCHAR,
            rows_loaded INTEGER
        )
    """)
    con.execute(f"""
        INSERT INTO pipeline_metadata.runs VALUES ('{datetime.now(timezone.utc)}', 'success', {rows})
    """)
    con.close()

with DAG(
    dag_id="vc_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule="@weekly",
    catchup=False,
    max_active_runs=1
) as dag:

    ingest_sec_task = PythonOperator(
        task_id="ingest_sec",
        python_callable=ingest_sec,
        retries=3,
        retry_delay=timedelta(minutes=5)
    )

    ingest_mkt_task = PythonOperator(
        task_id="ingest_market_cap",
        python_callable=ingest_market_cap,
        retries=3,
        retry_delay=timedelta(minutes=2)
    )

    dbt_task = BashOperator(
        task_id="dbt_run",
        bash_command=(
            "cd /opt/airflow/vc_dbt && "
            "dbt run --profiles-dir /opt/airflow/vc_dbt --project-dir /opt/airflow/vc_dbt"
        )
    )

    log_task = PythonOperator(
        task_id="log_run",
        python_callable=log_pipeline_run,
        provide_context=True
    )

    [ingest_sec_task, ingest_mkt_task] >> dbt_task >> log_task