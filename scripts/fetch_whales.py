"""以免費法人與融資資料建立『籌碼代理分數』。

這不是集保股權分散表，也不宣稱是真實大戶持股百分比。輸出為 0~100 的代理分數，
只表示法人資金流與融資變化相對於自身近期歷史的位置。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from config import FINMIND_TOKEN, STOCK_LIST
from data_fetcher import get_institutional_investors, get_margin_trading
from db_manager import upsert_dataframe


def _rolling_z(series: pd.Series, window: int = 26) -> pd.Series:
    min_periods = min(8, window)
    mean = series.rolling(window, min_periods=min_periods).mean()
    std = series.rolling(window, min_periods=min_periods).std(ddof=0).replace(0, np.nan)
    return ((series - mean) / std).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def get_position_proxy(stock_id: str, lookback_days: int = 730) -> pd.DataFrame:
    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    inst = get_institutional_investors(stock_id, start_date, end_date, token=FINMIND_TOKEN)
    margin = get_margin_trading(stock_id, start_date, end_date, token=FINMIND_TOKEN)

    inst = inst[["date", "total_net"]].copy()
    inst["total_net_lots"] = pd.to_numeric(inst["total_net"], errors="coerce").fillna(0) / 1000
    margin = margin[["date", "margin_balance"]].copy()
    margin["margin_balance"] = pd.to_numeric(margin["margin_balance"], errors="coerce")
    merged = inst.merge(margin, on="date", how="inner").sort_values("date").set_index("date")
    if merged.empty:
        return pd.DataFrame()

    weekly = merged.resample("W-FRI").agg(
        institutional_flow=("total_net_lots", "sum"),
        margin_balance=("margin_balance", "last"),
    ).dropna().reset_index()
    weekly["margin_change"] = weekly["margin_balance"].diff().fillna(0)
    weekly["institutional_flow_z"] = _rolling_z(weekly["institutional_flow"])
    weekly["margin_change_z"] = _rolling_z(weekly["margin_change"])

    # 法人流入提高分數；融資快速增加通常代表散戶籌碼升高，因此降低分數。
    score = 50 + 12 * weekly["institutional_flow_z"] - 7 * weekly["margin_change_z"]
    weekly["position_proxy_score"] = score.clip(0, 100).round(2)
    weekly["retail_proxy_score"] = (100 - weekly["position_proxy_score"]).round(2)

    def comment(row) -> str:
        if row["position_proxy_score"] >= 70:
            return "法人流入相對偏強、融資壓力相對偏低"
        if row["position_proxy_score"] <= 30:
            return "法人流出或融資增幅相對偏高"
        return "法人與融資代理訊號中性"

    weekly["comment"] = weekly.apply(comment, axis=1)
    weekly["stock_id"] = stock_id
    weekly["source"] = "FinMind法人買賣超+融資餘額代理分數；非集保持股比例"
    weekly["date"] = weekly["date"].dt.strftime("%Y-%m-%d")
    return weekly[[
        "stock_id", "date", "institutional_flow_z", "margin_change_z",
        "position_proxy_score", "retail_proxy_score", "comment", "source",
    ]]


def main(stock_ids: list[str]) -> int:
    failures = []
    for stock_id in stock_ids:
        try:
            df = get_position_proxy(stock_id)
            if df.empty:
                print(f"⚠️ [{stock_id}] 無法建立籌碼代理分數")
                continue
            upsert_dataframe(df, "weekly_position_proxy")
            print(f"✅ [{stock_id}] 已更新 {len(df)} 週籌碼代理分數")
        except Exception as exc:
            failures.append((stock_id, str(exc)))
            print(f"❌ [{stock_id}] 籌碼代理資料失敗：{exc}")
    return 1 if failures and len(failures) == len(stock_ids) else 0


if __name__ == "__main__":
    ids = sys.argv[1:] or STOCK_LIST
    raise SystemExit(main(ids))
