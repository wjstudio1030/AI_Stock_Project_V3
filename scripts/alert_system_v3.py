"""以相對異常 Z-score 與新聞情緒偵測風險，支援 Discord / Telegram。"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests

from config import (
    ALERT_FOREIGN_Z,
    ALERT_NEWS_SCORE,
    ALERT_TOTAL_Z,
    DOCS_DATA_DIR,
    STOCK_LIST,
)
from db_manager import get_db_connection
from project_data import load_json, save_json, stock_label


def _zscore_latest(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna().tail(60)
    if len(values) < 20 or values.std(ddof=0) == 0:
        return 0.0
    return float((values.iloc[-1] - values.mean()) / values.std(ddof=0))


def send_discord(title: str, message: str) -> None:
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        print("ℹ️ 未設定 Discord Webhook，略過 Discord 推播")
        return
    response = requests.post(
        url,
        json={
            "username": "AI Stock 風險雷達",
            "embeds": [{"title": title, "description": message, "color": 15158332}],
        },
        timeout=15,
    )
    response.raise_for_status()


def send_telegram(message: str) -> None:
    token = os.getenv("TG_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TG_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("ℹ️ 未設定 Telegram，略過 Telegram 推播")
        return
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message},
        timeout=15,
    )
    response.raise_for_status()


def check_black_swan_and_alert(stock_id: str) -> dict:
    conn = get_db_connection()
    try:
        chips = pd.read_sql_query(
            "SELECT date, foreign_net, total_net FROM institutional_chips WHERE stock_id = ? ORDER BY date",
            conn,
            params=(stock_id,),
        )
        price = pd.read_sql_query(
            "SELECT date, close FROM daily_price WHERE stock_id = ? ORDER BY date DESC LIMIT 1",
            conn,
            params=(stock_id,),
        )
    finally:
        conn.close()
    if chips.empty or price.empty:
        raise ValueError("缺少股價或法人資料")

    foreign_z = _zscore_latest(chips["foreign_net"])
    total_z = _zscore_latest(chips["total_net"])
    latest_chips = chips.iloc[-1]
    news = load_json(DOCS_DATA_DIR / f"{stock_id}_news_ai_sentiment.json", {}) or {}
    news_score = float(news.get("overall_sentiment_score", 0.0))

    alerts = []
    if foreign_z <= ALERT_FOREIGN_Z and float(latest_chips["foreign_net"]) < 0:
        alerts.append(f"外資賣超達自身近60日極端值（z={foreign_z:.2f}）")
    if total_z <= ALERT_TOTAL_Z and float(latest_chips["total_net"]) < 0:
        alerts.append(f"三大法人合計賣超達自身近60日極端值（z={total_z:.2f}）")
    if news_score <= ALERT_NEWS_SCORE:
        alerts.append(f"新聞情緒偏極端負面（{news_score:+.2f}）")

    result = {
        "stock_id": stock_id,
        "stock": stock_label(stock_id),
        "observation_date": str(price.iloc[0]["date"]),
        "close": float(price.iloc[0]["close"]),
        "foreign_z": round(foreign_z, 3),
        "total_institutional_z": round(total_z, 3),
        "news_sentiment_score": round(news_score, 3),
        "triggered": bool(alerts),
        "alerts": alerts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_json(DOCS_DATA_DIR / f"{stock_id}_risk_alert.json", result)

    if alerts:
        message = f"{result['stock']} {result['observation_date']}\n" + "\n".join(f"• {item}" for item in alerts)
        for sender in (lambda: send_discord(f"{result['stock']} 風險警報", message), lambda: send_telegram(message)):
            try:
                sender()
            except Exception as exc:
                print(f"⚠️ 推播失敗：{exc}")
        print(f"🚨 [{stock_id}] 觸發 {len(alerts)} 項風險警報")
    else:
        print(f"✅ [{stock_id}] 未觸發極端風險條件")
    return result


def main(stock_ids: list[str]) -> int:
    failures = []
    for stock_id in stock_ids:
        try:
            check_black_swan_and_alert(stock_id)
        except Exception as exc:
            failures.append(stock_id)
            print(f"❌ [{stock_id}] 風險掃描失敗：{exc}")
    return 1 if failures and len(failures) == len(stock_ids) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or STOCK_LIST))
