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


def test_backtester_empty_dataframe():
    # Test with empty DataFrame - should handle gracefully
    df = pd.DataFrame({'Close': [], 'signal': []})
    
    bt = Backtester(initial_capital=1000)
    res = bt.run(df)
    
    # Should return initial capital with no gains/losses
    assert res['metrics']['final_capital'] == 1000
    assert res['metrics']['total_return'] == 0.0
    assert res['metrics']['annualized_return'] == 0.0
    assert res['metrics']['max_drawdown'] == 0.0


def test_backtester_sell_signal():
    # Test with sell signal (signal=0) - should not participate in price increase
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    prices = pd.Series(100.0 + np.arange(100, dtype=float), index=dates)
    df = pd.DataFrame({'Close': prices})
    
    # no signal (sell/stay out)
    df['signal'] = 0
    
    bt = Backtester(initial_capital=1000)
    res = bt.run(df)
    final = res['metrics']['final_capital']
    
    # Capital should remain unchanged (no position)
    assert abs(final - 1000) < 0.01  # Allow for small floating point errors


def test_backtester_price_decrease():
    # Test with decreasing prices and buy signal - capital should decrease
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    prices = pd.Series(200.0 - np.arange(100, dtype=float), index=dates)
    df = pd.DataFrame({'Close': prices})
    
    # always-on signal (buy and hold through decline)
    df['signal'] = 1
    
    bt = Backtester(initial_capital=1000)
    res = bt.run(df)
    final = res['metrics']['final_capital']
    
    # Capital should decrease
    assert final < 1000


def test_backtester_warmup_period():
    # Test with signals during warm-up period where some values might be NaN
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    prices = pd.Series(100.0 + np.arange(100, dtype=float), index=dates)
    df = pd.DataFrame({'Close': prices})
    
    # Signal pattern with some NaN values at start (simulating SMA warm-up)
    df['signal'] = 0
    df.loc[df.index[50:], 'signal'] = 1  # Only trade after warm-up
    
    bt = Backtester(initial_capital=1000)
    res = bt.run(df)
    
    # Should handle gracefully and produce valid metrics
    assert res['metrics']['final_capital'] > 0
    assert not np.isnan(res['metrics']['total_return'])
