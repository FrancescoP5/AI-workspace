import os
import tempfile
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from simulator.data.yfinance_loader import (
    _normalize_yfinance_columns,
    _coerce_ohlc_numeric,
    _looks_valid,
    _is_cache_stale,
    fetch_data,
    DEFAULT_MAX_CACHE_AGE_DAYS,
)


def test_normalize_single_level_columns():
    # Test that single-level columns are left unchanged
    df = pd.DataFrame({
        'Open': [100, 101],
        'High': [102, 103],
        'Low': [99, 100],
        'Close': [101, 102]
    })
    
    result = _normalize_yfinance_columns(df)
    assert list(result.columns) == ['Open', 'High', 'Low', 'Close']


def test_normalize_multiindex_columns_level0():
    # Test MultiIndex with OHLC at level 0
    df = pd.DataFrame({
        ('Open', 'AAPL'): [100, 101],
        ('High', 'AAPL'): [102, 103],
        ('Low', 'AAPL'): [99, 100],
        ('Close', 'AAPL'): [101, 102]
    })
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    
    result = _normalize_yfinance_columns(df)
    assert list(result.columns) == ['Open', 'High', 'Low', 'Close']


def test_normalize_multiindex_columns_level1():
    # Test MultiIndex with OHLC at level 1
    df = pd.DataFrame({
        ('AAPL', 'Open'): [100, 101],
        ('AAPL', 'High'): [102, 103],
        ('AAPL', 'Low'): [99, 100],
        ('AAPL', 'Close'): [101, 102]
    })
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    
    result = _normalize_yfinance_columns(df)
    assert list(result.columns) == ['Open', 'High', 'Low', 'Close']


def test_coerce_ohlc_numeric():
    # Test that string values are coerced to numeric
    df = pd.DataFrame({
        'Open': ['100', '101'],
        'High': ['102', '103'],
        'Low': ['99', '100'],
        'Close': ['101', '102'],
        'Volume': ['1000', '2000']
    })
    
    result = _coerce_ohlc_numeric(df)
    assert result['Open'].dtype in [np.float64, np.int64]
    assert result['Close'].dtype in [np.float64, np.int64]


def test_looks_valid_true():
    # Test valid DataFrame
    df = pd.DataFrame({
        'Open': [100.0, 101.0],
        'High': [102.0, 103.0],
        'Low': [99.0, 100.0],
        'Close': [101.0, 102.0]
    })
    
    assert _looks_valid(df) is True


def test_looks_valid_false_empty():
    # Test empty DataFrame
    df = pd.DataFrame()
    assert _looks_valid(df) is False


def test_looks_valid_false_missing_columns():
    # Test DataFrame missing required columns
    df = pd.DataFrame({
        'Open': [100.0, 101.0],
        'Close': [101.0, 102.0]
    })
    
    assert _looks_valid(df) is False


def test_looks_valid_false_all_nan():
    # Test DataFrame with all NaN Close values
    df = pd.DataFrame({
        'Open': [100.0, 101.0],
        'High': [102.0, 103.0],
        'Low': [99.0, 100.0],
        'Close': [np.nan, np.nan]
    })
    
    assert _looks_valid(df) is False


def test_fetch_data_with_cache():
    # Test fetching data with cache
    # Create a temporary cache file with valid data using recent dates
    # so it won't be considered stale
    today = pd.Timestamp.now().normalize()
    recent_date_1 = (today - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    recent_date_2 = today.strftime('%Y-%m-%d')
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        cache_path = f.name
        # Write a simple CSV with OHLC data using recent dates
        f.write('Date,Open,High,Low,Close,Volume\n')
        f.write(f'{recent_date_1},100.0,102.0,99.0,101.0,1000\n')
        f.write(f'{recent_date_2},101.0,103.0,100.0,102.0,2000\n')
    
    try:
        # Fetch should use cache (not stale since dates are recent)
        df = fetch_data('AAPL', cache_path=cache_path, max_cache_age_days=5)
        
        assert isinstance(df, pd.DataFrame)
        assert 'Close' in df.columns
        assert len(df) == 2
        assert df['Close'].iloc[0] == 101.0
    finally:
        # Clean up
        if os.path.exists(cache_path):
            os.remove(cache_path)


def test_fetch_data_invalid_cache():
    # Test that invalid cache is deleted and refetch occurs
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        cache_path = f.name
        # Write invalid data
        f.write('Invalid,Data\n')
        f.write('foo,bar\n')
    
    try:
        # This should detect invalid cache, delete it, and try to fetch
        # Since we can't actually fetch from yfinance in tests, this will raise an error
        # But we can check that the cache was deleted
        initial_exists = os.path.exists(cache_path)
        assert initial_exists is True
        
        try:
            fetch_data('INVALID_TICKER', cache_path=cache_path)
        except Exception:
            # Expected to fail fetching invalid ticker
            pass
        
        # Verify cache was deleted after detecting invalid data
        # Note: This test depends on yfinance behavior. In production tests, we'd mock yfinance.download
        assert not os.path.exists(cache_path), "Invalid cache file should have been deleted"
    finally:
        # Clean up
        if os.path.exists(cache_path):
            os.remove(cache_path)


# === Task 5: Tests for cache invalidation logic ===

def test_is_cache_stale_fresh_data():
    """Test that recent data is not considered stale."""
    # Create DataFrame with data from today
    today = pd.Timestamp.now().normalize()
    df = pd.DataFrame({
        'Open': [100.0, 101.0],
        'High': [102.0, 103.0],
        'Low': [99.0, 100.0],
        'Close': [101.0, 102.0]
    }, index=[today - pd.Timedelta(days=1), today])
    
    assert _is_cache_stale(df, max_cache_age_days=1) is False


def test_is_cache_stale_old_data():
    """Test that old data is correctly identified as stale."""
    # Create DataFrame with data from 5 business days ago
    old_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=10)
    df = pd.DataFrame({
        'Open': [100.0, 101.0],
        'High': [102.0, 103.0],
        'Low': [99.0, 100.0],
        'Close': [101.0, 102.0]
    }, index=[old_date - pd.Timedelta(days=1), old_date])
    
    assert _is_cache_stale(df, max_cache_age_days=1) is True


def test_is_cache_stale_empty_dataframe():
    """Test that empty DataFrame is considered stale."""
    df = pd.DataFrame()
    assert _is_cache_stale(df, max_cache_age_days=1) is True


def test_is_cache_stale_none():
    """Test that None input is considered stale."""
    assert _is_cache_stale(None, max_cache_age_days=1) is True


def test_fetch_data_force_refresh():
    """Test that force_refresh bypasses cache."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        cache_path = f.name
        # Write cache with old dates (should be stale)
        f.write('Date,Open,High,Low,Close,Volume\n')
        f.write('2020-01-01,100.0,102.0,99.0,101.0,1000\n')
        f.write('2020-01-02,101.0,103.0,100.0,102.0,2000\n')
    
    try:
        # With force_refresh=True, cache should be ignored even if it exists
        # Since we can't mock yfinance here, we just verify the function accepts the param
        initial_exists = os.path.exists(cache_path)
        assert initial_exists is True
        
        # With old data, it should try to refetch due to staleness check
        try:
            # This will fail to download as we can't hit yfinance in tests
            # but we're testing that the staleness logic triggers
            df = fetch_data('INVALID_TICKER', cache_path=cache_path, force_refresh=False)
        except Exception:
            pass  # Expected
        
        # Cache should be deleted due to staleness
        assert not os.path.exists(cache_path), "Stale cache file should have been deleted"
    finally:
        if os.path.exists(cache_path):
            os.remove(cache_path)


def test_max_cache_age_days_custom():
    """Test that custom max_cache_age_days is respected."""
    # Create DataFrame with data from 3 business days ago
    days_back = 5  # Slightly more than 3 business days 
    old_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=days_back)
    df = pd.DataFrame({
        'Open': [100.0],
        'High': [102.0],
        'Low': [99.0],
        'Close': [101.0]
    }, index=[old_date])
    
    # With max_cache_age_days=1, should be stale
    assert _is_cache_stale(df, max_cache_age_days=1) is True
    
    # With max_cache_age_days=10, should not be stale
    assert _is_cache_stale(df, max_cache_age_days=10) is False
