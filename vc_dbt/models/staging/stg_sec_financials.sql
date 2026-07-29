select
    ticker,
    company_name,
    sector,
    fiscal_year,
    revenue,
    net_income,
    operating_income,
    total_assets,
    case
        when revenue > 0 then round(100.0 * net_income / revenue, 2)
        else null
    end as net_margin_pct,
    case
        when revenue > 0 then round(100.0 * operating_income / revenue, 2)
        else null
    end as op_margin_pct
from {{ source('raw', 'sec_financials') }}
where revenue is not null
  and fiscal_year is not null
