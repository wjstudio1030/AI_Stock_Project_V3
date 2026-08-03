"""無資料洩漏的 walk-forward 回測。

每個訊號只使用當日收盤以前的資料訓練，並於下一交易日開盤進場；
不載入已用全歷史訓練的部署模型，也不假設可用當日收盤價成交。
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from config import (
    DOCS_DATA_DIR,
    FEE_RATE,
    HOLD_DAYS,
    STOCK_LIST,
    TAX_RATE,
    XGB_MIN_TRAIN_SAMPLES,
    XGB_SIGNAL_THRESHOLD,
)
from model_features import build_feature_frame, build_training_data, load_merged_data
from xgb_model import make_classifier


def _simulate(df: pd.DataFrame, signals: pd.Series, name: str, initial_capital: float = 1_000_000.0) -> dict:
    capital = initial_capital
    trades = []
    i = 0
    while i < len(df) - HOLD_DAYS - 1:
        if not bool(signals.iloc[i]):
            i += 1
            continue
        buy_idx = i + 1
        sell_idx = min(buy_idx + HOLD_DAYS, len(df) - 1)
        buy_price = float(df.iloc[buy_idx]["open"])
        sell_price = float(df.iloc[sell_idx]["close"])
        if buy_price <= 0 or sell_price <= 0:
            i += 1
            continue
        cost_buy = buy_price * (1 + FEE_RATE)
        revenue_sell = sell_price * (1 - FEE_RATE - TAX_RATE)
        net_return = revenue_sell / cost_buy - 1
        profit = capital * net_return
        capital += profit
        trades.append({
            "signal_date": df.iloc[i]["date"].strftime("%Y-%m-%d"),
            "buy_date": df.iloc[buy_idx]["date"].strftime("%Y-%m-%d"),
            "sell_date": df.iloc[sell_idx]["date"].strftime("%Y-%m-%d"),
            "buy_price": round(buy_price, 2),
            "sell_price": round(sell_price, 2),
            "net_return_pct": round(net_return * 100, 2),
            "net_profit": round(profit, 0),
        })
        i = sell_idx + 1

    wins = sum(t["net_return_pct"] > 0 for t in trades)
    total = len(trades)
    return {
        "strategy": name,
        "initial_capital": initial_capital,
        "final_capital": round(capital, 0),
        "total_return_pct": round((capital / initial_capital - 1) * 100, 2),
        "trades": total,
        "wins": wins,
        "win_rate_pct": round(wins / total * 100, 1) if total else None,
        "trade_log": trades,
    }


def _walk_forward_probabilities(df: pd.DataFrame, test_start: int) -> pd.Series:
    X_all = build_feature_frame(df)
    probs = pd.Series(np.nan, index=df.index, dtype=float)
    for idx in range(test_start, len(df) - 1):
        history = df.iloc[: idx + 1].copy()
        X_train, y_train, _ = build_training_data(history)
        if len(X_train) < XGB_MIN_TRAIN_SAMPLES:
            continue
        row = X_all.iloc[[idx]]
        if row.isna().any().any():
            continue
        model = make_classifier(random_state=42)
        model.fit(X_train, y_train)
        probs.iloc[idx] = float(model.predict_proba(row)[0][1])
    return probs


def run_backtest(stock_id: str, test_days: int = 250) -> dict:
    df = load_merged_data(stock_id)
    if len(df) < XGB_MIN_TRAIN_SAMPLES + 50:
        raise ValueError("歷史資料不足以執行 walk-forward 回測")
    test_start = max(XGB_MIN_TRAIN_SAMPLES, len(df) - test_days)

    k_prev = df["k_val"].shift(1)
    d_prev = df["d_val"].shift(1)
    ma60_prev = df["ma60"].shift(1)
    signal_old = (
        (k_prev <= 20)
        & (k_prev < d_prev)
        & (df["k_val"] > df["d_val"])
        & (df["close"] > df["ma60"])
        & (df["ma60"] > ma60_prev)
    )
    signal_old.iloc[:test_start] = False

    probs = _walk_forward_probabilities(df, test_start)
    signal_ai = (probs >= XGB_SIGNAL_THRESHOLD) & (df["foreign_net"] > 0)
    signal_ai = signal_ai.fillna(False)

    result = {
        "stock_id": stock_id,
        "methodology": "expanding-window walk-forward; signal at close; next-day open entry",
        "test_start": df.iloc[test_start]["date"].strftime("%Y-%m-%d"),
        "test_end": df.iloc[-1]["date"].strftime("%Y-%m-%d"),
        "transaction_cost": {"fee_each_side": FEE_RATE, "sell_tax": TAX_RATE},
        "old_strategy": _simulate(df, signal_old, "V2 技術條件"),
        "xgb_strategy": _simulate(df, signal_ai, "V3 XGBoost walk-forward"),
    }
    out = DOCS_DATA_DIR / f"{stock_id}_backtest.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ [{stock_id}] walk-forward 回測完成：{out}")
    return result


def main(stock_ids: list[str]) -> int:
    failures = []
    for stock_id in stock_ids:
        try:
            run_backtest(stock_id)
        except Exception as exc:
            failures.append(stock_id)
            print(f"❌ [{stock_id}] 回測失敗：{exc}")
    return 1 if failures and len(failures) == len(stock_ids) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or STOCK_LIST[:1]))
