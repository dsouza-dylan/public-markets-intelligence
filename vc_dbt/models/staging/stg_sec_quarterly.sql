select
    ticker,
    company_name,
    sector,
    fiscal_year,
    period,
    period_start::date as period_start,
    period_end::date   as period_end,
    ytd_revenue,
    ytd_net_income,
    ytd_op_income,
    datediff('day', period_start::date, period_end::date) as period_days
from {{ source('raw', 'sec_quarterly') }}
where ytd_revenue is not null
  and period_start is not null
  and period_end   is not null
