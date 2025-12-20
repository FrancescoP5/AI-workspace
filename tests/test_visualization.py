import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from simulator.visualization import (
    VisualizationConfig,
    add_visualization_columns,
    build_interactive_figure,
    filter_date_range,
    load_price_data,
    render_visualization,
)


def _sample_prices():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    base = pd.Series(150 + (pd.Series(range(30)) * 0.5), index=dates)
    df = pd.DataFrame(
        {
            "Open": base + 0.2,
            "High": base + 1.0,
            "Low": base - 1.0,
            "Close": base,
            "Adj Close": base,
            "Volume": 1_000,
        },
        index=dates,
    )
    return df


def test_filter_date_range_limits_bounds():
    df = _sample_prices()
    filtered = filter_date_range(df, start="2024-01-05", end="2024-01-10")

    assert filtered.index.min() >= pd.Timestamp("2024-01-05")
    assert filtered.index.max() <= pd.Timestamp("2024-01-10")
    assert len(filtered) == 6


def test_add_visualization_columns_adds_signal_change():
    df = add_visualization_columns(_sample_prices(), short=3, long=5)

    assert "sma_short" in df.columns
    assert "sma_long" in df.columns
    assert "signal" in df.columns
    assert "signal_change" in df.columns

    # signal_change should be 0 or 1/-1 transitions
    assert set(df["signal_change"].dropna().unique()).issubset({-1, 0, 1})


def test_build_interactive_figure_has_expected_traces():
    df = add_visualization_columns(_sample_prices(), short=3, long=5)
    cfg = VisualizationConfig(ticker="TEST", short=3, long=5)

    fig = build_interactive_figure(df, cfg)
    trace_names = [trace.name for trace in fig.data]  # type: ignore[attr-defined]

    assert "TEST OHLC" in trace_names
    assert "SMA 3" in trace_names
    assert "SMA 5" in trace_names
    assert "Buy signal" in trace_names
    assert "Sell signal" in trace_names
    assert fig.layout.xaxis.rangeslider.visible is True


def test_visualization_config_validates_sma_windows():
    """Test that VisualizationConfig validates SMA window parameters."""
    # Test short >= long raises error
    with pytest.raises(ValueError, match="short SMA window .* must be less than long SMA window"):
        VisualizationConfig(short=50, long=20)
    
    # Test short == long raises error
    with pytest.raises(ValueError, match="short SMA window .* must be less than long SMA window"):
        VisualizationConfig(short=20, long=20)
    
    # Test negative short raises error
    with pytest.raises(ValueError, match="short SMA window must be positive"):
        VisualizationConfig(short=-5, long=20)
    
    # Test negative long raises error
    with pytest.raises(ValueError, match="long SMA window must be positive"):
        VisualizationConfig(short=10, long=-20)
    
    # Test zero values raise error
    with pytest.raises(ValueError, match="short SMA window must be positive"):
        VisualizationConfig(short=0, long=20)
    
    # Valid configuration should work
    cfg = VisualizationConfig(short=10, long=20)
    assert cfg.short == 10
    assert cfg.long == 20


def test_filter_date_range_handles_invalid_dates():
    """Test that filter_date_range raises clear errors for invalid date strings."""
    df = _sample_prices()
    
    # Invalid start date
    with pytest.raises(ValueError, match="Invalid start date .* Please use an ISO date format"):
        filter_date_range(df, start="not-a-date")
    
    # Invalid end date
    with pytest.raises(ValueError, match="Invalid end date .* Please use an ISO date format"):
        filter_date_range(df, end="invalid-date")


def test_filter_date_range_insufficient_data():
    """Test behavior when filtered date range results in insufficient data."""
    df = _sample_prices()
    # Filter to a very narrow range
    filtered = filter_date_range(df, start="2024-01-15", end="2024-01-17")
    
    # Should have only 3 days of data
    assert len(filtered) == 3
    assert filtered.index.min() >= pd.Timestamp("2024-01-15")
    assert filtered.index.max() <= pd.Timestamp("2024-01-17")


@patch('simulator.visualization.fetch_data')
def test_load_price_data(mock_fetch_data):
    """Test load_price_data orchestrates fetching, caching, and filtering."""
    # Setup mock to return sample data
    mock_fetch_data.return_value = _sample_prices()
    
    cfg = VisualizationConfig(
        ticker="TEST",
        period="1mo",
        interval="1d",
        start="2024-01-05",
        end="2024-01-15",
        cache_dir=Path("/tmp/test_cache")
    )
    
    df = load_price_data(cfg)
    
    # Verify fetch_data was called with correct parameters
    mock_fetch_data.assert_called_once_with(
        "TEST",
        period="1mo",
        interval="1d",
        cache_path="/tmp/test_cache/TEST.csv"
    )
    
    # Verify data was filtered
    assert df.index.min() >= pd.Timestamp("2024-01-05")
    assert df.index.max() <= pd.Timestamp("2024-01-15")


@patch('simulator.visualization.load_price_data')
@patch('simulator.visualization.build_interactive_figure')
def test_render_visualization_integration(mock_build_figure, mock_load_data, tmp_path):
    """Test render_visualization orchestrates the complete pipeline."""
    # Setup mocks
    mock_df = _sample_prices()
    mock_load_data.return_value = mock_df
    
    mock_fig = MagicMock()
    mock_build_figure.return_value = mock_fig
    
    output_file = tmp_path / "test_output.html"
    cfg = VisualizationConfig(
        ticker="TEST",
        short=3,
        long=5,
        output_html=output_file
    )
    
    result = render_visualization(cfg)
    
    # Verify data loading was called
    mock_load_data.assert_called_once_with(cfg)
    
    # Verify figure building was called
    mock_build_figure.assert_called_once()
    
    # Verify HTML was written
    mock_fig.write_html.assert_called_once()
    
    assert result == output_file


@patch('simulator.visualization.load_price_data')
def test_render_visualization_insufficient_data(mock_load_data):
    """Test render_visualization raises error when insufficient data for SMA."""
    # Return a dataframe with fewer rows than the long SMA window
    small_df = _sample_prices().head(10)
    mock_load_data.return_value = small_df
    
    cfg = VisualizationConfig(ticker="TEST", short=20, long=50)
    
    with pytest.raises(ValueError, match="Insufficient data loaded for ticker TEST"):
        render_visualization(cfg)


@patch('simulator.visualization.load_price_data')
def test_render_visualization_empty_dataframe(mock_load_data):
    """Test render_visualization raises error when dataframe is empty."""
    # Return empty dataframe
    mock_load_data.return_value = pd.DataFrame()
    
    cfg = VisualizationConfig(ticker="TEST", short=3, long=5)
    
    with pytest.raises(ValueError, match="Insufficient data loaded for ticker TEST"):
        render_visualization(cfg)
