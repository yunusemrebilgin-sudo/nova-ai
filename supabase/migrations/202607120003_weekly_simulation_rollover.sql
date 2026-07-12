create or replace function public.rollover_simulation_weeks()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_current_week text;
  v_account public.simulation_accounts%rowtype;
  v_ending_value numeric(14,2);
  v_trade_count integer;
  v_closed integer := 0;
begin
  v_current_week := to_char(timezone('Europe/Istanbul', now()), 'IYYY-"W"IW');

  for v_account in
    select * from public.simulation_accounts
    where week_key <> v_current_week
    for update skip locked
  loop
    select round(
      v_account.cash + coalesce(sum(quantity * coalesce(last_price, avg_price)), 0), 2
    ) into v_ending_value
    from public.simulation_positions
    where username = v_account.username and week_key = v_account.week_key;

    select count(*) into v_trade_count
    from public.simulation_trades
    where username = v_account.username and week_key = v_account.week_key;

    insert into public.simulation_weekly_summaries (
      username, week_key, ending_value, pnl, pnl_pct, trade_count, closed_at
    ) values (
      v_account.username,
      v_account.week_key,
      v_ending_value,
      round(v_ending_value - v_account.starting_cash, 2),
      round(((v_ending_value / nullif(v_account.starting_cash, 0)) - 1) * 100, 2),
      v_trade_count,
      now()
    ) on conflict (username, week_key) do update set
      ending_value = excluded.ending_value,
      pnl = excluded.pnl,
      pnl_pct = excluded.pnl_pct,
      trade_count = excluded.trade_count,
      closed_at = excluded.closed_at;

    delete from public.simulation_positions
      where username = v_account.username and week_key = v_account.week_key;

    update public.simulation_accounts set
      week_key = v_current_week,
      starting_cash = 10000,
      cash = 10000,
      updated_at = now()
    where username = v_account.username;

    v_closed := v_closed + 1;
  end loop;

  return jsonb_build_object('week', v_current_week, 'accounts_rolled_over', v_closed);
end;
$$;

revoke all on function public.rollover_simulation_weeks() from public, anon, authenticated;
grant execute on function public.rollover_simulation_weeks() to service_role;
