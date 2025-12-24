# CURRENT SPRINT STATUS
**Last Update:** 2025-12-24 11:50 UTC
**Phase:** Bugfix

## 🌿 GIT INSTRUCTIONS (Mandatory)
- **Active Branch:** `fix/live-visualization-bugs`
- **Base Branch:** `feat/live-stock-updates`
- **Action:** Checkout & Create (from `feat/live-stock-updates`)
- **Commit Message Prefix:** `[FIX] `

## 🎯 PRIMARY OBJECTIVE
Fix **two critical bugs** in the live visualization feature: (1) stale cached data not being refreshed (showing Dec 12 instead of Dec 24), and (2) candlestick chart not rendering properly (only SMA lines visible).

## 📋 TODO LIST
- [ ] Task 1 (Priority: Critical) - **Fix stale cache data bug in `yfinance_loader.py`**
  - Current behavior: Cache is read if file exists and looks valid, but no freshness check
  - Root cause: `fetch_data()` only checks if cache file exists and has valid columns, NOT if data is recent
  - Fix: Add cache staleness detection - if the latest date in cached data is older than 1 trading day (or configurable threshold), invalidate and re-fetch
  - Implementation hints:
    - After loading cache, check `df.index.max()` against current date
    - If gap > 1 business day, delete cache and re-download from yfinance
    - Consider adding a `max_cache_age_days` parameter (default: 1)

- [ ] Task 2 (Priority: Critical) - **Fix candlestick chart not rendering in live visualization**
  - Current behavior: Only SMA lines visible, candlesticks appear hidden/invisible
  - Suspected causes (investigate all):
    1. Plotly rangeslider may be overlapping/hiding candlesticks - try disabling or adjusting `rangeslider.visible`
    2. The candlestick trace may be hidden behind other traces - check trace order or use `opacity`
    3. Y-axis range may be incorrectly auto-scaled - verify `yaxis.autorange` settings
    4. Check if OHLC columns are being passed correctly to `go.Candlestick` (numeric types, no NaN)
  - Test by: Temporarily removing SMA traces to see if candlesticks appear alone

- [ ] Task 3 (Priority: High) - **Add live data bypass for cache in live mode**
  - In `live_visualization.py`, when refreshing data via `/api/figure`, consider bypassing cache entirely OR using a shorter cache TTL
  - The `FigureCache` class caches the figure but underlying data may still come from stale CSV
  - Fix: Add a `force_refresh=True` option to `load_price_data()` that skips file cache

- [ ] Task 4 (Priority: Medium) - **Add visual feedback for data freshness**
  - Show clear warning if data timestamp is more than 24 hours old
  - Display "Market Closed" or "Data may be delayed" message when appropriate
  - The `_stale_data_flag()` function exists but UI feedback could be more prominent

- [ ] Task 5 (Priority: Low) - **Add unit tests for cache invalidation logic**
  - Test that cache is invalidated when data is stale
  - Test that candlestick trace is properly included in figure output

## 🧠 CONTEXT & CONSTRAINTS
- **Bug Evidence (from user report):**
  - Screenshot shows "Data timestamp: 2025-12-12T00:00:00+00:00" (today is Dec 24)
  - Status shows "Stale data (market closed or rate limited)" - but issue is stale cache
  - Chart shows SMA lines but NO candlesticks visible at all
- **Files to Modify:**
  - `simulator/data/yfinance_loader.py` - Add cache freshness check (Task 1)
  - `simulator/visualization.py` - Fix candlestick rendering (Task 2)
  - `simulator/live_visualization.py` - Add force refresh option (Task 3)
- **Cache Location:** `simulator/data/cache/AAPL.csv` (last row is 2025-12-12)
- **Debug Steps:**
  1. Delete cache files manually and test if fresh data loads
  2. Inspect Plotly figure JSON to confirm candlestick trace data exists
  3. Check browser console for any JavaScript errors
- **Do NOT break existing tests** - run `pytest tests/` after changes
- **Remember:** Commit each fix separately with descriptive messages
