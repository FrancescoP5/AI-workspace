import numpy as np
import pandas as pd


class Backtester:
    def __init__(self, initial_capital: float = 10000.0, price_col: str = 'Close', signal_col: str = 'signal'):
        self.initial_capital = float(initial_capital)
        self.price_col = price_col
        self.signal_col = signal_col

    def run(self, df: pd.DataFrame):
        df = df.copy()
        prices = df[self.price_col]
        if isinstance(prices, pd.DataFrame):
            prices = prices.squeeze()

        # positions: 1 if signal==1 else 0; use prior day's signal for today's returns (no lookahead)
        signals = df[self.signal_col]
        if isinstance(signals, pd.DataFrame):
            signals = signals.squeeze()
        positions = pd.Series(signals).fillna(0).shift(1).fillna(0)

        # daily returns of the asset
        # `fill_method=None` avoids implicit forward-fill behavior warnings in recent pandas
        if not isinstance(prices, pd.Series):
            raise TypeError(f"Expected 'prices' to be a pandas Series, but got {type(prices).__name__}")
        returns = prices.pct_change(fill_method=None).fillna(0)

        # strategy returns = position * asset returns
        strategy_returns = positions * returns

        # equity curve
        equity = (1 + strategy_returns).cumprod() * self.initial_capital

        # metrics
        total_return = equity.iloc[-1] / self.initial_capital - 1
        days = max(len(df), 1)
        annualized_return = (1 + total_return) ** (252.0 / days) - 1 if days > 0 else 0.0
        ann_vol = strategy_returns.std() * np.sqrt(252)
        sharpe = (strategy_returns.mean() * 252) / (ann_vol + 1e-12)

        running_max = equity.cummax()
        drawdown = (equity - running_max) / running_max
        max_drawdown = drawdown.min()

        metrics = {
            'initial_capital': self.initial_capital,
            'final_capital': float(equity.iloc[-1]),
            'total_return': float(total_return),
            'annualized_return': float(annualized_return),
            'annualized_vol': float(ann_vol),
            'sharpe': float(sharpe),
            'max_drawdown': float(max_drawdown)
        }

        return {
            'equity': equity,
            'strategy_returns': strategy_returns,
            'positions': positions,
            'metrics': metrics
        }
