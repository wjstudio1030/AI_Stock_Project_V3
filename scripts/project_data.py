"""讀寫前端 JSON 與股票顯示名稱的共用工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import DOCS_DATA_DIR


def json_path(stock_id: str, suffix: str) -> Path:
    return Path(DOCS_DATA_DIR) / f"{stock_id}_{suffix}.json"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp.replace(path)


def stock_name(stock_id: str) -> str:
    data = load_json(Path(DOCS_DATA_DIR) / f"{stock_id}.json", {}) or {}
    return data.get("stock_name") or stock_id


def stock_label(stock_id: str) -> str:
    name = stock_name(stock_id)
    return f"{stock_id} {name}" if name != stock_id else stock_id
