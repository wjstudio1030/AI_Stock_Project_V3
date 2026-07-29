# scripts/indicators.py

import pandas as pd


def calc_rsi(df: pd.DataFrame, period: int = 14, price_col: str = "close") -> pd.Series:
    delta = df[price_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss != 0, 100)
    return rsi


def add_moving_averages(df: pd.DataFrame, windows=(5, 10, 20, 60), price_col: str = "close") -> pd.DataFrame:
    df = df.copy()
    for w in windows:
        df[f"MA{w}"] = df[price_col].rolling(window=w).mean()
    return df


def add_rsi_columns(df: pd.DataFrame, periods=(6, 14)) -> pd.DataFrame:
    df = df.copy()
    for p in periods:
        df[f"RSI{p}"] = calc_rsi(df, period=p)
    return df

def add_kd_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    min_low_9 = df['low'].rolling(window=9).min()
    max_high_9 = df['high'].rolling(window=9).max()
    df['RSV'] = 100 * (df['close'] - min_low_9) / (max_high_9 - min_low_9)
    # 預設前置值通常用 50
    df['K'] = df['RSV'].ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    return df