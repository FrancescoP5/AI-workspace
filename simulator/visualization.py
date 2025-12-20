"""Interactive stock visualization pipeline using yfinance + plotly.

CLI entrypoint:

    python -m simulator.visualization --ticker AAPL --period 1y --interval 1d \
        --short 20 --long 50 --start 2024-01-01 --end 2024-12-01

This produces an interactive HTML chart with zoom/pan, range selector, and SMA overlays.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

from simulator.data.yfinance_loader import fetch_data
from simulator.strategy import sma_crossover_signals

DEFAULT_CACHE_DIR = Path(__file__).parent / "data" / "cache"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "data" / "output"

# Chart color constants
COLOR_SMA_SHORT = "#1f77b4"
COLOR_SMA_LONG = "#ff7f0e"
COLOR_BUY_SIGNAL = "#2ca02c"
COLOR_SELL_SIGNAL = "#d62728"


@dataclass
class VisualizationConfig:
    ticker: str = "AAPL"
    period: str = "2y"
    interval: str = "1d"
    start: Optional[str] = None
    end: Optional[str] = None
    short: int = 20
    long: int = 50
    cache_dir: Path | None = DEFAULT_CACHE_DIR
    output_html: Path | None = None

    def __post_init__(self):
        """Validate SMA window parameters."""
        if self.short <= 0:
            raise ValueError(f"short SMA window must be positive, got {self.short}")
        if self.long <= 0:
            raise ValueError(f"long SMA window must be positive, got {self.long}")
        if self.short >= self.long:
            raise ValueError(
                f"short SMA window ({self.short}) must be less than long SMA window ({self.long})"
            )


def filter_date_range(df: pd.DataFrame, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
    """Filter dataframe by start/end ISO date strings if provided."""
    data = df.copy()
    try:
        data.index = pd.to_datetime(data.index)
    except (TypeError, ValueError) as exc:
        raise ValueError("Failed to convert dataframe index to datetime.") from exc

    start_ts = None
    end_ts = None

    if start:
        try:
            start_ts = pd.to_datetime(start)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid start date '{start}'. Please use an ISO date format such as 'YYYY-MM-DD'."
            ) from exc

    if end:
        try:
            end_ts = pd.to_datetime(end)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid end date '{end}'. Please use an ISO date format such as 'YYYY-MM-DD'."
            ) from exc

    if start_ts is not None:
        data = data.loc[data.index >= start_ts]
    if end_ts is not None:
        data = data.loc[data.index <= end_ts]

    return data


def load_price_data(cfg: VisualizationConfig) -> pd.DataFrame:
    cache_path: str | None = None
    if cfg.cache_dir is not None:
        cfg.cache_dir.mkdir(parents=True, exist_ok=True)
        # build cache path and normalize to POSIX so tests are stable across OS
        cache_path = (cfg.cache_dir / f"{cfg.ticker}.csv").as_posix()

    df = fetch_data(
        cfg.ticker,
        period=cfg.period,
        interval=cfg.interval,
        cache_path=cache_path,
    )
    df.index = pd.to_datetime(df.index)
    return filter_date_range(df, start=cfg.start, end=cfg.end)


def add_visualization_columns(df: pd.DataFrame, short: int, long: int) -> pd.DataFrame:
    data = sma_crossover_signals(df, short=short, long=long)
    # Track signal changes to place markers on the chart
    signal_delta = data['signal'].diff().fillna(0)
    data['signal_change'] = signal_delta
    return data


def build_interactive_figure(df: pd.DataFrame, cfg: VisualizationConfig) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name=f"{cfg.ticker} OHLC",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['sma_short'],
            name=f"SMA {cfg.short}",
            mode="lines",
            line={"width": 1.5, "color": COLOR_SMA_SHORT},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['sma_long'],
            name=f"SMA {cfg.long}",
            mode="lines",
            line={"width": 1.5, "color": COLOR_SMA_LONG},
        )
    )

    entries = df[df['signal_change'] == 1]
    exits = df[df['signal_change'] == -1]

    fig.add_trace(
        go.Scatter(
            x=entries.index,
            y=entries['Close'],
            mode="markers",
            name="Buy signal",
            marker={"color": COLOR_BUY_SIGNAL, "size": 8, "symbol": "triangle-up"},
            hovertemplate="Buy: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=exits.index,
            y=exits['Close'],
            mode="markers",
            name="Sell signal",
            marker={"color": COLOR_SELL_SIGNAL, "size": 8, "symbol": "triangle-down"},
            hovertemplate="Sell: %{y:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"{cfg.ticker} SMA {cfg.short}/{cfg.long} crossover",
        yaxis_title="Price",
        xaxis_title="Date",
        xaxis={
            "rangeslider":{"visible": True},
            "rangeselector": {
                "buttons": [
                    {"count": 1, "label": "1m", "step": "month", "stepmode": "backward"},
                    {"count": 3, "label": "3m", "step": "month", "stepmode": "backward"},
                    {"count": 6, "label": "6m", "step": "month", "stepmode": "backward"},
                    {"count": 1, "label": "YTD", "step": "year", "stepmode": "todate"},
                    {"count": 1, "label": "1y", "step": "year", "stepmode": "backward"},
                    {"step": "all"},
                ]
            },
        },
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        template="plotly_white",
    )
    return fig


def render_visualization(cfg: VisualizationConfig) -> Path:
    df = load_price_data(cfg)

    # Ensure we have enough data to compute the long SMA and build a meaningful chart
    if df.empty or len(df) <= cfg.long:
        date_range_desc = ""
        if cfg.start or cfg.end:
            date_range_desc = f" for date range {cfg.start or '…'} to {cfg.end or '…'}"
        raise ValueError(
            f"Insufficient data loaded for ticker {cfg.ticker}{date_range_desc}: "
            f"expected more than {cfg.long} data points to compute the long SMA, "
            f"but got {len(df)}."
        )

    df = add_visualization_columns(df, short=cfg.short, long=cfg.long)

    output_path = cfg.output_html
    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DEFAULT_OUTPUT_DIR / f"{cfg.ticker}_interactive.html"
    else:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fig = build_interactive_figure(df, cfg)
    fig.write_html(str(output_path), include_plotlyjs="cdn", full_html=True)
    return Path(output_path)


def parse_args() -> VisualizationConfig:
    parser = argparse.ArgumentParser(description="Build an interactive SMA crossover chart")
    parser.add_argument("--ticker", default="AAPL", help="Ticker to download")
    parser.add_argument("--period", default="2y", help="yfinance period (e.g., 6mo, 1y, 2y)")
    parser.add_argument("--interval", default="1d", help="yfinance interval (e.g., 1d, 1h)")
    parser.add_argument("--start", help="Optional start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="Optional end date (YYYY-MM-DD)")
    parser.add_argument("--short", type=int, default=20, help="Short SMA window")
    parser.add_argument("--long", type=int, default=50, help="Long SMA window")
    parser.add_argument(
        "--output",
        dest="output_html",
        help="Path to output HTML (default: simulator/data/output/<ticker>_interactive.html)",
    )
    parser.add_argument(
        "--cache-dir",
        dest="cache_dir",
        default=str(DEFAULT_CACHE_DIR),
        help="Directory for cached CSV files",
    )
    args = parser.parse_args()

    # Validate output path if provided
    output_path = None
    if args.output_html:
        output_path = Path(args.output_html)
        parent_dir = output_path.parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
            except (OSError) as exc:
                raise ValueError(
                    f"Cannot create output directory '{parent_dir}': {exc}"
                ) from exc
        elif not parent_dir.is_dir():
            raise ValueError(
                f"Output path parent '{parent_dir}' exists but is not a directory"
            )

    return VisualizationConfig(
        ticker=args.ticker,
        period=args.period,
        interval=args.interval,
        start=args.start,
        end=args.end,
        short=args.short,
        long=args.long,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        output_html=output_path,
    )


def main():
    cfg = parse_args()
    output_path = render_visualization(cfg)
    print(f"Saved interactive chart to {output_path}")


if __name__ == "__main__":
    main()
