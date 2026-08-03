"""以 Structured Outputs 分析近期新聞；無金鑰時使用明確標示的關鍵字備援。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

from config import DOCS_DATA_DIR, STOCK_LIST
from data_fetcher import get_stock_news
from news_analysis import classify_news_title
from openai_utils import has_openai_key, structured_json
from project_data import save_json, stock_label


def fetch_recent_news(stock_id: str, days: int = 10, limit: int = 15) -> list[dict]:
    end = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    df = get_stock_news(stock_id, start, end)
    records = []
    for idx, row in df.head(limit).reset_index(drop=True).iterrows():
        records.append({
            "id": idx + 1,
            "date": pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
            "title": str(row["title"]),
            "source": str(row.get("source") or ""),
        })
    return records


def _fallback(stock_id: str, articles: list[dict]) -> dict:
    analyses = []
    scores = []
    for article in articles:
        classified = classify_news_title(article["title"])
        score = 0.5 if classified["sentiment"] == "利多" else -0.5 if classified["sentiment"] == "利空" else 0.0
        scores.append(score)
        analyses.append({
            "id": article["id"],
            "title": article["title"],
            "score": score,
            "ai_comment": "未設定 OpenAI；使用關鍵字備援",
        })
    overall = round(sum(scores) / len(scores), 2) if scores else 0.0
    return {
        "stock_id": stock_id,
        "overall_sentiment_score": overall,
        "market_vibe_summary": "未設定 OpenAI API，以下為關鍵字法備援，不能視為深度語意分析。",
        "article_analysis": analyses,
        "analysis_method": "keyword_fallback",
    }


def analyze_news_sentiment(stock_id: str) -> dict | None:
    try:
        articles = fetch_recent_news(stock_id)
    except Exception as exc:
        print(f"⚠️ [{stock_id}] 沒有可分析新聞：{exc}")
        return None
    if not articles:
        return None

    if not has_openai_key():
        result = _fallback(stock_id, articles)
    else:
        schema = {
            "type": "object",
            "properties": {
                "stock_id": {"type": "string"},
                "overall_sentiment_score": {"type": "number", "minimum": -1, "maximum": 1},
                "market_vibe_summary": {"type": "string", "maxLength": 120},
                "article_analysis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "title": {"type": "string"},
                            "score": {"type": "number", "minimum": -1, "maximum": 1},
                            "ai_comment": {"type": "string", "maxLength": 80},
                        },
                        "required": ["id", "title", "score", "ai_comment"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["stock_id", "overall_sentiment_score", "market_vibe_summary", "article_analysis"],
            "additionalProperties": False,
        }
        system = (
            "你是台股財經新聞情緒分析師。只評估新聞對指定股票未來短期基本面與市場預期的影響。"
            "辨識否定、利多出盡、利空出盡與同時含正負資訊的標題；不要因誇張字眼直接給極端分數。"
        )
        user = f"標的：{stock_label(stock_id)}。請分析：\n{json.dumps(articles, ensure_ascii=False)}"
        result = structured_json(
            schema_name="stock_news_sentiment",
            schema=schema,
            system_prompt=system,
            user_prompt=user,
            temperature=0.15,
        )
        result["analysis_method"] = "openai_structured_output"

    result["stock_id"] = stock_id
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["overall_sentiment_score"] = round(max(-1.0, min(1.0, float(result.get("overall_sentiment_score", 0)))), 2)
    out = DOCS_DATA_DIR / f"{stock_id}_news_ai_sentiment.json"
    save_json(out, result)
    print(f"✅ [{stock_id}] 新聞情緒 {result['overall_sentiment_score']:+.2f} ({result['analysis_method']})")
    return result


def main(stock_ids: list[str]) -> int:
    failures = []
    for stock_id in stock_ids:
        try:
            analyze_news_sentiment(stock_id)
        except Exception as exc:
            failures.append(stock_id)
            print(f"❌ [{stock_id}] 新聞情緒分析失敗：{exc}")
    return 1 if failures and len(failures) == len(stock_ids) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or STOCK_LIST))
