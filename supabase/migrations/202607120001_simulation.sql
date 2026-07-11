create extension if not exists pg_cron;
create extension if not exists pg_net;

create table if not exists public.simulation_accounts (
  username text primary key,
  week_key text not null,
  starting_cash numeric(14,2) not null default 10000,
  cash numeric(14,2) not null default 10000,
  updated_at timestamptz not null default now()
);

create table if not exists public.simulation_positions (
  id bigint generated always as identity primary key,
  username text not null references public.simulation_accounts(username) on delete cascade,
  week_key text not null,
  symbol text not null,
  quantity integer not null check (quantity > 0),
  avg_price numeric(14,4) not null check (avg_price > 0),
  stop_price numeric(14,4) not null check (stop_price > 0),
  target_price numeric(14,4) not null check (target_price > 0),
  last_price numeric(14,4),
  opened_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (username, week_key, symbol)
);

create table if not exists public.simulation_trades (
  id bigint generated always as identity primary key,
  username text not null,
  week_key text not null,
  side text not null check (side in ('AL', 'SAT')),
  symbol text not null,
  quantity integer not null,
  price numeric(14,4) not null,
  total numeric(14,2) not null,
  realized_pnl numeric(14,2),
  reason text,
  executed_at timestamptz not null default now()
);

create table if not exists public.simulation_weekly_summaries (
  id bigint generated always as identity primary key,
  username text not null,
  week_key text not null,
  ending_value numeric(14,2) not null,
  pnl numeric(14,2) not null,
  pnl_pct numeric(10,2) not null,
  trade_count integer not null default 0,
  closed_at timestamptz not null default now(),
  unique (username, week_key)
);

create index if not exists simulation_positions_active_idx
  on public.simulation_positions (symbol, stop_price, target_price);
create index if not exists simulation_trades_user_week_idx
  on public.simulation_trades (username, week_key, executed_at desc);

alter table public.simulation_accounts enable row level security;
alter table public.simulation_positions enable row level security;
alter table public.simulation_trades enable row level security;
alter table public.simulation_weekly_summaries enable row level security;

-- Streamlit ve zamanlanmış Edge Function yalnızca service_role anahtarıyla erişir.
-- Böylece tablolar anonim internet isteklerine kapalı kalır.
