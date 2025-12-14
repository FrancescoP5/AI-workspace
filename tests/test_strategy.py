import numpy as np
import pandas as pd

from simulator.strategy import sma_crossover_signals


def test_sma_crossover_basic():
    # Test basic SMA crossover signal generation
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    prices = pd.Series(100.0 + np.arange(100, dtype=float), index=dates)
    df = pd.DataFrame({'Close': prices})
    
    result = sma_crossover_signals(df, short=5, long=20)
    
    # Should have required columns
    assert 'sma_short' in result.columns
    assert 'sma_long' in result.columns
    assert 'signal' in result.columns
    
    # After warm-up period, signals should be generated
    # With steadily increasing prices, short SMA should be > long SMA
    assert result['signal'].iloc[-1] == 1


def test_sma_crossover_insufficient_data():
    # Test with insufficient data for long window
    dates = pd.date_range('2020-01-01', periods=30, freq='D')
    prices = pd.Series(100.0 + np.arange(30, dtype=float), index=dates)
    df = pd.DataFrame({'Close': prices})
    
    result = sma_crossover_signals(df, short=20, long=50)
    
    # Should handle gracefully - most signals should be 0 due to NaN SMAs
    assert 'signal' in result.columns
    # With long=50 but only 30 data points, sma_long will be all NaN
    assert result['sma_long'].isna().all()
    # Signals should be 0 when SMAs are NaN
    assert (result['signal'] == 0).all()


def test_sma_crossover_nan_prices():
    # Test with NaN prices
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    prices = pd.Series(100.0 + np.arange(100, dtype=float), index=dates)
    prices.iloc[10:20] = np.nan  # Insert some NaN values
    df = pd.DataFrame({'Close': prices})
    
    result = sma_crossover_signals(df, short=5, long=20)
    
    # Should handle NaN gracefully
    assert 'signal' in result.columns
    # Signals during NaN periods should be 0
    assert (result['signal'].iloc[10:25] == 0).all()


def test_sma_crossover_after_flatten():
    # Test with flattened columns (after MultiIndex normalization)
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    prices = 100.0 + np.arange(100, dtype=float)
    
    df = pd.DataFrame({
        ('Close', 'AAPL'): prices
    }, index=dates)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    
    # Flatten to single-level columns
    df_flat = df.copy()
    df_flat.columns = ['Close']
    
    result = sma_crossover_signals(df_flat, short=5, long=20)
    
    # Should work with flattened columns
    assert 'signal' in result.columns
    assert result['signal'].iloc[-1] in [0, 1]


def test_sma_crossover_warmup_period():
    # Test that signals are not generated during warm-up period
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    prices = pd.Series(100.0 + np.arange(100, dtype=float), index=dates)
    df = pd.DataFrame({'Close': prices})
    
    result = sma_crossover_signals(df, short=20, long=50)
    
    # First 49 rows should have signal=0 due to long SMA warm-up (before we have 50 data points)
    assert (result['signal'].iloc[:49] == 0).all()
    # At row 50 and after, with increasing prices, should have buy signal
    assert result['signal'].iloc[-1] == 1


def test_sma_crossover_signal_change():
    # Test signal changes when short SMA crosses long SMA
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    # Create prices that go up then down to trigger crossover
    prices_up = np.arange(50, dtype=float) * 2
    prices_down = 100.0 - np.arange(50, dtype=float)
    prices = pd.Series(np.concatenate([prices_up, prices_down]), index=dates)
    df = pd.DataFrame({'Close': prices})
    
    result = sma_crossover_signals(df, short=5, long=20)
    
    # Should have both 0 and 1 signals due to crossover
    assert 0 in result['signal'].values
    assert 1 in result['signal'].values
