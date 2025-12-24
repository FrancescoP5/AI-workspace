import pandas as pd
from simulator.live_visualization import create_live_app
from simulator.visualization import VisualizationConfig


def _sample_prices():
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    base = pd.Series(100 + (pd.Series(range(40)) * 0.5), index=dates)
    return pd.DataFrame(
        {
            "Open": base + 0.1,
            "High": base + 1.0,
            "Low": base - 1.0,
            "Close": base,
            "Adj Close": base,
            "Volume": 1_000,
        },
        index=dates,
    )


def test_live_app_serves_cached_figure_twice():
    """Test that the live app caches the figure (not data) to avoid hitting API too frequently."""
    cfg = VisualizationConfig(ticker="TEST", short=3, long=5)

    call_count = {"count": 0}

    def loader(_cfg, _force_refresh=False):
        call_count["count"] += 1
        return _sample_prices()

    # For this test, we use force_refresh_data=False to test figure caching behavior
    # In production live mode, force_refresh_data=True is the default to ensure fresh data
    app = create_live_app(cfg, data_loader=loader, min_refresh_seconds=30, force_refresh_data=False)
    client = app.test_client()

    first = client.get("/api/figure")
    second = client.get("/api/figure")

    payload_first = first.get_json()
    payload_second = second.get_json()

    assert payload_first["from_cache"] is False
    assert payload_second["from_cache"] is True
    assert payload_first["figure"] == payload_second["figure"]
    assert call_count["count"] == 1


def test_live_app_returns_error_when_loader_fails_without_cache():
    cfg = VisualizationConfig(ticker="FAIL", short=3, long=5)

    def loader(_cfg, _force_refresh=False):  # pragma: no cover - error path
        raise ValueError("network down")

    app = create_live_app(cfg, data_loader=loader, min_refresh_seconds=30)
    client = app.test_client()

    resp = client.get("/api/figure")
    assert resp.status_code == 503
    payload = resp.get_json()
    assert "error" in payload
    assert payload["error"] == "network down"


def test_index_returns_html_with_controls():
    cfg = VisualizationConfig(ticker="HTML", short=3, long=5)
    app = create_live_app(cfg, data_loader=lambda _cfg, _force=False: _sample_prices())
    client = app.test_client()

    resp = client.get("/")
    body = resp.get_data(as_text=True)

    assert "Refresh interval" in body
    assert "Stop live updates" in body
    assert "application/json" in body
