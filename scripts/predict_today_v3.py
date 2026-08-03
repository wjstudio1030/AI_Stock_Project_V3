"""使用每檔股票獨立模型與共用特徵管線產生最新盤後預測。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import joblib

from config import DOCS_DATA_DIR, STOCK_LIST
from model_features import latest_feature_row, load_merged_data
from xgb_model import model_path


def predict_tomorrow(stock_id: str) -> dict:
    path = model_path(stock_id)
    if not path.exists():
        raise FileNotFoundError(f"找不到模型 {path}，請先訓練")
    payload = joblib.load(path)
    if payload.get("stock_id") != stock_id:
        raise ValueError("模型股票代號與請求不一致")

    merged = load_merged_data(stock_id)
    X_latest, row = latest_feature_row(merged)
    expected = payload["feature_names"]
    missing = [name for name in expected if name not in X_latest.columns]
    if missing:
        raise ValueError(f"即時特徵缺少模型欄位：{missing}")
    X_latest = X_latest.reindex(columns=expected)
    if X_latest.isna().any().any():
        raise ValueError("最新特徵仍含缺值")

    probabilities = payload["model"].predict_proba(X_latest)[0]
    up = round(float(probabilities[1] * 100), 1)
    down = round(100.0 - up, 1)
    result = {
        "stock_id": stock_id,
        "observation_date": row["date"].strftime("%Y-%m-%d"),
        "close": round(float(row["close"]), 2),
        "up_probability": up,
        "down_probability": down,
        "model_validation": payload.get("metrics", {}),
        "model_trained_through": payload.get("trained_through"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature_snapshot": {name: round(float(X_latest.iloc[0][name]), 4) for name in expected},
    }
    out_path = DOCS_DATA_DIR / f"{stock_id}_xgb_prediction.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ [{stock_id}] {result['observation_date']} 上漲 {up}% / 下跌 {down}%")
    return result


def main(stock_ids: list[str]) -> int:
    failures = []
    for stock_id in stock_ids:
        try:
            predict_tomorrow(stock_id)
        except Exception as exc:
            failures.append(stock_id)
            print(f"❌ [{stock_id}] 預測失敗：{exc}")
    return 1 if failures and len(failures) == len(stock_ids) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or STOCK_LIST))
