"""Live auto-refresh visualization server.

Starts a small Flask app that serves the interactive Plotly chart and
provides a JSON endpoint for fresh data. The client polls the endpoint on a
configurable interval (30s, 1m, 5m) and updates the chart without a full page
reload.
"""
from __future__ import annotations

import html
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

import pandas as pd
from flask import Flask, Response, jsonify

from simulator.visualization import (
    LIVE_REFRESH_INTERVALS,
    VisualizationConfig,
    add_visualization_columns,
    build_interactive_figure,
    load_price_data,
)
from simulator.data.yfinance_loader import DEFAULT_MAX_CACHE_AGE_DAYS

logger = logging.getLogger(__name__)

MIN_REFRESH_SECONDS = 30


class FigureCache:
    def __init__(self):
        self.figure_json: str | None = None
        self.fetched_at: datetime | None = None
        self.data_timestamp: datetime | None = None

    def is_fresh(self, min_refresh_seconds: int) -> bool:
        if self.figure_json is None or self.fetched_at is None:
            return False
        delta = datetime.now(timezone.utc) - self.fetched_at
        return delta.total_seconds() < min_refresh_seconds


def _build_figure(
    cfg: VisualizationConfig,
    cache: FigureCache,
    data_loader: Callable[[VisualizationConfig, bool], pd.DataFrame],
    min_refresh_seconds: int,
    force_refresh_data: bool = False,
) -> tuple[str, datetime, datetime, bool]:
    now = datetime.now(timezone.utc)
    if cache.is_fresh(min_refresh_seconds) and not force_refresh_data:
        # Return cached figure without re-querying the data source.
        assert cache.figure_json is not None
        assert cache.fetched_at is not None
        assert cache.data_timestamp is not None
        return cache.figure_json, cache.fetched_at, cache.data_timestamp, True

    # In live mode, use force_refresh=True to bypass file cache staleness
    df = data_loader(cfg, force_refresh_data)
    if df.empty or len(df) <= cfg.long:
        raise ValueError(
            f"Insufficient data loaded for ticker {cfg.ticker}: expected more than {cfg.long} data points, got {len(df)}."
        )

    df = add_visualization_columns(df, short=cfg.short, long=cfg.long)
    data_timestamp = pd.to_datetime(df.index.max()).to_pydatetime().replace(tzinfo=timezone.utc)
    fig = build_interactive_figure(df, cfg)
    figure_json = fig.to_json()

    cache.figure_json = figure_json
    cache.fetched_at = now
    cache.data_timestamp = data_timestamp
    return figure_json, now, data_timestamp, False


def _stale_data_flag(data_timestamp: datetime) -> bool:
    return (datetime.now(timezone.utc) - data_timestamp) > timedelta(hours=24)


def _build_live_page(
    cfg: VisualizationConfig,
    figure_json: str,
    fetched_at_iso: str,
    data_timestamp_iso: str,
    intervals: tuple[int, ...],
    default_interval: int,
) -> str:
    interval_options = "".join(
        f"<option value=\"{seconds}\">{seconds//60 if seconds >= 60 else seconds}{'m' if seconds >= 60 else 's'}</option>"
        for seconds in intervals
    )

    escaped_figure_json = figure_json.replace("</", "<\\/")
    intervals_json = json.dumps(list(intervals))

    return f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{html.escape(cfg.ticker)} live SMA chart</title>
  <script src=\"https://cdn.plot.ly/plotly-latest.min.js\"></script>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; padding: 1rem; background: #f7f9fb; }}
    h1 {{ margin: 0 0 0.5rem 0; font-size: 1.2rem; }}
    #chart {{ width: 100%; height: 70vh; }}
    .panel {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }}
    .tag {{ padding: 0.2rem 0.55rem; border-radius: 0.35rem; background: #eef2f7; color: #1f2b3a; font-size: 0.9rem; }}
    button {{ padding: 0.45rem 0.9rem; border: none; background: #1f77b4; color: white; border-radius: 0.35rem; cursor: pointer; }}
    button[data-state="stopped"] {{ background: #2ca02c; }}
    button:disabled {{ opacity: 0.6; cursor: not-allowed; }}
    select {{ padding: 0.35rem; border-radius: 0.3rem; border: 1px solid #ccd5e0; }}
    .status {{ font-size: 0.9rem; color: #1f2b3a; }}
    .status strong {{ margin-right: 0.35rem; }}
    .error {{ color: #d62728; font-weight: 600; }}
    .muted {{ color: #6b7280; }}
    .warning-banner {{ background: #fef3cd; border: 1px solid #ffc107; padding: 0.5rem 1rem; border-radius: 0.35rem; margin-bottom: 0.5rem; display: none; }}
    .warning-banner.visible {{ display: block; }}
    .warning-text {{ color: #856404; font-weight: 500; }}
    .stale-indicator {{ color: #d62728; font-weight: 600; }}
  </style>
</head>
<body>
  <div class="warning-banner" id="stale-warning">
    <span class="warning-text">⚠️ Data may be delayed - last market data is more than 24 hours old. Market may be closed.</span>
  </div>
  <h1>Live SMA crossover - {html.escape(cfg.ticker)}</h1>
  <div class=\"panel\">
    <label for=\"interval-select\">Refresh interval</label>
    <select id=\"interval-select\" aria-label=\"Refresh interval\">{interval_options}</select>
    <button id=\"toggle\" data-state=\"running\">Stop live updates</button>
    <span class=\"tag\" id=\"loading\" style=\"display:none\">Fetching...</span>
    <span class=\"tag\" id=\"from-cache\" style=\"display:none\">Cached</span>
  </div>
  <div class=\"status\">
    <strong>Status:</strong> <span id=\"status-text\">Live</span> ·
    <span>Last refresh: <span id=\"last-refresh\">{fetched_at_iso}</span></span> ·
    <span>Data timestamp: <span id=\"data-timestamp\">{data_timestamp_iso}</span></span>
    <span class=\"error\" id=\"error-text\"></span>
  </div>
  <div id=\"chart\"></div>
  <script id=\"initial-figure\" type=\"application/json\">{escaped_figure_json}</script>
  <script>
    const availableIntervals = {intervals_json};
    const defaultInterval = {default_interval};
    const intervalSelect = document.getElementById('interval-select');
    const toggle = document.getElementById('toggle');
    const statusText = document.getElementById('status-text');
    const lastRefreshEl = document.getElementById('last-refresh');
    const dataTimestampEl = document.getElementById('data-timestamp');
    const loadingTag = document.getElementById('loading');
    const cacheTag = document.getElementById('from-cache');
    const errorText = document.getElementById('error-text');
    const staleWarning = document.getElementById('stale-warning');
    const initialFigure = JSON.parse(document.getElementById('initial-figure').textContent);

    let timerId = null;

    function setLoading(isLoading) {{
      loadingTag.style.display = isLoading ? 'inline-block' : 'none';
    }}

    function setCacheTag(isCached) {{
      cacheTag.style.display = isCached ? 'inline-block' : 'none';
    }}

    function setStaleWarning(isStale) {{
      staleWarning.classList.toggle('visible', isStale);
    }}

    async function fetchAndUpdate() {{
      setLoading(true);
      errorText.textContent = '';
      try {{
        const res = await fetch('/api/figure');
        const payload = await res.json();

        if (!res.ok || payload.error) {{
          throw new Error(payload.error || 'Request failed');
        }}

        const fig = JSON.parse(payload.figure);
        await Plotly.react('chart', fig.data, fig.layout);
        lastRefreshEl.textContent = new Date(payload.fetched_at).toLocaleTimeString();
        dataTimestampEl.textContent = payload.data_timestamp;
        const isStale = Boolean(payload.stale);
        statusText.textContent = isStale ? 'Stale data (market closed or rate limited)' : 'Live';
        setStaleWarning(isStale);
        setCacheTag(Boolean(payload.from_cache));
      }} catch (err) {{
        console.error(err);
        errorText.textContent = err.message || 'Unable to refresh data';
        statusText.textContent = 'Paused after error';
        stop();
      }} finally {{
        setLoading(false);
      }}
    }}

    function start() {{
      if (timerId) return;
      const intervalMs = Number(intervalSelect.value) * 1000;
      timerId = setInterval(fetchAndUpdate, intervalMs);
      fetchAndUpdate();
      toggle.dataset.state = 'running';
      toggle.textContent = 'Stop live updates';
      statusText.textContent = 'Live';
    }}

    function stop() {{
      if (timerId) {{
        clearInterval(timerId);
        timerId = null;
      }}
      toggle.dataset.state = 'stopped';
      toggle.textContent = 'Start live updates';
    }}

    toggle.addEventListener('click', () => {{
      if (toggle.dataset.state === 'running') {{
        stop();
      }} else {{
        start();
      }}
    }});

    intervalSelect.addEventListener('change', () => {{
      if (toggle.dataset.state === 'running') {{
        stop();
        start();
      }}
    }});

    document.addEventListener('visibilitychange', () => {{
      if (document.hidden) {{
        stop();
      }} else if (toggle.dataset.state === 'running') {{
        start();
      }}
    }});

    // Initialize chart and controls
    intervalSelect.value = defaultInterval.toString();
    Plotly.newPlot('chart', initialFigure.data, initialFigure.layout);
    start();
  </script>
</body>
</html>
"""


def create_live_app(
    cfg: VisualizationConfig,
    *,
    data_loader: Callable[[VisualizationConfig, bool], pd.DataFrame] = load_price_data,
    min_refresh_seconds: int = MIN_REFRESH_SECONDS,
    force_refresh_data: bool = True,
) -> Flask:
    """Create a Flask app for live visualization.
    
    Args:
        cfg: Visualization configuration
        data_loader: Function to load price data (cfg, force_refresh) -> DataFrame
        min_refresh_seconds: Minimum seconds between API figure updates
        force_refresh_data: If True, bypass file cache on each API call (default for live mode)
    """
    cache = FigureCache()
    app = Flask(__name__)

    @app.get("/api/figure")
    def api_figure():
        try:
            # In live mode, force_refresh_data=True bypasses stale file cache
            figure_json, fetched_at, data_timestamp, from_cache = _build_figure(
                cfg, cache, data_loader, min_refresh_seconds, force_refresh_data
            )
            return jsonify(
                {
                    "figure": figure_json,
                    "fetched_at": fetched_at.isoformat(),
                    "data_timestamp": data_timestamp.isoformat(),
                    "from_cache": from_cache,
                    "stale": _stale_data_flag(data_timestamp),
                }
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Live update failed for %s: %s", cfg.ticker, exc)
            if cache.figure_json and cache.fetched_at and cache.data_timestamp:
                return (
                    jsonify(
                        {
                            "figure": cache.figure_json,
                            "fetched_at": cache.fetched_at.isoformat(),
                            "data_timestamp": cache.data_timestamp.isoformat(),
                            "from_cache": True,
                            "stale": True,
                            "error": str(exc),
                        }
                    ),
                    200,
                )
            return jsonify({"error": str(exc)}), 503

    @app.get("/")
    def index() -> Response:
        # For initial page load, also use force_refresh to ensure fresh data
        figure_json, fetched_at, data_timestamp, _ = _build_figure(
            cfg, cache, data_loader, min_refresh_seconds, force_refresh_data
        )
        html_page = _build_live_page(
            cfg,
            figure_json=figure_json,
            fetched_at_iso=fetched_at.isoformat(),
            data_timestamp_iso=data_timestamp.isoformat(),
            intervals=LIVE_REFRESH_INTERVALS,
            default_interval=cfg.refresh_seconds,
        )
        return Response(html_page, mimetype="text/html")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "ticker": cfg.ticker}

    return app


def run_live_server(cfg: VisualizationConfig):
    if cfg.refresh_seconds < MIN_REFRESH_SECONDS:
        logger.info(
            "Using minimum refresh %s seconds to respect rate limits", MIN_REFRESH_SECONDS
        )
        cfg.refresh_seconds = MIN_REFRESH_SECONDS

    app = create_live_app(cfg)
    logger.info(
        "Starting live server for %s on http://localhost:%s (interval %ss)",
        cfg.ticker,
        cfg.port,
        cfg.refresh_seconds,
    )
    print(
        f"Live mode enabled for {cfg.ticker}. Open http://localhost:{cfg.port} to view the chart. "
        f"Intervals available: {', '.join(str(v) for v in LIVE_REFRESH_INTERVALS)} seconds."
    )
    app.run(host="0.0.0.0", port=cfg.port, debug=False, use_reloader=False)
