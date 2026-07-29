select
    ticker,
    market_cap,
    current_price,
    shares_outstanding,
    as_of::date as as_of
from {{ source('raw', 'market_cap') }}
where market_cap is not null
