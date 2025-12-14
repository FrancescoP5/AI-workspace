import numpy as np
import pandas as pd

# Number of trading days per year for annualization calculations
TRADING_DAYS_PER_YEAR = 252


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
        if equity.empty:
            final_capital = self.initial_capital
            total_return = 0.0
            annualized_return = 0.0
            ann_vol = 0.0
            sharpe = 0.0
            max_drawdown = 0.0
        else:
            final_capital = float(equity.iloc[-1])
            total_return = final_capital / self.initial_capital - 1
            days = max(len(df), 1)
            annualized_return = (1 + total_return) ** (TRADING_DAYS_PER_YEAR / days) - 1 if days > 0 else 0.0
            ann_vol = strategy_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
            # Sharpe ratio calculation assumes zero risk-free rate
            sharpe = (strategy_returns.mean() * TRADING_DAYS_PER_YEAR) / (ann_vol + 1e-12)
            running_max = equity.cummax()
            # Avoid division by zero in max drawdown calculation
            # If running_max is zero (equity never positive), set drawdown to 0
            if (running_max == 0).any():
                running_max_safe = running_max.replace(0, 1e-12)
            else:
                running_max_safe = running_max
            drawdown = (equity - running_max_safe) / running_max_safe
            max_drawdown = drawdown.min()

        metrics = {
            'initial_capital': self.initial_capital,
            'final_capital': float(final_capital),
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
