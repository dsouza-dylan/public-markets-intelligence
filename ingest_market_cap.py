import yfinance as yf
import duckdb
import pandas as pd

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
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        shares = info.get("sharesOutstanding")
        records.append({
            "ticker":             ticker,
            "market_cap":         market_cap,
            "current_price":      price,
            "shares_outstanding": shares,
            "as_of":              pd.Timestamp.now().date().isoformat(),
        })
        print(f"  {ticker}: ${market_cap/1e9:.1f}B" if market_cap else f"  {ticker}: no market cap")
    except Exception as e:
        print(f"  {ticker}: failed — {e}")

df = pd.DataFrame(records)
print(f"\n{df['market_cap'].notna().sum()}/{len(TICKERS)} companies loaded")

con = duckdb.connect("vc_pipeline.duckdb")
con.execute("CREATE SCHEMA IF NOT EXISTS raw")
con.execute("CREATE OR REPLACE TABLE raw.market_cap AS SELECT * FROM df")
con.close()
print("Loaded into raw.market_cap")
