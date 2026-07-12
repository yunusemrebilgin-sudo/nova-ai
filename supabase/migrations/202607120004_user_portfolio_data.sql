create table if not exists public.user_portfolio_data (
  username text primary key,
  open_positions jsonb not null default '[]'::jsonb,
  closed_trades jsonb not null default '[]'::jsonb,
  ai_watchlist jsonb not null default '[]'::jsonb,
  schema_version integer not null default 1,
  updated_at timestamptz not null default now(),
  check (jsonb_typeof(open_positions) = 'array'),
  check (jsonb_typeof(closed_trades) = 'array'),
  check (jsonb_typeof(ai_watchlist) = 'array')
);

alter table public.user_portfolio_data enable row level security;

-- Streamlit backend accesses this table only with the existing service-role key.
-- Anonymous clients receive no policy and therefore cannot read or write user data.
