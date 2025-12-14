import numpy as np
import pandas as pd

from simulator.backtester import Backtester


def test_backtester_buy_and_hold():
    # synthetic price: linear increase (so buy & hold should increase capital)
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    prices = pd.Series(100.0 + np.arange(100, dtype=float), index=dates)
    df = pd.DataFrame({'Close': prices})

    # always-on signal (buy at start and hold)
    df['signal'] = 1

    bt = Backtester(initial_capital=1000)
    res = bt.run(df)
    final = res['metrics']['final_capital']

    assert final > 1000
