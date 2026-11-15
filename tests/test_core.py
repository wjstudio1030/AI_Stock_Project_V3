from __future__ import annotations

import json
import re
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from fetch_dram import normalize_dram_data  # noqa: E402
from news_sentiment_log import add_daily_entry  # noqa: E402
from ultimate_judge_ai_v4 import _grid_adjustment, _news_adjustment  # noqa: E402


class CoreTests(unittest.TestCase):
    def test_daily_news_entry_is_upserted(self):
        initial = [{"date": "2026-08-03", "score": -1, "total": 1}]
        summary = {"positive_count": 2, "negative_count": 0, "neutral_count": 0, "total": 2}
        result = add_daily_entry(initial, "2026-08-03", summary)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["score"], 1.0)

    def test_dram_normalization_uses_given_real_values(self):
        import pandas as pd

        raw = pd.DataFrame([
            {"date": "2026-08-01", "ddr4_8gb_price": 2.0, "source": "verified"},
            {"date": "2026-08-02", "ddr4_8gb_price": 2.1, "source": "verified"},
        ])
        result = normalize_dram_data(raw)
        self.assertEqual(result.iloc[-1]["daily_change_pct"], 5.0)
        self.assertEqual(result.iloc[-1]["source"], "verified")

    def test_fusion_adjustments_are_bounded(self):
        self.assertEqual(_news_adjustment(10), 5.0)
        self.assertEqual(_news_adjustment(-10), -5.0)
        self.assertEqual(_grid_adjustment("level_618"), 5.0)
        self.assertEqual(_grid_adjustment("unknown"), 0.0)

    def test_frontend_ids_match_javascript(self):
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")
        html_ids = set(re.findall(r'\bid="([^"]+)"', html))
        js_ids = set(re.findall(r'getElementById\("([^"]+)"\)', js))
        self.assertFalse(js_ids - html_ids, f"Missing HTML ids: {sorted(js_ids - html_ids)}")
        self.assertNotIn("../docs/data", js)

    def test_database_migrates_and_removes_unverified_legacy_dram(self):
        import db_manager

        original_path = db_manager.DB_PATH
        original_ready = db_manager._SCHEMA_READY
        with tempfile.TemporaryDirectory() as tmp:
            test_path = Path(tmp) / "legacy.db"
            conn = sqlite3.connect(test_path)
            conn.execute("CREATE TABLE dram_spot_price (date TEXT PRIMARY KEY, ddr4_8gb_price REAL, ddr4_4gb_price REAL, daily_change_pct REAL)")
            conn.execute("INSERT INTO dram_spot_price VALUES ('2026-01-01', 1.75, 1.0, 0.0)")
            conn.commit()
            conn.close()
            try:
                db_manager.DB_PATH = test_path
                db_manager._SCHEMA_READY = False
                db_manager.init_database()
                conn = sqlite3.connect(test_path)
                columns = [row[1] for row in conn.execute("PRAGMA table_info(dram_spot_price)")]
                count = conn.execute("SELECT COUNT(*) FROM dram_spot_price").fetchone()[0]
                conn.close()
                self.assertIn("source", columns)
                self.assertEqual(count, 0)
            finally:
                db_manager.DB_PATH = original_path
                db_manager._SCHEMA_READY = original_ready

    def test_default_manifest_contains_exactly_the_requested_twenty_stocks(self):
        from config import STOCK_LIST

        expected = "2330,2454,2317,2308,3711,1303,2881,2882,2891,2383,2408,3037,2412,2303,3017,3443,2382,2887,2885,6669".split(",")
        manifest = json.loads((ROOT / "docs" / "data" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(STOCK_LIST, expected)
        self.assertEqual(manifest["stocks"], expected)
        self.assertEqual(len(set(manifest["stocks"])), 20)

    def test_finmind_quota_breaker_does_not_repeat_requests(self):
        import data_fetcher

        response = MagicMock(status_code=402)
        with patch.object(data_fetcher, "_FINMIND_QUOTA_EXHAUSTED", False), patch.object(data_fetcher._SESSION, "get", return_value=response) as request:
            with self.assertRaises(data_fetcher.FinMindQuotaExceeded):
                data_fetcher._request({"dataset": "TaiwanStockInfo"})
            with self.assertRaises(data_fetcher.FinMindQuotaExceeded):
                data_fetcher._request({"dataset": "TaiwanStockPrice", "data_id": "2330"})
            self.assertEqual(request.call_count, 1)

    def test_yahoo_daily_price_fallback_normalizes_ohlcv(self):
        import pandas as pd
        import data_fetcher

        history = pd.DataFrame(
            {"Open": [100, 102], "High": [104, 105], "Low": [98, 100],
             "Close": [103, 104], "Volume": [10000, 12000]},
            index=pd.date_range("2026-11-12", periods=2, tz="Asia/Taipei"),
        )
        yahoo_ticker = MagicMock()
        yahoo_ticker.history.return_value = history
        with patch.object(data_fetcher, "_fetch", side_effect=data_fetcher.FinMindQuotaExceeded("quota")):
            with patch("yfinance.Ticker", return_value=yahoo_ticker) as yf_ticker:
                frame = data_fetcher.get_stock_price("2330", "2026-11-01", "2026-11-13")
        self.assertEqual(yf_ticker.call_args.args[0], "2330.TW")
        self.assertEqual(len(frame), 2)
        self.assertEqual(list(frame.columns), ["date", "open", "high", "low", "close", "volume"])
        self.assertEqual(frame["date"].dt.strftime("%Y-%m-%d").iloc[0], "2026-11-12")
        self.assertEqual(frame["close"].iloc[-1], 104)
        self.assertIn("Yahoo Finance", frame.attrs["source"])

    def test_no_secret_file_is_packaged(self):
        self.assertFalse((ROOT / ".env").exists())
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertNotIn("sk-proj-", example)
        self.assertNotRegex(example, r'\d{8,}:[A-Za-z0-9_-]{20,}')


if __name__ == "__main__":
    unittest.main()
