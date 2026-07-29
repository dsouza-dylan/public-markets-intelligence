import yfinance as yf
import duckdb
import pandas as pd
import os

TICKERS = [
    "AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA",
    "INTC", "IBM", "CSCO", "QCOM", "ADBE", "CRM", "AMD", "ORCL",
    "JPM", "GS", "BAC", "V", "MA", "WFC", "MS", "C", "AXP", "BLK",
    "JNJ", "PFE", "UNH", "ABBV", "MRK", "LLY", "AMGN", "BMY", "TMO", "ABT",
    "XOM", "CVX", "COP", "SLB",
    "WMT", "MCD", "COST", "HD", "TGT", "NKE", "SBUX", "LOW",
    "BA", "CAT", "HON", "GE", "RTX",
    "VZ", "T",
]

records = []
for ticker in TICKERS:
    try:
        info = yf.Ticker(ticker).info
        market_cap = info.get("marketCap")
        records.append({
            "ticker":             ticker,
            "market_cap":         market_cap,
            "current_price":      info.get("currentPrice") or info.get("regularMarketPrice"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "as_of":              pd.Timestamp.now().date().isoformat(),
        })
        print(f"  {ticker}: ${market_cap/1e9:.1f}B" if market_cap else f"  {ticker}: no market cap")
    except Exception as e:
        print(f"  {ticker}: failed — {e}")

df = pd.DataFrame(records)
print(f"\n{df['market_cap'].notna().sum()}/{len(TICKERS)} companies loaded")

token = os.environ["MOTHERDUCK_TOKEN"]
con = duckdb.connect(f"md:?motherduck_token={token}")
con.execute("CREATE DATABASE IF NOT EXISTS vc_pipeline")
con.execute("USE vc_pipeline")
con.execute("CREATE OR REPLACE TABLE raw.market_cap AS SELECT * FROM df")
con.close()
print("Loaded into MotherDuck raw.market_cap")
