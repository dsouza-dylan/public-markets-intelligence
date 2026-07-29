-- LTM = Most Recent Annual + Current YTD - Prior Year Same Period YTD
-- Standard formula used in investment banking comps

with annual as (
    select * from {{ ref('stg_sec_financials') }}
    qualify fiscal_year = max(fiscal_year) over (partition by ticker)
),

quarterly as (
    select * from {{ ref('stg_sec_quarterly') }}
),

most_recent_q as (
    select * from quarterly
    qualify period_end = max(period_end) over (partition by ticker)
),

prior_year_q as (
    select q.*
    from quarterly q
    inner join most_recent_q mrq
        on  q.ticker      = mrq.ticker
        and q.period      = mrq.period
        and q.fiscal_year = mrq.fiscal_year - 1
),

ltm as (
    select
        a.ticker,
        a.company_name,
        a.sector,
        a.fiscal_year                                   as annual_fy,
        mrq.period                                      as ltm_period,
        mrq.fiscal_year                                 as ltm_fy,
        mrq.period_end                                  as ltm_as_of,

        a.revenue
            + coalesce(mrq.ytd_revenue,    0)
            - coalesce(pyq.ytd_revenue,    0)           as ltm_revenue,

        a.net_income
            + coalesce(mrq.ytd_net_income, 0)
            - coalesce(pyq.ytd_net_income, 0)           as ltm_net_income,

        a.operating_income
            + coalesce(mrq.ytd_op_income,  0)
            - coalesce(pyq.ytd_op_income,  0)           as ltm_op_income,

        a.revenue                                       as annual_revenue,
        a.net_margin_pct                                as annual_net_margin_pct,
        a.op_margin_pct                                 as annual_op_margin_pct

    from annual a
    left join most_recent_q mrq on a.ticker = mrq.ticker
    left join prior_year_q  pyq on a.ticker = pyq.ticker
),

with_margins as (
    select
        *,
        case
            when ltm_revenue > 0
            then round(100.0 * ltm_net_income / ltm_revenue, 2)
        end as ltm_net_margin_pct,
        case
            when ltm_revenue > 0
            then round(100.0 * ltm_op_income / ltm_revenue, 2)
        end as ltm_op_margin_pct,
        case
            when annual_revenue > 0
            then round(100.0 * (ltm_revenue - annual_revenue) / annual_revenue, 2)
        end as ltm_vs_annual_growth_pct
    from ltm
)

select
    m.*,
    mc.market_cap,
    mc.current_price,
    mc.as_of                                            as market_cap_as_of,

    -- LTM valuation multiples
    case
        when m.ltm_revenue > 0
        then round(mc.market_cap / m.ltm_revenue, 2)
    end                                                 as ltm_price_to_revenue,

    case
        when m.ltm_net_income > 0
        then round(mc.market_cap / m.ltm_net_income, 2)
    end                                                 as ltm_pe_ratio

from with_margins m
left join {{ ref('stg_market_cap') }} mc on m.ticker = mc.ticker
