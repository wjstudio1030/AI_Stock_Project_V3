"""以時間順序切分驗證集，訓練每檔股票獨立的 XGBoost 模型。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import joblib
from sklearn.metrics import accuracy_score, balanced_accuracy_score, log_loss

from config import DOCS_DATA_DIR, STOCK_LIST, XGB_HOLDOUT_DAYS, XGB_MIN_TRAIN_SAMPLES
from model_features import build_training_data, load_merged_data
from xgb_model import make_classifier, model_path


def train_and_save_model(stock_id: str) -> dict:
    merged = load_merged_data(stock_id)
    X, y, aligned = build_training_data(merged)
    if len(X) < XGB_MIN_TRAIN_SAMPLES:
        raise ValueError(f"有效樣本 {len(X)} 筆，少於最低要求 {XGB_MIN_TRAIN_SAMPLES}")

    holdout = min(XGB_HOLDOUT_DAYS, max(30, int(len(X) * 0.2)))
    if len(X) - holdout < 100:
        raise ValueError("扣除驗證集後訓練樣本不足 100 筆")

    X_train, X_test = X.iloc[:-holdout], X.iloc[-holdout:]
    y_train, y_test = y.iloc[:-holdout], y.iloc[-holdout:]
    model_eval = make_classifier()
    model_eval.fit(X_train, y_train)
    pred = model_eval.predict(X_test)
    prob = model_eval.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy_pct": round(float(accuracy_score(y_test, pred) * 100), 2),
        "balanced_accuracy_pct": round(float(balanced_accuracy_score(y_test, pred) * 100), 2),
        "log_loss": round(float(log_loss(y_test, prob, labels=[0, 1])), 4),
        "holdout_days": holdout,
        "train_samples": len(X_train),
        "total_samples": len(X),
        "train_through": aligned.iloc[-holdout - 1]["date"].strftime("%Y-%m-%d"),
        "holdout_start": aligned.iloc[-holdout]["date"].strftime("%Y-%m-%d"),
        "holdout_end": aligned.iloc[-1]["date"].strftime("%Y-%m-%d"),
    }

    # 評估完成後才用全部歷史重訓部署模型；保存評估切分日期，避免把它誤稱為未見資料模型。
    final_model = make_classifier()
    final_model.fit(X, y)
    payload = {
        "model": final_model,
        "feature_names": list(X.columns),
        "stock_id": stock_id,
        "metrics": metrics,
        "trained_through": aligned.iloc[-1]["date"].strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_pipeline": "model_features.py:v1",
    }
    path = model_path(stock_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, path)

    metrics_path = DOCS_DATA_DIR / f"{stock_id}_xgb_metrics.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump({"stock_id": stock_id, **metrics, "model_path": str(path)}, f, ensure_ascii=False, indent=2)
    print(f"✅ [{stock_id}] XGBoost 已保存：{path}；時間序列驗證準確率 {metrics['accuracy_pct']}%")
    return payload


def main(stock_ids: list[str]) -> int:
    failures = []
    for stock_id in stock_ids:
        try:
            train_and_save_model(stock_id)
        except Exception as exc:
            failures.append(stock_id)
            print(f"❌ [{stock_id}] 訓練失敗：{exc}")
    return 1 if failures and len(failures) == len(stock_ids) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or STOCK_LIST))
