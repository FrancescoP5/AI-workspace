"use strict";
(() => {
  // src/worker.ts
  addEventListener("fetch", (event) => {
    event.respondWith(handleRequest(event.request));
  });
  async function handleRequest(req) {
    if (req.method === "GET") {
      return new Response(JSON.stringify({ message: "AI-workspace simulator worker", usage: "POST JSON { prices: number[], short: number, long: number }" }), { headers: { "Content-Type": "application/json" } });
    }
    try {
      const body = await req.json();
      const prices = Array.isArray(body.prices) ? body.prices.map(Number) : [];
      const short = Number(body.short) || 5;
      const long = Number(body.long) || 20;
      if (prices.length < long)
        return new Response(JSON.stringify({ error: "not enough data" }), { status: 400, headers: { "Content-Type": "application/json" } });
      const result = smaCrossover(prices, short, long);
      return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
    } catch (err) {
      return new Response(JSON.stringify({ error: "invalid request" }), { status: 400, headers: { "Content-Type": "application/json" } });
    }
  }
  function sma(arr, period, idx) {
    if (idx < period - 1)
      return null;
    let sum = 0;
    for (let i = idx - period + 1; i <= idx; i++)
      sum += arr[i];
    return sum / period;
  }
  function smaCrossover(prices, short, long) {
    const signals = [];
    for (let i = 0; i < prices.length; i++) {
      const s = sma(prices, short, i);
      const l = sma(prices, long, i);
      if (s === null || l === null)
        continue;
      const prevS = sma(prices, short, i - 1);
      const prevL = sma(prices, long, i - 1);
      if (prevS !== null && prevL !== null) {
        if (prevS <= prevL && s > l)
          signals.push({ idx: i, price: prices[i], signal: "buy" });
        if (prevS >= prevL && s < l)
          signals.push({ idx: i, price: prices[i], signal: "sell" });
      }
    }
    return { signals };
  }
})();
