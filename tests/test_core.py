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

    def test_site_uses_wj_stock_lab_branding(self):
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "docs" / "style.css").read_text(encoding="utf-8")
        self.assertIn("<title>WJ Stock Lab | WJ Studio</title>", html)
        self.assertIn("Designed &amp; Developed by <strong>WJ Studio</strong>", html)
        self.assertIn('class="brand-lockup"', html)
        self.assertIn('class="brand-logo"', html)
        self.assertIn('src="./logo.png"', html)
        # The favicon may add a cache-busting query string, but must load the real logo.
        self.assertRegex(html, r'<link\s+rel="icon"[^>]*href="\./logo\.png(?:\?[^"]*)?"')
        self.assertTrue((ROOT / "docs" / "logo.png").is_file())
        self.assertIn(".brand-logo[hidden]", css)
        self.assertIn("WJ × SAM COLLABORATIVE PROJECT", html)
        self.assertNotIn("MARKET INTELLIGENCE", html)
        self.assertNotIn("brand-emblem", html)
        self.assertNotIn("INDEPENDENT RESEARCH PROJECT", html)
        self.assertNotIn("<h1>AI Stock</h1>", html)

    def test_global_manifest_keeps_known_stocks_when_quote_provider_is_unavailable(self):
        import build_global_data

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(
                json.dumps({
                    "stocks": ["2330"],
                    "global_stocks": ["^TWII", "^SOX"],
                    "global_updated_at": "2026-11-15T00:00:00+00:00",
                }), encoding="utf-8",
            )
            with patch.object(build_global_data, "OUTPUT_DIR_ABS", tmp):
                build_global_data.update_manifest([])
            result = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(result["stocks"], ["2330"])
            self.assertEqual(result["global_stocks"], ["^TWII", "^SOX"])
            self.assertEqual(result["global_updated_at"], "2026-11-15T00:00:00+00:00")
            self.assertIn("^TWII", result["global_failed_stocks"])

    def test_frontend_staleness_uses_actual_quote_day(self):
        js = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")
        self.assertIn("renderStaleWarning(data.updated_at, data.finmind_quota_exhausted, data.price_as_of, data.retained_section_dates)", js)
        self.assertIn("priceAsOf", js)

    def test_news_analysis_reuses_snapshot_without_refetching_finmind(self):
        import news_sentiment_ai_v3
        from datetime import datetime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            today = datetime.today().strftime("%Y-%m-%d")
            (root / "2330.json").write_text(
                json.dumps({"news": {"articles": [
                    {"date": today + " 11:08", "title": "台積電測試新聞", "source": "verified test"},
                ]}}, ensure_ascii=False), encoding="utf-8",
            )
            with patch.object(news_sentiment_ai_v3, "DOCS_DATA_DIR", root):
                with patch.object(news_sentiment_ai_v3, "get_stock_news", side_effect=AssertionError("must reuse cache")):
                    articles = news_sentiment_ai_v3.fetch_recent_news("2330", days=7)
            self.assertEqual(len(articles), 1)
            self.assertEqual(articles[0]["title"], "台積電測試新聞")

    def test_news_analysis_does_not_retry_empty_cached_news(self):
        import news_sentiment_ai_v3

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "2330.json").write_text(
                json.dumps({"news": {"articles": []}}), encoding="utf-8",
            )
            with patch.object(news_sentiment_ai_v3, "DOCS_DATA_DIR", root):
                with patch.object(news_sentiment_ai_v3, "get_stock_news", side_effect=AssertionError("must not refetch")):
                    self.assertEqual(news_sentiment_ai_v3.fetch_recent_news("2330"), [])

    def test_pipeline_commits_base_market_data_before_optional_ai(self):
        workflow = (ROOT / ".github" / "workflows" / "update_data.yml").read_text(encoding="utf-8")
        self.assertIn("Commit base market data before optional analyses", workflow)
        self.assertLess(workflow.index("Commit base market data before optional analyses"),
                        workflow.index("Generate structured news sentiment reports"))

    def test_openai_failure_does_not_block_keyword_news_summary(self):
        import news_sentiment_ai_v3

        article = [{"id": 1, "date": "2026-11-17", "title": "公司公布新訂單", "source": "test"}]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(news_sentiment_ai_v3, "DOCS_DATA_DIR", Path(tmp)):
                with patch.object(news_sentiment_ai_v3, "fetch_recent_news", return_value=article):
                    with patch.object(news_sentiment_ai_v3, "has_openai_key", return_value=True):
                        with patch.object(news_sentiment_ai_v3, "structured_json", side_effect=TimeoutError("test")):
                            report = news_sentiment_ai_v3.analyze_news_sentiment("2330")
            self.assertEqual(report["analysis_method"], "keyword_fallback_api_error")
            self.assertIn("關鍵字", report["market_vibe_summary"])
            self.assertTrue((Path(tmp) / "2330_news_ai_sentiment.json").exists())

    def test_openai_failure_does_not_block_quant_summary(self):
        import ai_analyst_v3

        input_data = {"XGBoost上漲機率": 51.0, "外資買賣超張": 0,
                      "DRAM單日漲跌%": 0.0, "觀測日期": "2026-11-17", "股票": "2330"}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_analyst_v3, "DOCS_DATA_DIR", Path(tmp)):
                with patch.object(ai_analyst_v3, "get_latest_quant_data", return_value=input_data):
                    with patch.object(ai_analyst_v3, "has_openai_key", return_value=True):
                        with patch.object(ai_analyst_v3, "structured_json", side_effect=TimeoutError("test")):
                            result = ai_analyst_v3.generate_ai_report("2330")
            self.assertEqual(result["analysis_method"], "deterministic_fallback_api_error")
            self.assertTrue((Path(tmp) / "2330_ai_report.json").exists())

    def test_quota_retains_last_known_nonprice_data_with_provenance(self):
        from data_retention import retain_optional_sections

        previous = {
            "updated_at": "2026-11-17T05:00:00+00:00",
            "overview": {"close": 100.0, "per": 12.0, "foreign_net_today": 500, "news_positive": 2},
            "institutional": {"total_net": [{"time": "2026-11-17", "value": 500}]},
            "margin": {"margin_balance": [{"time": "2026-11-17", "value": 1}]},
            "valuation": {"PER": [{"time": "2026-11-17", "value": 12}]},
            "fundamentals": {"quarters": [{"date": "2026-09-30", "eps": 3.0}]},
            "news": {"articles": [{"date": "2026-11-17", "title": "verified"}], "total": 1},
        }
        current = {
            "price_as_of": "2026-11-18",
            "price": [{"time": "2026-11-18", "close": 105}],
            "overview": {"close": 105.0, "per": None, "foreign_net_today": None, "news_positive": 0},
            "institutional": {"total_net": []},
            "margin": {"margin_balance": []},
            "valuation": {"PER": []},
            "fundamentals": {"quarters": []},
            "news": {"articles": [], "total": 0},
        }
        result = retain_optional_sections(current, previous, provider_unavailable=True)
        self.assertEqual(result["price_as_of"], "2026-11-18")
        self.assertEqual(result["overview"]["close"], 105.0)
        self.assertEqual(result["overview"]["per"], 12.0)
        self.assertEqual(result["overview"]["foreign_net_today"], 500)
        self.assertEqual(result["overview"]["news_positive"], 2)
        self.assertEqual(set(result["retained_section_dates"]),
                         {"institutional", "margin", "valuation", "fundamentals", "news"})
        self.assertEqual(result["retained_section_dates"]["news"], previous["updated_at"])
        self.assertEqual(current["news"]["total"], 0)  # input must not be mutated

    def test_retained_section_provenance_does_not_become_false_new_date(self):
        from data_retention import retain_optional_sections

        previous = {
            "updated_at": "2026-11-18T10:00:00+00:00",
            "retained_section_dates": {"news": "2026-11-14T10:00:00+00:00"},
            "news": {"articles": [{"title": "older verified"}]},
            "overview": {"news_positive": 1},
        }
        current = {"price_as_of": "2026-11-18", "news": {"articles": []}, "overview": {"news_positive": 0}}
        result = retain_optional_sections(current, previous, provider_unavailable=True)
        self.assertEqual(result["retained_section_dates"]["news"], "2026-11-14T10:00:00+00:00")

    def test_frontend_identifies_reused_fundamental_data(self):
        js = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")
        self.assertIn("data.retained_section_dates", js)

    def test_no_secret_file_is_packaged(self):
        self.assertFalse((ROOT / ".env").exists())
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertNotIn("sk-proj-", example)
        self.assertNotRegex(example, r'\d{8,}:[A-Za-z0-9_-]{20,}')


if __name__ == "__main__":
    unittest.main()
