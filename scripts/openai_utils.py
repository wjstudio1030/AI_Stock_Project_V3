"""OpenAI Structured Outputs 共用工具。

只有實際呼叫時才檢查金鑰，避免匯入模組就讓整條資料產線失敗。
"""

from __future__ import annotations

import json
import os
from typing import Any


from config import OPENAI_MODEL


def has_openai_key() -> bool:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return bool(key and "請在這裡填入" not in key)


def structured_json(
    *,
    schema_name: str,
    schema: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY 未設定")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("尚未安裝 openai 套件，請執行 pip install -r requirements.txt") from exc
    client = OpenAI(api_key=key)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        },
        temperature=temperature,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI 未回傳內容")
    result = json.loads(content)
    if not isinstance(result, dict):
        raise ValueError("OpenAI 回傳不是 JSON 物件")
    return result
