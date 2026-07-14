alter table public.user_portfolio_data
  add column if not exists inception_active jsonb not null default '[]'::jsonb,
  add column if not exists inception_history jsonb not null default '[]'::jsonb,
  add column if not exists inception_metadata jsonb not null default '[]'::jsonb;

alter table public.user_portfolio_data
  add constraint inception_active_is_array check (jsonb_typeof(inception_active) = 'array'),
  add constraint inception_history_is_array check (jsonb_typeof(inception_history) = 'array'),
  add constraint inception_metadata_is_array check (jsonb_typeof(inception_metadata) = 'array');

update public.user_portfolio_data set schema_version = greatest(schema_version, 2);
