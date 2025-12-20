import logging
import os
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


_REQUIRED_COLS = ['Open', 'High', 'Low', 'Close']


def _normalize_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize yfinance output to single-level OHLCV columns."""
    if isinstance(df.columns, pd.MultiIndex):
        level0 = set(df.columns.get_level_values(0))
        level1 = set(df.columns.get_level_values(1))
        if set(_REQUIRED_COLS).issubset(level0):
            df = df.copy()
            df.columns = df.columns.droplevel(1)
        elif set(_REQUIRED_COLS).issubset(level1):
            df = df.copy()
            df.columns = df.columns.droplevel(0)
    return df


def _coerce_ohlc_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def _looks_valid(df: pd.DataFrame) -> bool:
    if df is None or getattr(df, 'empty', True):
        return False
    if not set(_REQUIRED_COLS).issubset(set(df.columns)):
        return False
    # require Close to be mostly numeric
    close = pd.to_numeric(df['Close'], errors='coerce')
    return bool(close.notna().any())


def _read_csv_with_header(cache_path: str, header: int | list[int]):
    """Helper to read CSV with given header parameter and handle exceptions."""
    try:
        return pd.read_csv(cache_path, header=header, index_col=0, parse_dates=True)
    except (pd.errors.ParserError, ValueError, KeyError) as e:
        header_type = "MultiIndex" if isinstance(header, list) else "single"
        logger.debug(f"Failed to read cache with {header_type} header: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error reading cache file {cache_path}: {e}")
        return None


def fetch_data(ticker, period='2y', interval='1d', cache_path=None):
    """Fetch OHLCV data for `ticker` using yfinance. Optionally cache to CSV.

    Returns a DataFrame indexed by DatetimeIndex with columns: Open, High, Low, Close, Adj Close, Volume
    """
    if cache_path and os.path.exists(cache_path):
        # Cache may come from older runs with MultiIndex headers; try both formats.
        df = _read_csv_with_header(cache_path, header=0)

        if df is None or (isinstance(df, pd.DataFrame) and 'Close' not in df.columns):
            df = _read_csv_with_header(cache_path, header=[0, 1])

        if isinstance(df, pd.DataFrame):
            df = _normalize_yfinance_columns(df)
            df = _coerce_ohlc_numeric(df)
            df.index = pd.to_datetime(df.index, errors='coerce')

        if df is not None and _looks_valid(df):
            return df

        # If cache is invalid, delete it and refetch.
        try:
            os.remove(cache_path)
        except OSError as e:
            logger.warning(f"Failed to delete invalid cache file {cache_path}: {e}")

    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
    if df is None or df.empty:
        raise ValueError(f"No data returned for {ticker}")

    df = _normalize_yfinance_columns(df)
    df = _coerce_ohlc_numeric(df)

    df.index = pd.to_datetime(df.index)
    if cache_path:
        try:
            df.to_csv(cache_path)
        except OSError as e:
            logger.warning(f"Failed to write cache file {cache_path}: {e}")
    return df
