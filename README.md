# Simple trading simulator

This minimal project fetches price data with `yfinance`, generates SMA crossover signals, and runs a lightweight backtest.

Quick start (PowerShell on Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m simulator.main
```

Files:
- `simulator/data/yfinance_loader.py`: fetches data from yfinance
- `simulator/strategy.py`: SMA crossover signals
- `simulator/backtester.py`: simple backtester
- `simulator/main.py`: example runner
- `simulator/visualization.py`: interactive SMA visualization (plotly HTML)

Interactive visualization
-------------------------

Generate an interactive SMA crossover chart with zoom/pan, range selector, ticker choice, and buy/sell markers:

```powershell
python -m simulator.visualization --ticker AAPL --period 1y --interval 1d --short 20 --long 50 --start 2024-01-01 --end 2024-12-01
```

Output: `simulator/data/output/<ticker>_interactive.html` (override with `--output`).

Cloudflare Workers
------------------

You can deploy a small HTTP endpoint of the SMA-crossover logic to Cloudflare Workers. I added a minimal Worker in `src/worker.ts` plus `wrangler.toml` and `package.json` scripts.

Quick deploy (PowerShell):
```powershell
npm install
npm run build
wrangler login
wrangler publish
```

Usage: POST JSON to the worker with `prices` (array), `short`, and `long`.

Example request body:
```json
{ "prices": [100,101,102,...], "short": 5, "long": 20 }
```