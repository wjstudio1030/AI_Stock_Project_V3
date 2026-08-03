"""使用最新量化資料產生結構化白話報告；不自行重新計算模型特徵。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pandas as pd

from config import DOCS_DATA_DIR, STOCK_LIST
from db_manager import get_db_connection
from openai_utils import has_openai_key, structured_json
from project_data import load_json, save_json, stock_label


def get_latest_quant_data(stock_id: str) -> dict:
    prediction = load_json(DOCS_DATA_DIR / f"{stock_id}_xgb_prediction.json", {}) or {}
    if not prediction:
        raise FileNotFoundError("缺少 XGBoost 預測 JSON，請先執行 predict_today_v3.py")

    conn = get_db_connection()
    try:
        price = pd.read_sql_query(
            "SELECT * FROM daily_price WHERE stock_id = ? ORDER BY date DESC LIMIT 1",
            conn,
            params=(stock_id,),
        )
        chips = pd.read_sql_query(
            "SELECT * FROM institutional_chips WHERE stock_id = ? ORDER BY date DESC LIMIT 1",
            conn,
            params=(stock_id,),
        )
        proxy = pd.read_sql_query(
            "SELECT * FROM weekly_position_proxy WHERE stock_id = ? ORDER BY date DESC LIMIT 1",
            conn,
            params=(stock_id,),
        )
        dram = pd.read_sql_query("SELECT * FROM dram_spot_price ORDER BY date DESC LIMIT 1", conn)
    finally:
        conn.close()
    if price.empty:
        raise ValueError("資料庫沒有最新股價")

    p = price.iloc[0]
    c = chips.iloc[0] if not chips.empty else {}
    w = proxy.iloc[0] if not proxy.empty else {}
    d = dram.iloc[0] if not dram.empty else {}
    ma20 = float(p.get("ma20") or 0)
    bias = ((float(p["close"]) - ma20) / ma20 * 100) if ma20 else 0.0
    return {
        "觀測日期": str(p["date"]),
        "股票": stock_label(stock_id),
        "最新收盤價": float(p["close"]),
        "XGBoost上漲機率": float(prediction["up_probability"]),
        "時間序列驗證準確率": prediction.get("model_validation", {}).get("accuracy_pct"),
        "KD_K": round(float(p.get("k_val") or 0), 2),
        "月線乖離率%": round(bias, 2),
        "外資買賣超張": int(c.get("foreign_net", 0) or 0),
        "投信買賣超張": int(c.get("trust_net", 0) or 0),
        "籌碼代理分數": float(w.get("position_proxy_score", 0) or 0),
        "籌碼代理說明": "0~100 相對分數，非集保持股比例",
        "DRAM單日漲跌%": float(d.get("daily_change_pct", 0) or 0),
        "DRAM資料來源": str(d.get("source", "未提供真實來源")) if len(d) else "未提供真實來源",
    }


def _fallback(data: dict) -> dict:
    up = float(data["XGBoost上漲機率"])
    foreign = int(data["外資買賣超張"])
    dram = float(data["DRAM單日漲跌%"])
    if up >= 60:
        rating = "⭐⭐⭐⭐ 偏多觀察"
    elif up <= 40:
        rating = "⭐⭐ 偏空謹慎"
    else:
        rating = "⭐⭐⭐ 區間觀察"
    return {
        "date": data["觀測日期"],
        "stock": data["股票"],
        "trend_rating": rating,
        "quant_summary": f"模型上漲機率 {up:.1f}%，外資 {foreign:+,} 張，DRAM {dram:+.2f}%。",
        "action_advice": "依風險承受度分批處理，勿把單日機率當成保證。",
        "risk_warning": "模型驗證樣本有限，且外部資料可能缺漏。",
        "analysis_method": "deterministic_fallback",
    }


def generate_ai_report(stock_id: str) -> dict:
    data = get_latest_quant_data(stock_id)
    if not has_openai_key():
        result = _fallback(data)
    else:
        schema = {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "stock": {"type": "string"},
                "trend_rating": {"type": "string", "maxLength": 40},
                "quant_summary": {"type": "string", "maxLength": 180},
                "action_advice": {"type": "string", "maxLength": 100},
                "risk_warning": {"type": "string", "maxLength": 100},
            },
            "required": ["date", "stock", "trend_rating", "quant_summary", "action_advice", "risk_warning"],
            "additionalProperties": False,
        }
        result = structured_json(
            schema_name="stock_quant_report",
            schema=schema,
            system_prompt=(
                "你是台股量化研究報告編輯。只能解讀輸入數值，不得創造不存在的資料，"
                "不得把驗證準確率稱為未來保證，也不得提供保證獲利或命令式投資建議。"
            ),
            user_prompt=json.dumps(data, ensure_ascii=False),
            temperature=0.2,
        )
        result["analysis_method"] = "openai_structured_output"

    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    out = DOCS_DATA_DIR / f"{stock_id}_ai_report.json"
    save_json(out, result)
    print(f"✅ [{stock_id}] 量化早報已產生 ({result['analysis_method']})")
    return result


def main(stock_ids: list[str]) -> int:
    failures = []
    for stock_id in stock_ids:
        try:
            generate_ai_report(stock_id)
        except Exception as exc:
            failures.append(stock_id)
            print(f"❌ [{stock_id}] 量化早報失敗：{exc}")
    return 1 if failures and len(failures) == len(stock_ids) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or STOCK_LIST))
