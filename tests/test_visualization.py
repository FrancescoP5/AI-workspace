import pandas as pd

from simulator.visualization import (
    VisualizationConfig,
    add_visualization_columns,
    build_interactive_figure,
    filter_date_range,
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
    trace_names = [trace.name for trace in fig.data]

    assert "TEST OHLC" in trace_names
    assert "SMA 3" in trace_names
    assert "SMA 5" in trace_names
    assert "Buy signal" in trace_names
    assert "Sell signal" in trace_names
    assert fig.layout.xaxis.rangeslider.visible is True
