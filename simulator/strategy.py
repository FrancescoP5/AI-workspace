import pandas as pd


def sma_crossover_signals(df: pd.DataFrame, short: int = 20, long: int = 50) -> pd.DataFrame:
    """Add simple SMA crossover signals to a copy of df.

    The function returns a new DataFrame with columns `sma_short`, `sma_long`, and `signal`.
    `signal` is 1 when short SMA > long SMA, otherwise 0.
    """
    data = df.copy()
    close = data['Close']
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()
    data['sma_short'] = close.rolling(window=short, min_periods=1).mean()
    data['sma_long'] = close.rolling(window=long, min_periods=1).mean()
    data['signal'] = 0
    data.loc[data['sma_short'] > data['sma_long'], 'signal'] = 1
    return data
