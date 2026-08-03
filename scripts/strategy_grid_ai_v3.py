"""確定性波段回吐網格策略，不讓語言模型改寫數字或觸發狀態。"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import pandas as pd

from config import DOCS_DATA_DIR, STOCK_LIST
from db_manager import get_db_connection
from project_data import load_json, save_json, stock_label


def calculate_wave_grid(stock_id: str, lookback_days: int = 120) -> dict:
    conn = get_db_connection()
    try:
        df = pd.read_sql_query(
            "SELECT date, close FROM daily_price WHERE stock_id = ? ORDER BY date DESC LIMIT ?",
            conn,
            params=(stock_id, lookback_days),
        )
    finally:
        conn.close()
    if df.empty or len(df) < 20:
        raise ValueError("K 線資料不足")
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna().sort_values("date").reset_index(drop=True)

    # 找出「低點先出現、其後才有高點」的正向波段。
    best = None
    running_min_price = float(df.iloc[0]["close"])
    running_min_idx = 0
    for idx in range(1, len(df)):
        price = float(df.iloc[idx]["close"])
        gain = price - running_min_price
        if best is None or gain > best[0]:
            best = (gain, running_min_idx, idx)
        if price < running_min_price:
            running_min_price = price
            running_min_idx = idx
    if best is None or best[0] <= 0:
        raise ValueError("期間內沒有可辨識的正向波段")
    _, start_idx, peak_idx = best
    p_start = float(df.iloc[start_idx]["close"])
    p_peak = float(df.iloc[peak_idx]["close"])
    delta = p_peak - p_start

    current = float(df.iloc[-1]["close"])
    targets = {
        "level_382_price": round(p_peak - delta * 0.382, 2),
        "level_500_price": round(p_peak - delta * 0.5, 2),
        "level_618_price": round(p_peak - delta * 0.618, 2),
    }
    if current <= targets["level_618_price"]:
        hit_level, status = "level_618", "進入 61.8% 最後防線"
    elif current <= targets["level_500_price"]:
        hit_level, status = "level_500", "進入 50.0% 中期防線"
    elif current <= targets["level_382_price"]:
        hit_level, status = "level_382", "進入 38.2% 第一防線"
    else:
        hit_level, status = "none", "尚未抵達回吐防線"

    xgb = load_json(DOCS_DATA_DIR / f"{stock_id}_xgb_prediction.json", {}) or {}
    up = xgb.get("up_probability")
    if hit_level == "none":
        order = "價格尚未回吐至防線，維持觀望，禁止因短線上漲追價。"
    elif up is not None and float(up) >= 60:
        order = "已進入防線且量化機率偏多，只能分批、小部位承接並設定停損。"
    else:
        order = "雖已進入防線，但量化機率未確認，等待止跌訊號，不搶反彈。"

    return {
        "stock": stock_label(stock_id),
        "stock_id": stock_id,
        "date": df.iloc[-1]["date"].strftime("%Y-%m-%d"),
        "current_price": current,
        "wave_start": {"date": df.iloc[start_idx]["date"].strftime("%Y-%m-%d"), "price": p_start},
        "wave_peak": {"date": df.iloc[peak_idx]["date"].strftime("%Y-%m-%d"), "price": p_peak},
        "wave_summary": f"波段由 {p_start:.2f} 上升至 {p_peak:.2f}，目前收盤 {current:.2f}。",
        "grid_defense_lines": {
            "level_382": f"{targets['level_382_price']:.2f} 元",
            "level_500": f"{targets['level_500_price']:.2f} 元",
            "level_618": f"{targets['level_618_price']:.2f} 元",
        },
        "grid_prices": targets,
        "hit_level": hit_level,
        "strike_status": status,
        "ai_execution_order": order,
        "xgb_up_probability": up,
        "calculation_method": "deterministic_fibonacci_retracement",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_grid_strategy_report(stock_id: str) -> dict:
    report = calculate_wave_grid(stock_id)
    out = DOCS_DATA_DIR / f"{stock_id}_grid_strategy.json"
    save_json(out, report)
    print(f"✅ [{stock_id}] 網格策略：{report['strike_status']}")
    return report


def main(stock_ids: list[str]) -> int:
    failures = []
    for stock_id in stock_ids:
        try:
            generate_grid_strategy_report(stock_id)
        except Exception as exc:
            failures.append(stock_id)
            print(f"❌ [{stock_id}] 網格策略失敗：{exc}")
    return 1 if failures and len(failures) == len(stock_ids) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or STOCK_LIST))
