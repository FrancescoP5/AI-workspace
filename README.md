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
