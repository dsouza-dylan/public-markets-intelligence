with base as (
    select * from {{ ref('stg_sec_financials') }}
),

with_growth as (
    select
        *,
        lag(revenue) over (partition by ticker order by fiscal_year) as prev_revenue,
        case
            when lag(revenue) over (partition by ticker order by fiscal_year) > 0
            then round(
                100.0 * (revenue - lag(revenue) over (partition by ticker order by fiscal_year))
                / lag(revenue) over (partition by ticker order by fiscal_year),
                2
            )
            else null
        end as revenue_growth_pct
    from base
),

with_percentiles as (
    select
        *,
        round(percent_rank() over (
            partition by sector, fiscal_year order by revenue
        ) * 100, 1) as revenue_percentile,
        round(percent_rank() over (
            partition by sector, fiscal_year order by net_margin_pct
        ) * 100, 1) as margin_percentile,
        round(percent_rank() over (
            partition by sector, fiscal_year order by revenue_growth_pct
        ) * 100, 1) as growth_percentile
    from with_growth
),

with_market_cap as (
    select
        p.*,
        m.market_cap,
        m.current_price,
        m.as_of                                             as market_cap_as_of,

        -- Valuation multiples (market cap based, not true EV)
        case
            when p.revenue > 0
            then round(m.market_cap / p.revenue, 2)
        end                                                 as price_to_revenue,

        case
            when p.net_income > 0
            then round(m.market_cap / p.net_income, 2)
        end                                                 as pe_ratio

    from with_percentiles p
    left join {{ ref('stg_market_cap') }} m on p.ticker = m.ticker
)

select * from with_market_cap
