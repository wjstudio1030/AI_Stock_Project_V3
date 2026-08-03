"""XGBoost 訓練、即時預測與回測共用的唯一特徵管線。

共用同一份實作可避免 train/serve skew，例如訓練時計算 ret_3d，預測時卻填 0。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from db_manager import get_db_connection

FEATURE_MAP = {
    "k_val": "1.技術_KD值(K)",
    "d_val": "2.技術_KD值(D)",
    "bias_ma20": "3.技術_月線乖離率%",
    "ret_3d": "4.技術_近3日動能%",
    "foreign_net": "5.籌碼_外資買賣超(張)",
    "trust_net": "6.籌碼_投信買賣超(張)",
    "margin_change": "7.散戶_融資增減(張)",
    "position_proxy_score": "8.籌碼_大戶代理分數",
    "dram_change_pct": "9.產業_DRAM現貨單日漲跌%",
    "position_proxy_available": "10.大戶代理資料可用",
    "dram_available": "11.DRAM真實資料可用",
}


def _read_sql(conn, sql: str, params: tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, params=params)


def load_merged_data(stock_id: str) -> pd.DataFrame:
    conn = get_db_connection()
    try:
        price = _read_sql(
            conn,
            "SELECT * FROM daily_price WHERE stock_id = ? ORDER BY date",
            (stock_id,),
        )
        chips = _read_sql(
            conn,
            "SELECT * FROM institutional_chips WHERE stock_id = ? ORDER BY date",
            (stock_id,),
        )
        proxy = _read_sql(
            conn,
            "SELECT * FROM weekly_position_proxy WHERE stock_id = ? ORDER BY date",
            (stock_id,),
        )
        dram = _read_sql(conn, "SELECT * FROM dram_spot_price ORDER BY date")
    finally:
        conn.close()

    if price.empty:
        raise ValueError(f"資料庫中找不到 [{stock_id}] 的 K 線資料")

    for frame in (price, chips, proxy, dram):
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame.dropna(subset=["date"], inplace=True)
            frame.sort_values("date", inplace=True)

    work = price.copy()

    if chips.empty:
        for col in ("foreign_net", "trust_net", "dealer_net", "total_net", "margin_change"):
            work[col] = 0.0
    else:
        chip_cols = [
            "date", "foreign_net", "trust_net", "dealer_net", "total_net", "margin_change"
        ]
        work = work.merge(chips[chip_cols], on="date", how="left")
        work[[c for c in chip_cols if c != "date"]] = work[
            [c for c in chip_cols if c != "date"]
        ].fillna(0)

    if proxy.empty:
        work["position_proxy_score"] = 0.0
        work["position_proxy_available"] = 0.0
    else:
        proxy_small = proxy[["date", "position_proxy_score"]].drop_duplicates("date")
        work = pd.merge_asof(
            work.sort_values("date"),
            proxy_small.sort_values("date"),
            on="date",
            direction="backward",
            tolerance=pd.Timedelta(days=14),
        )
        work["position_proxy_available"] = work["position_proxy_score"].notna().astype(float)
        work["position_proxy_score"] = work["position_proxy_score"].fillna(0.0)

    if dram.empty:
        work["dram_change_pct"] = 0.0
        work["dram_available"] = 0.0
    else:
        dram_small = dram[["date", "daily_change_pct"]].drop_duplicates("date").rename(
            columns={"daily_change_pct": "dram_change_pct"}
        )
        work = pd.merge_asof(
            work.sort_values("date"),
            dram_small.sort_values("date"),
            on="date",
            direction="backward",
            tolerance=pd.Timedelta(days=7),
        )
        work["dram_available"] = work["dram_change_pct"].notna().astype(float)
        work["dram_change_pct"] = work["dram_change_pct"].fillna(0.0)

    work["ma20"] = pd.to_numeric(work["ma20"], errors="coerce").replace(0, np.nan)
    work["bias_ma20"] = ((work["close"] - work["ma20"]) / work["ma20"]) * 100
    work["ret_3d"] = pd.to_numeric(work["close"], errors="coerce").pct_change(3) * 100
    work = work.replace([np.inf, -np.inf], np.nan)
    return work.sort_values("date").reset_index(drop=True)


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    missing = [col for col in FEATURE_MAP if col not in df.columns]
    if missing:
        raise ValueError(f"特徵來源缺少欄位: {missing}")
    X = df[list(FEATURE_MAP)].apply(pd.to_numeric, errors="coerce")
    X = X.rename(columns=FEATURE_MAP)
    return X


def build_training_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    X = build_feature_frame(df)
    y = (df["close"].shift(-1) > df["close"]).astype(float)
    y[df["close"].shift(-1).isna()] = np.nan
    valid = X.notna().all(axis=1) & y.notna()
    return X.loc[valid].reset_index(drop=True), y.loc[valid].astype(int).reset_index(drop=True), df.loc[valid].reset_index(drop=True)


def latest_feature_row(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = build_feature_frame(df)
    valid = X.notna().all(axis=1)
    if not valid.any():
        raise ValueError("沒有任何完整特徵列可供預測")
    idx = valid[valid].index[-1]
    return X.loc[[idx]].reset_index(drop=True), df.loc[idx]
