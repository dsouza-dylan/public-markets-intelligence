import requests
import pandas as pd
import duckdb
import time
import os

HEADERS = {"User-Agent": "VC Pipeline Project research@vc-pipeline.com"}

COMPANIES = {
    # Technology
    "AAPL":  "0000320193", "MSFT":  "0000789019", "GOOGL": "0001652044",
    "META":  "0001326801", "AMZN":  "0001018724", "NVDA":  "0001045810",
    "TSLA":  "0001318605", "INTC":  "0000050863", "IBM":   "0000051143",
    "CSCO":  "0000858877", "QCOM":  "0000804328", "ADBE":  "0000796343",
    "CRM":   "0001108524", "AMD":   "0000002488", "ORCL":  "0001341439",
    # Finance
    "JPM":   "0000019617", "GS":    "0000886982", "BAC":   "0000070858",
    "V":     "0001403161", "MA":    "0001141391", "WFC":   "0000072971",
    "MS":    "0000895421", "C":     "0000831001", "AXP":   "0000004962",
    "BLK":   "0001364742",
    # Healthcare
    "JNJ":   "0000200406", "PFE":   "0000078003", "UNH":   "0000731766",
    "ABBV":  "0001551152", "MRK":   "0000310158", "LLY":   "0000059478",
    "AMGN":  "0000318154", "BMY":   "0000014272", "TMO":   "0000097745",
    "ABT":   "0001800227",
    # Energy
    "XOM":   "0000034088", "CVX":   "0000093410", "COP":   "0001163165",
    "SLB":   "0000087429",
    # Retail & Consumer
    "WMT":   "0000104169", "MCD":   "0000063754", "COST":  "0000909832",
    "HD":    "0000354950", "TGT":   "0000027419", "NKE":   "0000320187",
    "SBUX":  "0000829224", "LOW":   "0000060667",
    # Industrial & Aerospace
    "BA":    "0000012927", "CAT":   "0000018230", "HON":   "0000773840",
    "GE":    "0000040533", "RTX":   "0000101829",
    # Telecom
    "VZ":    "0000732712", "T":     "0000732717",
}

SECTORS = {
    "AAPL": "Technology",   "MSFT": "Technology",   "GOOGL": "Technology",
    "META": "Technology",   "AMZN": "E-Commerce",   "NVDA":  "Technology",
    "TSLA": "Automotive",   "INTC": "Technology",   "IBM":   "Technology",
    "CSCO": "Technology",   "QCOM": "Technology",   "ADBE":  "Technology",
    "CRM":  "Technology",   "AMD":  "Technology",   "ORCL":  "Technology",
    "JPM":  "Finance",      "GS":   "Finance",      "BAC":   "Finance",
    "V":    "Finance",      "MA":   "Finance",      "WFC":   "Finance",
    "MS":   "Finance",      "C":    "Finance",      "AXP":   "Finance",
    "BLK":  "Finance",
    "JNJ":  "Healthcare",   "PFE":  "Healthcare",   "UNH":   "Healthcare",
    "ABBV": "Healthcare",   "MRK":  "Healthcare",   "LLY":   "Healthcare",
    "AMGN": "Healthcare",   "BMY":  "Healthcare",   "TMO":   "Healthcare",
    "ABT":  "Healthcare",
    "XOM":  "Energy",       "CVX":  "Energy",       "COP":   "Energy",
    "SLB":  "Energy",
    "WMT":  "Retail",       "MCD":  "Food & Beverage", "COST": "Retail",
    "HD":   "Retail",       "TGT":  "Retail",       "NKE":   "Consumer",
    "SBUX": "Food & Beverage", "LOW": "Retail",
    "BA":   "Aerospace",    "CAT":  "Industrial",   "HON":   "Industrial",
    "GE":   "Industrial",   "RTX":  "Aerospace",
    "VZ":   "Telecom",      "T":    "Telecom",
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
    recent = [y for y in all_years if y >= 2019]

    for year in recent:
        annual_records.append({
            "ticker": ticker, "company_name": company_name, "sector": sector,
            "fiscal_year": year, "revenue": rev.get(year),
            "net_income": net_inc.get(year), "operating_income": op_inc.get(year),
            "total_assets": assets.get(year),
        })

    q_rev_idx = {(e["fy"], e["fp"]): e for e in get_quarterly_ytd(facts, REVENUE_TAGS)}
    q_ni_idx  = {(e["fy"], e["fp"]): e for e in get_quarterly_ytd(facts, ["NetIncomeLoss"])}
    q_op_idx  = {(e["fy"], e["fp"]): e for e in get_quarterly_ytd(facts, ["OperatingIncomeLoss"])}

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

    print(f"  {ticker}: {len(recent)} annual, {len(quarterly_records)} quarterly cumulative")
    time.sleep(0.15)

df_annual    = pd.DataFrame(annual_records)
df_quarterly = pd.DataFrame(quarterly_records)

token = os.environ["MOTHERDUCK_TOKEN"]
con = duckdb.connect(f"md:?motherduck_token={token}")
con.execute("CREATE DATABASE IF NOT EXISTS vc_pipeline")
con.execute("USE vc_pipeline")
con.execute("CREATE SCHEMA IF NOT EXISTS raw")
con.execute("CREATE OR REPLACE TABLE raw.sec_financials AS SELECT * FROM df_annual")
con.execute("CREATE OR REPLACE TABLE raw.sec_quarterly  AS SELECT * FROM df_quarterly")
print(f"Loaded {len(df_annual)} annual + {len(df_quarterly)} quarterly rows into MotherDuck")
con.close()
