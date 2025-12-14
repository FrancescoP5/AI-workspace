"""Example runner for the simple trading simulator.

Usage: python simulator/main.py
"""
from pathlib import Path

import matplotlib.pyplot as plt

from simulator.data.yfinance_loader import fetch_data
from simulator.strategy import sma_crossover_signals
from simulator.backtester import Backtester


def run_example(ticker='AAPL'):
    data_dir = Path(__file__).parent / 'data' / 'cache'
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_file = data_dir / f"{ticker}.csv"

    print(f"Fetching data for {ticker}...")
    df = fetch_data(ticker, period='2y', interval='1d', cache_path=str(cache_file))

    print("Generating signals (SMA crossover)...")
    signals = sma_crossover_signals(df, short=20, long=50)

    print("Running backtest...")
    bt = Backtester(initial_capital=10000)
    res = bt.run(signals)

    print("Metrics:")
    for k, v in res['metrics'].items():
        print(f"  {k}: {v}")

    # Plot equity
    fig, ax = plt.subplots(figsize=(10, 5))
    res['equity'].plot(ax=ax)
    ax.set_title(f"Equity curve: {ticker}")
    ax.set_ylabel('Portfolio value')
    out_dir = Path(__file__).parent / 'data' / 'output'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"equity_{ticker}.png"
    fig.savefig(out)
    print(f"Saved equity plot to {out}")


if __name__ == '__main__':
    run_example()
