"""SQLite schema、連線與可靠 upsert 工具。"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

from config import DATA_DB_DIR

DB_PATH = Path(DATA_DB_DIR) / "ai_stock.db"
_ALLOWED_TABLES = {
    "daily_price",
    "institutional_chips",
    "weekly_position_proxy",
    "dram_spot_price",
}
_SCHEMA_READY = False


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def init_database() -> None:
    """建立或升級專案需要的資料表。可重複執行。"""
    global _SCHEMA_READY
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_price (
                stock_id TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                k_val REAL,
                d_val REAL,
                ma5 REAL,
                ma10 REAL,
                ma20 REAL,
                ma60 REAL,
                PRIMARY KEY (stock_id, date)
            );

            CREATE TABLE IF NOT EXISTS institutional_chips (
                stock_id TEXT NOT NULL,
                date TEXT NOT NULL,
                foreign_net INTEGER,
                trust_net INTEGER,
                dealer_net INTEGER,
                total_net INTEGER,
                margin_balance INTEGER,
                margin_change INTEGER,
                short_balance INTEGER,
                PRIMARY KEY (stock_id, date)
            );

            CREATE TABLE IF NOT EXISTS weekly_position_proxy (
                stock_id TEXT NOT NULL,
                date TEXT NOT NULL,
                institutional_flow_z REAL,
                margin_change_z REAL,
                position_proxy_score REAL,
                retail_proxy_score REAL,
                comment TEXT,
                source TEXT,
                PRIMARY KEY (stock_id, date)
            );

            CREATE TABLE IF NOT EXISTS dram_spot_price (
                date TEXT PRIMARY KEY,
                ddr4_8gb_price REAL,
                ddr4_4gb_price REAL,
                daily_change_pct REAL,
                source TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_daily_price_date ON daily_price(date);
            CREATE INDEX IF NOT EXISTS idx_chips_date ON institutional_chips(date);
            CREATE INDEX IF NOT EXISTS idx_position_proxy_date ON weekly_position_proxy(date);
            """
        )
        # 舊版 dram_spot_price 沒有 source，且舊版程式固定產生模擬數據。
        # 升級時加欄位並移除無法證明來源的舊資料，避免繼續污染模型。
        _ensure_column(conn, "dram_spot_price", "source", "TEXT")
        conn.execute(
            "DELETE FROM dram_spot_price WHERE source IS NULL OR TRIM(source) = '' "
            "OR source IN ('legacy-unverified', 'simulated', 'trend-fit')"
        )
        conn.commit()
        _SCHEMA_READY = True
    finally:
        conn.close()


def get_db_connection() -> sqlite3.Connection:
    global _SCHEMA_READY
    if not _SCHEMA_READY:
        init_database()
    return _connect()


def _to_sql_value(value):
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def upsert_dataframe(df: pd.DataFrame, table_name: str) -> None:
    """以交易方式寫入資料，發生錯誤時回滾並向上拋出。"""
    if df.empty:
        return
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"不允許寫入資料表: {table_name}")

    conn = get_db_connection()
    try:
        table_cols = _table_columns(conn, table_name)
        unknown = set(df.columns) - table_cols
        if unknown:
            raise ValueError(f"{table_name} 不存在欄位: {sorted(unknown)}")

        columns = list(df.columns)
        placeholders = ", ".join(["?"] * len(columns))
        col_sql = ", ".join(f'"{c}"' for c in columns)
        sql = f"INSERT OR REPLACE INTO {table_name} ({col_sql}) VALUES ({placeholders})"
        rows: Iterable[tuple] = (
            tuple(_to_sql_value(v) for v in row)
            for row in df.itertuples(index=False, name=None)
        )
        with conn:
            conn.executemany(sql, rows)
        print(f"✅ 成功寫入/更新 {len(df)} 筆資料至 [{table_name}]")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
    print(f"✅ SQLite Schema 已就緒：{DB_PATH}")
