"""XGBoost 模型定義與每檔股票模型路徑。"""

from __future__ import annotations

from pathlib import Path

import xgboost as xgb

from config import MODEL_DIR


def model_path(stock_id: str) -> Path:
    safe_id = "".join(ch for ch in stock_id if ch.isalnum() or ch in {"-", "_"})
    if not safe_id:
        raise ValueError("股票代號不合法")
    return Path(MODEL_DIR) / f"xgb_{safe_id}.pkl"


def make_classifier(random_state: int = 42) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=180,
        max_depth=3,
        learning_rate=0.03,
        min_child_weight=4,
        gamma=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.05,
        reg_lambda=1.2,
        random_state=random_state,
        eval_metric="logloss",
        n_jobs=2,
    )
