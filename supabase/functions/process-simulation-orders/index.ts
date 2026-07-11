import { createClient } from "npm:@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

async function latestPrice(symbol: string): Promise<number | null> {
  const yahooSymbol = symbol.replace(".IS", ".IS");
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yahooSymbol)}?interval=1m&range=1d`;
  const response = await fetch(url, { headers: { "User-Agent": "NOVA-AI/1.0" } });
  if (!response.ok) return null;
  const payload = await response.json();
  const result = payload?.chart?.result?.[0];
  const price = Number(result?.meta?.regularMarketPrice ?? result?.indicators?.quote?.[0]?.close?.at(-1));
  return Number.isFinite(price) && price > 0 ? price : null;
}

Deno.serve(async () => {
  const { data: positions, error } = await supabase
    .from("simulation_positions")
    .select("*");
  if (error) return Response.json({ error: error.message }, { status: 500 });

  const priceCache = new Map<string, number>();
  const executed: Array<Record<string, unknown>> = [];
  for (const position of positions ?? []) {
    let price = priceCache.get(position.symbol);
    if (!price) {
      price = (await latestPrice(position.symbol)) ?? undefined;
      if (!price) continue;
      priceCache.set(position.symbol, price);
    }
    await supabase.from("simulation_positions").update({ last_price: price, updated_at: new Date().toISOString() }).eq("id", position.id);
    const reason = price <= Number(position.stop_price)
      ? "Stop loss emri"
      : price >= Number(position.target_price)
      ? "Hedef satış emri"
      : null;
    if (!reason) continue;

    const proceeds = Number((price * position.quantity).toFixed(2));
    const pnl = Number(((price - Number(position.avg_price)) * position.quantity).toFixed(2));
    const { data: account } = await supabase.from("simulation_accounts").select("cash").eq("username", position.username).single();
    const { error: cashError } = await supabase.from("simulation_accounts")
      .update({ cash: Number(account.cash) + proceeds, updated_at: new Date().toISOString() })
      .eq("username", position.username);
    if (cashError) continue;
    await supabase.from("simulation_trades").insert({
      username: position.username, week_key: position.week_key, side: "SAT",
      symbol: position.symbol, quantity: position.quantity, price,
      total: proceeds, realized_pnl: pnl, reason,
    });
    await supabase.from("simulation_positions").delete().eq("id", position.id);
    executed.push({ username: position.username, symbol: position.symbol, price, reason });
  }
  return Response.json({ checked: positions?.length ?? 0, executed });
});
