import streamlit as st
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(
    page_title="Public Markets Intelligence",
    page_icon="📈",
    layout="wide"
)

# Clearbit logo domains — add more as needed
DOMAINS = {
    "AAPL": "apple.com",       "MSFT": "microsoft.com",  "GOOGL": "google.com",
    "META": "meta.com",        "AMZN": "amazon.com",     "NVDA":  "nvidia.com",
    "TSLA": "tesla.com",       "INTC": "intel.com",      "IBM":   "ibm.com",
    "CSCO": "cisco.com",       "QCOM": "qualcomm.com",   "ADBE":  "adobe.com",
    "CRM":  "salesforce.com",  "AMD":  "amd.com",        "ORCL":  "oracle.com",
    "JPM":  "jpmorganchase.com","GS":  "goldmansachs.com","BAC":  "bankofamerica.com",
    "V":    "visa.com",        "MA":   "mastercard.com", "WFC":   "wellsfargo.com",
    "MS":   "morganstanley.com","C":   "citigroup.com",  "AXP":   "americanexpress.com",
    "BLK":  "blackrock.com",
    "JNJ":  "jnj.com",         "PFE":  "pfizer.com",    "UNH":   "unitedhealthgroup.com",
    "ABBV": "abbvie.com",      "MRK":  "merck.com",     "LLY":   "lilly.com",
    "AMGN": "amgen.com",       "BMY":  "bms.com",       "TMO":   "thermofisher.com",
    "ABT":  "abbott.com",
    "XOM":  "exxonmobil.com",  "CVX":  "chevron.com",   "COP":   "conocophillips.com",
    "SLB":  "slb.com",
    "WMT":  "walmart.com",     "MCD":  "mcdonalds.com", "COST":  "costco.com",
    "HD":   "homedepot.com",   "TGT":  "target.com",    "NKE":   "nike.com",
    "SBUX": "starbucks.com",   "LOW":  "lowes.com",
    "BA":   "boeing.com",      "CAT":  "caterpillar.com","HON":  "honeywell.com",
    "GE":   "ge.com",          "RTX":  "rtx.com",
    "VZ":   "verizon.com",     "T":    "att.com",
}

con = duckdb.connect("vc_pipeline.duckdb", read_only=True)

def format_money(amount):
    if pd.isna(amount):
        return "N/A"
    if amount >= 1e12:
        return f"${amount/1e12:.2f}T"
    if amount >= 1e9:
        return f"${amount/1e9:.1f}B"
    elif amount >= 1e6:
        return f"${amount/1e6:.1f}M"
    else:
        return f"${amount:,.0f}"

def format_pct(val):
    if pd.isna(val):
        return "N/A"
    return f"{val:+.1f}%"

def logo_url(ticker):
    domain = DOMAINS.get(ticker)
    return f"https://logo.clearbit.com/{domain}" if domain else None

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("Pipeline Status")

try:
    last_run, total_rows = con.execute("""
        SELECT MAX(run_at), SUM(rows_loaded)
        FROM pipeline_metadata.runs
    """).fetchone()
    last_run_str = str(last_run)[:19] if last_run else None
except Exception:
    last_run_str, total_rows = None, None

if last_run_str:
    st.sidebar.metric("Last Run", last_run_str)
    st.sidebar.metric("Rows Loaded", f"{int(total_rows):,}" if total_rows else "—")
else:
    st.sidebar.metric("Last Run", "Never")
    st.sidebar.info(
        "**Why Never?**\n\n"
        "This updates when the pipeline runs through Airflow. "
        "If you ran `ingest_sec.py` or `ingest_market_cap.py` manually, it won't be recorded here."
    )

try:
    sec_count = con.execute("SELECT COUNT(DISTINCT ticker) FROM main.stg_sec_financials").fetchone()[0]
    st.sidebar.metric("Companies Tracked", sec_count)
except Exception:
    pass

st.sidebar.divider()
st.sidebar.caption(
    "Data: [SEC EDGAR XBRL API](https://www.sec.gov/cgi-bin/browse-edgar)  \n"
    "Free · No API key · Updated on filing"
)

# ── Main ──────────────────────────────────────────────────────────────────────
st.title("Public Markets Intelligence")
st.caption("Live SEC EDGAR 10-K annual + 10-Q quarterly filings")

tab1, tab2 = st.tabs(["Annual Comps", "LTM Comps"])

# ── TAB 1: Annual Comps ───────────────────────────────────────────────────────
with tab1:
    try:
        comps_df = con.execute("""
            SELECT ticker, company_name, sector, fiscal_year,
                   revenue, net_income, operating_income,
                   net_margin_pct, op_margin_pct, revenue_growth_pct,
                   revenue_percentile, margin_percentile, growth_percentile,
                   market_cap, price_to_revenue, pe_ratio
            FROM main.mart_public_company_comps
            QUALIFY fiscal_year = MAX(fiscal_year) OVER (PARTITION BY ticker)
            ORDER BY revenue DESC
        """).df()
        latest_year = int(comps_df["fiscal_year"].max())

        sectors = ["All"] + sorted(comps_df["sector"].dropna().unique().tolist())
        selected_sector = st.selectbox("Filter by sector", sectors, key="annual_sector")
        filtered = comps_df if selected_sector == "All" else comps_df[comps_df["sector"] == selected_sector]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Companies", len(filtered))
        c2.metric("Median Revenue", format_money(filtered["revenue"].median()))
        c3.metric("Median Net Margin", f"{filtered['net_margin_pct'].median():.1f}%")
        c4.metric("Median P/E", f"{filtered['pe_ratio'].median():.1f}x" if filtered["pe_ratio"].notna().any() else "N/A")
        c5.metric("Median P/Revenue", f"{filtered['price_to_revenue'].median():.1f}x" if filtered["price_to_revenue"].notna().any() else "N/A")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            fig_rev = px.bar(
                filtered.sort_values("revenue", ascending=False),
                x="ticker", y="revenue", color="sector",
                title="Revenue by Company (Most Recent Annual)",
                labels={"revenue": "Revenue ($)", "ticker": ""},
                hover_data=["company_name", "net_margin_pct", "revenue_growth_pct"],
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_rev.update_layout(xaxis_tickangle=-45, showlegend=False)
            st.plotly_chart(fig_rev, use_container_width=True)

        with col2:
            fig_margin = px.scatter(
                filtered, x="revenue_growth_pct", y="net_margin_pct",
                color="sector", text="ticker",
                title="Growth vs Net Margin",
                labels={"revenue_growth_pct": "YoY Revenue Growth (%)", "net_margin_pct": "Net Margin (%)"},
                hover_data=["company_name", "revenue"],
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_margin.update_traces(textposition="top center")
            fig_margin.add_hline(y=0, line_dash="dash", line_color="lightgray")
            fig_margin.add_vline(x=0, line_dash="dash", line_color="lightgray")
            st.plotly_chart(fig_margin, use_container_width=True)

        st.subheader("Comps Table")
        display = filtered[[
            "ticker", "company_name", "sector", "fiscal_year", "revenue",
            "net_margin_pct", "op_margin_pct", "revenue_growth_pct",
            "market_cap", "price_to_revenue", "pe_ratio"
        ]].copy()
        display["company_name"] = display["company_name"] + " (" + display["ticker"] + ")"
        display = display.drop(columns=["ticker"])
        display["revenue"]           = display["revenue"].apply(format_money)
        display["market_cap"]        = display["market_cap"].apply(format_money)
        display["net_margin_pct"]    = display["net_margin_pct"].apply(lambda x: f"{x:.1f}%" if not pd.isna(x) else "N/A")
        display["op_margin_pct"]     = display["op_margin_pct"].apply(lambda x: f"{x:.1f}%" if not pd.isna(x) else "N/A")
        display["revenue_growth_pct"]= display["revenue_growth_pct"].apply(format_pct)
        display["price_to_revenue"]  = display["price_to_revenue"].apply(lambda x: f"{x:.1f}x" if not pd.isna(x) else "N/A")
        display["pe_ratio"]          = display["pe_ratio"].apply(lambda x: f"{x:.1f}x" if not pd.isna(x) else "N/A")
        display.columns = ["Company", "Sector", "FY", "Revenue", "Net Margin", "Op Margin", "YoY Growth", "Mkt Cap", "P/Revenue", "P/E"]
        st.dataframe(display, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Company Deep Dive")

        ticker_to_name = dict(zip(comps_df["ticker"], comps_df["company_name"]))
        company_options = sorted(comps_df["ticker"].unique().tolist(), key=lambda t: ticker_to_name.get(t, t))
        display_options = [f"{ticker_to_name.get(t, t)} ({t})" for t in company_options]

        col_sel, col_logo = st.columns([4, 1])
        with col_sel:
            selected_display = st.selectbox("Select a company", display_options, key="annual_ticker")
            selected_ticker = company_options[display_options.index(selected_display)]
        with col_logo:
            url = logo_url(selected_ticker)
            if url:
                st.image(url, width=60)

        trend_df = con.execute(f"""
            SELECT fiscal_year, revenue, net_margin_pct, op_margin_pct, revenue_growth_pct
            FROM main.mart_public_company_comps
            WHERE ticker = '{selected_ticker}'
            ORDER BY fiscal_year
        """).df()

        col3, col4 = st.columns(2)
        with col3:
            fig_trend = px.area(
                trend_df, x="fiscal_year", y="revenue",
                title=f"{selected_ticker} — Revenue Over Time",
                labels={"fiscal_year": "Year", "revenue": "Revenue ($)"},
                markers=True, color_discrete_sequence=["#636EFA"]
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        with col4:
            fig_margins = go.Figure()
            fig_margins.add_trace(go.Scatter(
                x=trend_df["fiscal_year"], y=trend_df["net_margin_pct"],
                mode="lines+markers", name="Net Margin %", line=dict(color="#00CC96")
            ))
            fig_margins.add_trace(go.Scatter(
                x=trend_df["fiscal_year"], y=trend_df["op_margin_pct"],
                mode="lines+markers", name="Op Margin %", line=dict(color="#EF553B")
            ))
            fig_margins.update_layout(
                title=f"{selected_ticker} — Margins Over Time",
                xaxis_title="Year", yaxis_title="Margin (%)"
            )
            st.plotly_chart(fig_margins, use_container_width=True)

    except Exception as e:
        st.warning("Annual data not loaded. Run `python ingest_sec.py` then `dbt run`.")
        st.caption(str(e))

# ── TAB 2: LTM Comps ─────────────────────────────────────────────────────────
with tab2:
    st.caption("LTM = Most Recent Annual  +  Current YTD Quarter  −  Prior Year Same Quarter YTD")

    try:
        ltm_df = con.execute("""
            SELECT ticker, company_name, sector,
                   annual_fy, ltm_fy, ltm_period, ltm_as_of,
                   annual_revenue, ltm_revenue,
                   annual_net_margin_pct, ltm_net_margin_pct,
                   annual_op_margin_pct,  ltm_op_margin_pct,
                   ltm_vs_annual_growth_pct,
                   ltm_net_income, ltm_op_income,
                   market_cap, ltm_price_to_revenue, ltm_pe_ratio
            FROM main.mart_ltm_comps
            ORDER BY ltm_revenue DESC NULLS LAST
        """).df()

        sectors_ltm = ["All"] + sorted(ltm_df["sector"].dropna().unique().tolist())
        selected_sector_ltm = st.selectbox("Filter by sector", sectors_ltm, key="ltm_sector")
        filtered_ltm = ltm_df if selected_sector_ltm == "All" else ltm_df[ltm_df["sector"] == selected_sector_ltm]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Companies with LTM", filtered_ltm["ltm_revenue"].notna().sum())
        c2.metric("Median LTM Revenue", format_money(filtered_ltm["ltm_revenue"].median()))
        median_ltm_margin = filtered_ltm["ltm_net_margin_pct"].median()
        c3.metric("Median LTM Net Margin", f"{median_ltm_margin:.1f}%" if not pd.isna(median_ltm_margin) else "N/A")
        median_growth = filtered_ltm["ltm_vs_annual_growth_pct"].median()
        c4.metric("Median LTM P/E", f"{filtered_ltm['ltm_pe_ratio'].median():.1f}x" if filtered_ltm["ltm_pe_ratio"].notna().any() else "N/A")
        c5.metric("Median LTM P/Revenue", f"{filtered_ltm['ltm_price_to_revenue'].median():.1f}x" if filtered_ltm["ltm_price_to_revenue"].notna().any() else "N/A")

        st.divider()

        chart_data = filtered_ltm[filtered_ltm["ltm_revenue"].notna()].copy()
        chart_melted = pd.melt(
            chart_data[["ticker", "annual_revenue", "ltm_revenue"]],
            id_vars="ticker", value_vars=["annual_revenue", "ltm_revenue"],
            var_name="Period", value_name="Revenue"
        )
        chart_melted["Period"] = chart_melted["Period"].map({"annual_revenue": "Annual", "ltm_revenue": "LTM"})

        col1, col2 = st.columns(2)
        with col1:
            fig_ltm = px.bar(
                chart_melted.sort_values("Revenue", ascending=False),
                x="ticker", y="Revenue", color="Period", barmode="group",
                title="Annual vs LTM Revenue",
                labels={"Revenue": "Revenue ($)", "ticker": ""},
                color_discrete_map={"Annual": "#aec7e8", "LTM": "#1f77b4"}
            )
            fig_ltm.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_ltm, use_container_width=True)

        with col2:
            fig_growth = px.bar(
                filtered_ltm[filtered_ltm["ltm_vs_annual_growth_pct"].notna()].sort_values("ltm_vs_annual_growth_pct", ascending=False),
                x="ticker", y="ltm_vs_annual_growth_pct", color="sector",
                title="LTM vs Annual Revenue Δ (%)",
                labels={"ltm_vs_annual_growth_pct": "Growth (%)", "ticker": ""},
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_growth.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_growth.update_layout(xaxis_tickangle=-45, showlegend=False)
            st.plotly_chart(fig_growth, use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            m_data = filtered_ltm[filtered_ltm["ltm_net_margin_pct"].notna()].sort_values("ltm_revenue", ascending=False)
            fig_margin_comp = go.Figure()
            fig_margin_comp.add_trace(go.Bar(x=m_data["ticker"], y=m_data["annual_net_margin_pct"], name="Annual", marker_color="#aec7e8"))
            fig_margin_comp.add_trace(go.Bar(x=m_data["ticker"], y=m_data["ltm_net_margin_pct"], name="LTM", marker_color="#1f77b4"))
            fig_margin_comp.update_layout(barmode="group", title="Annual vs LTM Net Margin (%)", xaxis_tickangle=-45)
            st.plotly_chart(fig_margin_comp, use_container_width=True)

        with col4:
            fig_scatter = px.scatter(
                filtered_ltm[filtered_ltm["ltm_net_margin_pct"].notna()],
                x="ltm_revenue", y="ltm_net_margin_pct",
                color="sector", text="ticker",
                title="LTM Revenue vs LTM Net Margin",
                labels={"ltm_revenue": "LTM Revenue ($)", "ltm_net_margin_pct": "LTM Net Margin (%)"},
                hover_data=["company_name", "ltm_as_of"],
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_scatter.update_traces(textposition="top center")
            fig_scatter.add_hline(y=0, line_dash="dash", line_color="lightgray")
            st.plotly_chart(fig_scatter, use_container_width=True)

        st.subheader("LTM Comps Table")
        table = filtered_ltm[[
            "ticker", "company_name", "sector",
            "annual_fy", "ltm_period", "ltm_as_of",
            "annual_revenue", "ltm_revenue",
            "annual_net_margin_pct", "ltm_net_margin_pct",
            "ltm_vs_annual_growth_pct",
            "market_cap", "ltm_price_to_revenue", "ltm_pe_ratio"
        ]].copy()
        table["annual_revenue"]        = table["annual_revenue"].apply(format_money)
        table["ltm_revenue"]           = table["ltm_revenue"].apply(format_money)
        table["market_cap"]            = table["market_cap"].apply(format_money)
        table["annual_net_margin_pct"] = table["annual_net_margin_pct"].apply(lambda x: f"{x:.1f}%" if not pd.isna(x) else "N/A")
        table["ltm_net_margin_pct"]    = table["ltm_net_margin_pct"].apply(lambda x: f"{x:.1f}%" if not pd.isna(x) else "N/A")
        table["ltm_vs_annual_growth_pct"] = table["ltm_vs_annual_growth_pct"].apply(format_pct)
        table["ltm_price_to_revenue"]  = table["ltm_price_to_revenue"].apply(lambda x: f"{x:.1f}x" if not pd.isna(x) else "N/A")
        table["ltm_pe_ratio"]          = table["ltm_pe_ratio"].apply(lambda x: f"{x:.1f}x" if not pd.isna(x) else "N/A")
        table["company_name"] = table["company_name"] + " (" + table["ticker"] + ")"
        table = table.drop(columns=["ticker"])
        table.columns = ["Company", "Sector", "Annual FY", "LTM Period", "As Of",
                         "Annual Revenue", "LTM Revenue", "Annual Net Margin", "LTM Net Margin",
                         "LTM vs Annual", "Mkt Cap", "LTM P/Revenue", "LTM P/E"]
        st.dataframe(table, use_container_width=True, hide_index=True)

    except Exception as e:
        st.warning("LTM data not loaded. Run `python ingest_sec.py` then `dbt run --select stg_sec_quarterly mart_ltm_comps`.")
        st.caption(str(e))

con.close()
