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
    const { data: result, error: saleError } = await supabase.rpc("execute_simulation_sale", {
      p_position_id: position.id,
      p_market_price: price,
    });
    if (saleError) {
      console.error("simulation sale failed", { positionId: position.id, message: saleError.message });
      continue;
    }
    if (result?.executed) executed.push(result);
  }
  return Response.json({ checked: positions?.length ?? 0, executed });
});
