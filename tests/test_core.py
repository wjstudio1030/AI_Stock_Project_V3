from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
import unittest
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

    def test_no_secret_file_is_packaged(self):
        self.assertFalse((ROOT / ".env").exists())
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertNotIn("sk-proj-", example)
        self.assertNotRegex(example, r'\d{8,}:[A-Za-z0-9_-]{20,}')


if __name__ == "__main__":
    unittest.main()
