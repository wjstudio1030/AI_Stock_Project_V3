"""AI Stock 專案集中設定。

所有憑證與部署差異都由環境變數提供；程式庫中不保存任何金鑰。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
load_dotenv(REPO_ROOT / ".env")
DOCS_DATA_DIR = REPO_ROOT / "docs" / "data"
DATA_DB_DIR = REPO_ROOT / "data_db"
MODEL_DIR = DATA_DB_DIR / "models"

FINMIND_API_URL = os.getenv("FINMIND_API_URL", "https://api.finmindtrade.com/api/v4/data")
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


STOCK_LIST = _csv_env("STOCK_LIST", "2408,2344,2337,4973,6770")
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "250"))
RSI_PERIODS = [6, 14]
MA_WINDOWS = [5, 10, 20, 60]
FUNDAMENTALS_QUARTERS = int(os.getenv("FUNDAMENTALS_QUARTERS", "8"))
ANALYSIS_LOOKBACK_YEARS = float(os.getenv("ANALYSIS_LOOKBACK_YEARS", "5"))
ANALYSIS_MIN_SAMPLE = int(os.getenv("ANALYSIS_MIN_SAMPLE", "20"))
NEWS_LOOKBACK_DAYS = int(os.getenv("NEWS_LOOKBACK_DAYS", "7"))
NEWS_TODAY_MAX_ARTICLES = int(os.getenv("NEWS_TODAY_MAX_ARTICLES", "10"))
NEWS_MAX_ARTICLES = int(os.getenv("NEWS_MAX_ARTICLES", "30"))
TRACK_RECORD_MAX_ENTRIES = int(os.getenv("TRACK_RECORD_MAX_ENTRIES", "180"))
NEWS_SENTIMENT_LOG_MAX_ENTRIES = int(os.getenv("NEWS_SENTIMENT_LOG_MAX_ENTRIES", "1000"))
NEWS_SENTIMENT_MIN_FOR_ML = int(os.getenv("NEWS_SENTIMENT_MIN_FOR_ML", "250"))
ANOMALY_STREAK_THRESHOLD = int(os.getenv("ANOMALY_STREAK_THRESHOLD", "3"))
OUTPUT_DIR = "docs/data"

# XGBoost
XGB_MIN_TRAIN_SAMPLES = int(os.getenv("XGB_MIN_TRAIN_SAMPLES", "200"))
XGB_HOLDOUT_DAYS = int(os.getenv("XGB_HOLDOUT_DAYS", "60"))
XGB_SIGNAL_THRESHOLD = float(os.getenv("XGB_SIGNAL_THRESHOLD", "0.65"))

# 回測與交易摩擦
TAX_RATE = float(os.getenv("TAX_RATE", "0.003"))
FEE_RATE = float(os.getenv("FEE_RATE", "0.001425"))
HOLD_DAYS = int(os.getenv("HOLD_DAYS", "5"))

# 風險警報採標準化異常，不使用對所有股票都不合理的固定張數門檻。
ALERT_FOREIGN_Z = float(os.getenv("ALERT_FOREIGN_Z", "-2.5"))
ALERT_TOTAL_Z = float(os.getenv("ALERT_TOTAL_Z", "-2.5"))
ALERT_NEWS_SCORE = float(os.getenv("ALERT_NEWS_SCORE", "-0.6"))

# DRAM 不再產生模擬價格。需提供真實 CSV URL、CSV 路徑，或單日真實報價。
DRAM_DATA_URL = os.getenv("DRAM_DATA_URL", "").strip()
DRAM_DATA_PATH = os.getenv("DRAM_DATA_PATH", "").strip()
DRAM_LATEST_DATE = os.getenv("DRAM_LATEST_DATE", "").strip()
DRAM_LATEST_8GB_PRICE = os.getenv("DRAM_LATEST_8GB_PRICE", "").strip()
DRAM_LATEST_4GB_PRICE = os.getenv("DRAM_LATEST_4GB_PRICE", "").strip()
DRAM_DATA_SOURCE = os.getenv("DRAM_DATA_SOURCE", "user-configured real source").strip()

for directory in (DOCS_DATA_DIR, DATA_DB_DIR, MODEL_DIR):
    directory.mkdir(parents=True, exist_ok=True)
