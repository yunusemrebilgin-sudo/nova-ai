create or replace function public.execute_simulation_sale(
  p_position_id bigint,
  p_market_price numeric
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_position public.simulation_positions%rowtype;
  v_reason text;
  v_proceeds numeric(14,2);
  v_pnl numeric(14,2);
begin
  select * into v_position
  from public.simulation_positions
  where id = p_position_id
  for update skip locked;

  if not found then
    return jsonb_build_object('executed', false, 'reason', 'position_missing_or_locked');
  end if;

  if p_market_price <= v_position.stop_price then
    v_reason := 'Stop loss emri';
  elsif p_market_price >= v_position.target_price then
    v_reason := 'Hedef satış emri';
  else
    update public.simulation_positions
      set last_price = p_market_price, updated_at = now()
      where id = v_position.id;
    return jsonb_build_object('executed', false, 'reason', 'price_not_triggered');
  end if;

  v_proceeds := round(p_market_price * v_position.quantity, 2);
  v_pnl := round((p_market_price - v_position.avg_price) * v_position.quantity, 2);

  update public.simulation_accounts
    set cash = cash + v_proceeds, updated_at = now()
    where username = v_position.username;

  if not found then
    raise exception 'simulation account not found for %', v_position.username;
  end if;

  insert into public.simulation_trades (
    username, week_key, side, symbol, quantity, price, total,
    realized_pnl, reason, executed_at
  ) values (
    v_position.username, v_position.week_key, 'SAT', v_position.symbol,
    v_position.quantity, p_market_price, v_proceeds, v_pnl, v_reason, now()
  );

  delete from public.simulation_positions where id = v_position.id;

  return jsonb_build_object(
    'executed', true,
    'username', v_position.username,
    'symbol', v_position.symbol,
    'price', p_market_price,
    'reason', v_reason,
    'pnl', v_pnl
  );
end;
$$;

revoke all on function public.execute_simulation_sale(bigint, numeric) from public, anon, authenticated;
grant execute on function public.execute_simulation_sale(bigint, numeric) to service_role;
