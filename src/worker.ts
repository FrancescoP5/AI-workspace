import { FetchEvent, Request, Response } from '@cloudflare/workers-types';

addEventListener("fetch", (event: Event) => {
  // The double cast is required because Cloudflare Workers' type definitions
  // may type the event as a generic Event, but in this environment it is always a FetchEvent.
  // This cast is safe in the context of Cloudflare Workers.
  const fetchEvent = event as unknown as FetchEvent;
  fetchEvent.respondWith(handleRequest(fetchEvent.request));
});

async function handleRequest(req: Request): Promise<Response> {
  if (req.method === "GET") {
    return new Response(JSON.stringify({ message: "AI-workspace simulator worker", usage: "POST JSON { prices: number[], short: number, long: number }" }), { headers: { "Content-Type": "application/json" } });
  }

  try {
    interface RequestBody {
      prices: number[];
      short?: number;
      long?: number;
    }
    let body: RequestBody;
    try {
      body = await req.json();
    } catch (jsonErr) {
      return new Response(JSON.stringify({ error: "Invalid JSON format" }), { status: 400, headers: { "Content-Type": "application/json" } });
    }
    if (!body || !Array.isArray(body.prices)) {
      return new Response(JSON.stringify({ error: "Missing or invalid 'prices' field (must be an array of numbers)" }), { status: 400, headers: { "Content-Type": "application/json" } });
    }
    const DEFAULT_SHORT_PERIOD = 5;
    const DEFAULT_LONG_PERIOD = 20;
    const prices: number[] = body.prices.map(Number);
    if (prices.some((p) => Number.isNaN(p))) {
      return new Response(JSON.stringify({ error: "Prices array contains invalid numbers" }), { status: 400, headers: { "Content-Type": "application/json" } });
    }
    const short = body.short !== undefined ? Number(body.short) : DEFAULT_SHORT_PERIOD;
    const long = body.long !== undefined ? Number(body.long) : DEFAULT_LONG_PERIOD;
    if (
      !Number.isInteger(short) || !Number.isInteger(long) ||
      short <= 0 || long <= 0 ||
      short >= long
    ) {
      return new Response(
        JSON.stringify({ error: "'short' and 'long' must be positive integers and 'short' < 'long'" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }
    if (prices.length < long) {
      return new Response(JSON.stringify({ error: `Not enough price data: received ${prices.length}, but 'long' period is ${long}` }), { status: 400, headers: { "Content-Type": "application/json" } });
    }
    const result = smaCrossover(prices, short, long);
    return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
  } catch (err) {
    // Log the error server-side for debugging/monitoring
    console.error(err);
    return new Response(JSON.stringify({ error: "Unexpected error" }), { status: 500, headers: { "Content-Type": "application/json" } });
  }
}

function sma(arr: number[], period: number, idx: number): number | null {
  if (idx < period - 1) return null;
  let sum = 0;
  for (let i = idx - period + 1; i <= idx; i++) sum += arr[i];
  return sum / period;
}

function smaCrossover(prices: number[], short: number, long: number) {
  const signals: { idx: number; price: number; signal: "buy" | "sell" }[] = [];
  for (let i = 0; i < prices.length; i++) {
    const shortSma = sma(prices, short, i);
    const longSma = sma(prices, long, i);
    if (shortSma === null || longSma === null) continue;
    const prevShortSma = sma(prices, short, i - 1);
    const prevLongSma = sma(prices, long, i - 1);
    if (prevShortSma !== null && prevLongSma !== null) {
      if (prevShortSma <= prevLongSma && shortSma > longSma) signals.push({ idx: i, price: prices[i], signal: "buy" });
      if (prevShortSma >= prevLongSma && shortSma < longSma) signals.push({ idx: i, price: prices[i], signal: "sell" });
    }
  }
  return { signals };
}
