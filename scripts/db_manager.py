# scripts/db_manager.py
"""
AI Stock V3 - SQLite 資料庫總管
負責初始化資料庫、建立 Schema 結構，以及提供通用的資料庫連線與寫入工具。
"""

import sqlite3
import os
import pandas as pd

# 設定資料庫檔案路徑 (放在專案根目錄下的 data_db/ai_stock.db)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(REPO_ROOT, "data_db", "ai_stock.db")


def get_db_connection():
    """取得 SQLite 資料庫連線"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # 讓回傳的資料可以像字典一樣用欄位名稱取值
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """初始化資料庫：如果資料表不存在，就依據 Schema 建立"""
    conn = get_db_connection()
    cursor = conn.cursor()

    print(f"[{DB_PATH}] 正在檢查並建立 SQLite 資料表結構...")

    # 1. 建立日 K 線與技術指標表
    cursor.execute("""
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
    """)

    # 2. 建立三大法人與信用交易表
    cursor.execute("""
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
    """)

    # 3. 建立集保大戶籌碼週報表 (解決官方資料每週覆蓋的問題)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weekly_whales (
        stock_id TEXT NOT NULL,
        date TEXT NOT NULL,
        whale_pct REAL,       -- 大戶持股比例 (例如: 持有400張以上比例)
        retail_pct REAL,      -- 散戶持股比例 (例如: 持有50張以下比例)
        total_holders INTEGER,-- 總股東人數
        comment TEXT,         -- 籌碼面評語 (例如: 大戶增持、散戶退場)
        PRIMARY KEY (stock_id, date)
    );
    """)

    # 4. 建立 DRAM 每日現貨價格表 (南亞科專屬產業指標)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dram_spot_price (
        date TEXT PRIMARY KEY,
        ddr4_8gb_price REAL,
        ddr4_4gb_price REAL,
        daily_change_pct REAL
    );
    """)

    # 建立索引 (Index) 以加速未來 XGBoost 與 API 查詢歷史資料的順序
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_price_date ON daily_price(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chips_date ON institutional_chips(date);")

    conn.commit()
    conn.close()
    print("✅ 資料庫與 Schema 初始化成功！所有資料表皆已準備就緒。")


def upsert_dataframe(df: pd.DataFrame, table_name: str):
    """
    通用寫入工具：將 Pandas DataFrame 寫入指定的 SQLite 資料表。
    使用 'REPLACE' 邏輯，如果 (stock_id, date) 已經存在就會自動覆蓋更新，不怕重複寫入！
    """
    if df.empty:
        return
    
    conn = get_db_connection()
    try:
        # 建立臨時表來處理 SQLite 的 INSERT OR REPLACE
        temp_table = f"temp_{table_name}"
        df.to_sql(temp_table, conn, if_exists="replace", index=False)
        
        # 取得 DataFrame 的欄位名稱
        cols = ", ".join(df.columns)
        
        # 執行 INSERT OR REPLACE 寫入正式表
        sql = f"INSERT OR REPLACE INTO {table_name} ({cols}) SELECT {cols} FROM {temp_table};"
        conn.execute(sql)
        conn.execute(f"DROP TABLE {temp_table};")
        conn.commit()
        print(f"✅ 成功寫入/更新 {len(df)} 筆資料至資料表 [{table_name}]")
    except Exception as e:
        print(f"❌ 寫入 [{table_name}] 失敗：{e}")
    finally:
        conn.close()


if __name__ == "__main__":
    # 直接執行這個腳本就能建立資料庫
    init_database()