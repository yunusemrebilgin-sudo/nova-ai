import { createClient } from "npm:@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

type MarketQuote = { price: number; timestamp: number; ageSeconds: number };

function istanbulSessionState(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Istanbul", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(now);
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  const weekday = value("weekday");
  const minutes = Number(value("hour")) * 60 + Number(value("minute"));
  const weekdayOpen = !["Sat", "Sun"].includes(weekday);
  return { open: weekdayOpen && minutes >= 600 && minutes < 1080, weekday, minutes };
}

async function latestPrice(symbol: string): Promise<MarketQuote | null> {
  const yahooSymbol = symbol.replace(".IS", ".IS");
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yahooSymbol)}?interval=1m&range=1d`;
  const response = await fetch(url, { headers: { "User-Agent": "NOVA-AI/1.0" } });
  if (!response.ok) return null;
  const payload = await response.json();
  const result = payload?.chart?.result?.[0];
  const timestamps: number[] = result?.timestamp ?? [];
  const timestamp = Number(result?.meta?.regularMarketTime ?? timestamps.at(-1));
  const price = Number(result?.meta?.regularMarketPrice ?? result?.indicators?.quote?.[0]?.close?.at(-1));
  const ageSeconds = Math.max(0, Math.floor(Date.now() / 1000) - timestamp);
  return Number.isFinite(price) && price > 0 && Number.isFinite(timestamp)
    ? { price, timestamp, ageSeconds }
    : null;
}

Deno.serve(async () => {
  const { data: rollover, error: rolloverError } = await supabase.rpc("rollover_simulation_weeks");
  if (rolloverError) return Response.json({ error: rolloverError.message, stage: "weekly_rollover" }, { status: 500 });

  const session = istanbulSessionState();
  if (!session.open) return Response.json({ checked: 0, executed: [], skipped: "bist_session_closed", session, rollover });

  const { data: positions, error } = await supabase
    .from("simulation_positions")
    .select("*");
  if (error) return Response.json({ error: error.message }, { status: 500 });

  const priceCache = new Map<string, MarketQuote>();
  const executed: Array<Record<string, unknown>> = [];
  const staleSymbols: Array<Record<string, unknown>> = [];
  for (const position of positions ?? []) {
    let quote = priceCache.get(position.symbol);
    if (!quote) {
      quote = (await latestPrice(position.symbol)) ?? undefined;
      if (!quote) continue;
      priceCache.set(position.symbol, quote);
    }
    if (quote.ageSeconds > 1200) {
      staleSymbols.push({ symbol: position.symbol, ageSeconds: quote.ageSeconds });
      continue;
    }
    const { data: result, error: saleError } = await supabase.rpc("execute_simulation_sale", {
      p_position_id: position.id,
      p_market_price: quote.price,
    });
    if (saleError) {
      console.error("simulation sale failed", { positionId: position.id, message: saleError.message });
      continue;
    }
    if (result?.executed) executed.push(result);
  }
  return Response.json({ checked: positions?.length ?? 0, executed, staleSymbols, session, rollover });
});
