"""確定性訊號融合器。

最終機率由明確公式計算，語言模型不參與數字加權；輸出會驗證 0~100 且上下相加為 100。
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from config import DOCS_DATA_DIR, STOCK_LIST
from project_data import load_json, save_json


def _news_adjustment(score: float) -> float:
    return max(-5.0, min(5.0, score * 5.0))


def _grid_adjustment(hit_level: str) -> float:
    return {"none": -2.0, "level_382": 2.0, "level_500": 4.0, "level_618": 5.0}.get(hit_level, 0.0)


def run_ultimate_judge(stock_id: str) -> dict:
    xgb = load_json(DOCS_DATA_DIR / f"{stock_id}_xgb_prediction.json", {}) or {}
    if "up_probability" not in xgb:
        raise FileNotFoundError("缺少可驗證的 XGBoost 數值預測")
    news = load_json(DOCS_DATA_DIR / f"{stock_id}_news_ai_sentiment.json", {}) or {}
    grid = load_json(DOCS_DATA_DIR / f"{stock_id}_grid_strategy.json", {}) or {}
    risk = load_json(DOCS_DATA_DIR / f"{stock_id}_risk_alert.json", {}) or {}

    base = float(xgb["up_probability"])
    news_score = float(news.get("overall_sentiment_score", 0.0))
    news_adj = _news_adjustment(news_score)
    grid_adj = _grid_adjustment(str(grid.get("hit_level", "unknown")))
    risk_adjustment = -5.0 if risk.get("triggered") else 0.0
    raw = base + news_adj + grid_adj + risk_adjustment
    cap_applied = False
    if risk.get("triggered") and news_score <= -0.6:
        raw = min(raw, 30.0)
        cap_applied = True
    up = round(max(1.0, min(99.0, raw)), 1)
    down = round(100.0 - up, 1)
    if round(up + down, 1) != 100.0:
        down = round(100.0 - up, 1)

    logic_parts = [
        f"XGBoost 基準 {base:.1f}%",
        f"新聞調整 {news_adj:+.1f}%",
        f"網格調整 {grid_adj:+.1f}%",
        f"風險警報調整 {risk_adjustment:+.1f}%",
    ]
    if cap_applied:
        logic_parts.append("極端負面風險上限 30%")
    result = {
        "stock_id": stock_id,
        "observation_date": xgb.get("observation_date"),
        "ultimate_up_probability": up,
        "ultimate_down_probability": down,
        "adjustment_logic": "；".join(logic_parts),
        "components": {
            "xgb_base_probability": base,
            "news_sentiment_score": news_score,
            "news_adjustment": news_adj,
            "grid_hit_level": grid.get("hit_level", "unknown"),
            "grid_adjustment": grid_adj,
            "risk_adjustment": risk_adjustment,
            "risk_cap_applied": cap_applied,
        },
        "calculation_method": "deterministic_weighted_fusion_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_json(DOCS_DATA_DIR / f"{stock_id}_ultimate_judge.json", result)
    print(f"✅ [{stock_id}] 最終上漲機率 {up:.1f}% / 下跌 {down:.1f}%")
    return result


def main(stock_ids: list[str]) -> int:
    failures = []
    for stock_id in stock_ids:
        try:
            run_ultimate_judge(stock_id)
        except Exception as exc:
            failures.append(stock_id)
            print(f"❌ [{stock_id}] 最終融合失敗：{exc}")
    return 1 if failures and len(failures) == len(stock_ids) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or STOCK_LIST))
