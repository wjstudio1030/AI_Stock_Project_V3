"""匯入真實 DRAM 現貨價格。

本模組不再生成任何隨機或擬合資料。資料來源可為：
1. DRAM_DATA_URL：公開或授權 CSV URL
2. DRAM_DATA_PATH：本機 CSV
3. DRAM_LATEST_DATE + DRAM_LATEST_8GB_PRICE（可選 4GB）單日真實報價

CSV 必須至少包含 date、ddr4_8gb_price；可包含 ddr4_4gb_price、source。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from config import (
    DRAM_DATA_PATH,
    DRAM_DATA_SOURCE,
    DRAM_DATA_URL,
    DRAM_LATEST_4GB_PRICE,
    DRAM_LATEST_8GB_PRICE,
    DRAM_LATEST_DATE,
)
from db_manager import get_db_connection, upsert_dataframe


def _load_raw() -> pd.DataFrame:
    if DRAM_DATA_URL:
        print("📡 從設定的 CSV URL 匯入真實 DRAM 報價")
        return pd.read_csv(DRAM_DATA_URL)
    if DRAM_DATA_PATH:
        path = Path(DRAM_DATA_PATH).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"DRAM_DATA_PATH 不存在：{path}")
        print(f"📄 從本機 CSV 匯入真實 DRAM 報價：{path}")
        return pd.read_csv(path)
    if DRAM_LATEST_DATE and DRAM_LATEST_8GB_PRICE:
        return pd.DataFrame(
            [{
                "date": DRAM_LATEST_DATE,
                "ddr4_8gb_price": DRAM_LATEST_8GB_PRICE,
                "ddr4_4gb_price": DRAM_LATEST_4GB_PRICE or None,
                "source": DRAM_DATA_SOURCE,
            }]
        )
    return pd.DataFrame()


def normalize_dram_data(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return raw
    required = {"date", "ddr4_8gb_price"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"DRAM CSV 缺少必要欄位：{sorted(missing)}")

    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["ddr4_8gb_price"] = pd.to_numeric(df["ddr4_8gb_price"], errors="coerce")
    if "ddr4_4gb_price" not in df:
        df["ddr4_4gb_price"] = None
    df["ddr4_4gb_price"] = pd.to_numeric(df["ddr4_4gb_price"], errors="coerce")
    if "source" not in df:
        df["source"] = DRAM_DATA_SOURCE
    df["source"] = df["source"].replace(r"^\s*$", pd.NA, regex=True).fillna(DRAM_DATA_SOURCE).astype(str)
    df = df.dropna(subset=["date", "ddr4_8gb_price"]).sort_values("date").drop_duplicates("date", keep="last")
    if df.empty:
        raise ValueError("DRAM 資料清理後沒有有效報價")
    if (df["ddr4_8gb_price"] <= 0).any():
        raise ValueError("DRAM 報價必須大於 0")
    df["daily_change_pct"] = df["ddr4_8gb_price"].pct_change() * 100
    df["daily_change_pct"] = df["daily_change_pct"].fillna(0).round(4)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df[["date", "ddr4_8gb_price", "ddr4_4gb_price", "daily_change_pct", "source"]]


def main() -> int:
    raw = _load_raw()
    if raw.empty:
        print("ℹ️ 未設定真實 DRAM 資料來源；不產生模擬資料，也不覆寫既有資料。")
        return 0
    df = normalize_dram_data(raw)
    # 單日報價以資料庫前一筆真實價格計算漲跌，不把每日變動誤設為 0。
    if len(df) == 1:
        conn = get_db_connection()
        try:
            previous = pd.read_sql_query(
                "SELECT ddr4_8gb_price FROM dram_spot_price WHERE date < ? "
                "ORDER BY date DESC LIMIT 1",
                conn,
                params=(df.iloc[0]["date"],),
            )
        finally:
            conn.close()
        if not previous.empty:
            prev = float(previous.iloc[0]["ddr4_8gb_price"])
            current = float(df.iloc[0]["ddr4_8gb_price"])
            df.loc[df.index[0], "daily_change_pct"] = round((current / prev - 1) * 100, 4)
    upsert_dataframe(df, "dram_spot_price")
    print(f"✅ 已匯入 {len(df)} 筆真實 DRAM 報價")
    return 0


if __name__ == "__main__":
    sys.exit(main())
