# scripts/alert_system_v3.py
"""
AI Stock V3 - 黑天鵝事件防範與即時推播預警模組
自動掃描 SQLite 籌碼動向與 OpenAI 新聞情緒，
一旦偵測到重大利空或法人巨量倒貨，秒速發送推播至 Discord / Telegram！
"""

import os
import json
import sqlite3
import requests
import pandas as pd
from dotenv import load_dotenv
from db_manager import get_db_connection

# 1. 載入環境變數
load_dotenv()
DISCORD_URL = os.environ.get("DISCORD_WEBHOOK_URL")
TG_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

# 路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(REPO_ROOT, "docs", "data")

def send_discord_alert(title: str, message: str, color: int = 15158332):
    """發送精美嵌入式卡片至 Discord 頻道 (15158332 為紅色，3066993 為綠色)"""
    if not DISCORD_URL or "discord.com" not in DISCORD_URL:
        print("💡 [推播模擬] Discord Webhook 未設定，改為印出終端機訊息。")
        return
        
    payload = {
        "username": "AI Stock V3 鐵血警衛",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/2592/2592186.png",
        "embeds": [
            {
                "title": f"🚨 {title}",
                "description": message,
                "color": color,
                "footer": {"text": "AI Stock V3 黑天鵝自動監控系統"}
            }
        ]
    }
    try:
        resp = requests.post(DISCORD_URL, json=payload, timeout=10)
        resp.raise_for_status()
        print("📱 成功發送預警卡片至 Discord 群組！")
    except Exception as e:
        print(f"❌ Discord 推播發送失敗：{e}")

def send_telegram_alert(message: str):
    """發送訊息至 Telegram 群組或私人對話"""
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("📱 成功發送推播至 Telegram！")
    except Exception as e:
        print(f"❌ Telegram 推播發送失敗：{e}")

def check_black_swan_and_alert(stock_id: str = "2408"):
    """執行全方位黑天鵝掃描，判斷是否需要發布緊急推播"""
    print(f"🛡️ 正在執行 [{stock_id} 南亞科] 盤後黑天鵝與異常籌碼防禦掃描...")
    
    # --- 1. 從 SQLite 撈取今日最新籌碼 ---
    conn = get_db_connection()
    df_chips = pd.read_sql(f"SELECT * FROM institutional_chips WHERE stock_id = '{stock_id}' ORDER BY date DESC LIMIT 1", conn)
    df_price = pd.read_sql(f"SELECT * FROM daily_price WHERE stock_id = '{stock_id}' ORDER BY date DESC LIMIT 1", conn)
    conn.close()
    
    if df_price.empty or df_chips.empty:
        print("⚠️ 資料庫尚無最新 K 線或籌碼，跳過掃描。")
        return

    latest_date = str(df_price["date"].iloc[0])
    close_price = float(df_price["close"].iloc[0])
    foreign_net = int(df_chips["foreign_net"].iloc[0])
    trust_net = int(df_chips["trust_net"].iloc[0])
    total_net = int(df_chips["total_net"].iloc[0])
    
    # --- 2. 讀取最新 OpenAI 新聞情緒分數 ---
    sentiment_score = 0.0
    sentiment_vibe = "無新聞數據"
    news_file = os.path.join(OUTPUT_DIR, f"{stock_id}_news_ai_sentiment.json")
    if os.path.exists(news_file):
        try:
            with open(news_file, "r", encoding="utf-8") as f:
                news_data = json.load(f)
                sentiment_score = float(news_data.get("overall_sentiment_score", 0.0))
                sentiment_vibe = news_data.get("market_vibe_summary", "")
        except Exception:
            pass
            
    # --- 3. 觸發防禦紅線檢查 ---
    alerts_triggered = []
    
    # 紅線 A：外資單日大幅砍殺超過 -8,000 張
    if foreign_net <= -8000:
        alerts_triggered.append(f"🐳 **外資巨量倒貨**：今日狂砍 **{foreign_net:,} 張**，賣壓極度沉重！")
        
    # 紅線 B：三大法人合計出逃超過 -12,000 張
    if total_net <= -12000:
        alerts_triggered.append(f"🌊 **法人土洋齊賣**：三大法人單日共拋售 **{total_net:,} 張**！")
        
    # 紅線 C：OpenAI 新聞情緒跌破 -0.6 (重大利空/黑天鵝氣氛)
    if sentiment_score <= -0.6:
        alerts_triggered.append(f"📰 **AI 氣氛核彈**：新聞情緒跌至 **{sentiment_score}**！理由：*{sentiment_vibe}*")
        
    # --- 4. 判斷並執行推播 ---
    print("\n" + "="*56)
    print(f"🛡️ 【 AI Stock V3 ── 盤後防禦雷達掃描報告 】 🛡️")
    print("="*56)
    print(f"📌 標的：{stock_id} 南亞科 | 觀測日期：{latest_date} | 收盤：{close_price} 元")
    print(f"📊 籌碼概況：外資 {foreign_net:+,} 張 | 投信 {trust_net:+,} 張 | 合計 {total_net:+,} 張")
    print(f"🧠 AI 新聞情緒分數：【 {sentiment_score:+.2f} 】")
    print("-" * 56)
    
    if alerts_triggered:
        print("🚨 狀態判定：【 觸發紅線！系統發動緊急避險警報 】")
        print("-" * 56)
        for idx, alt in enumerate(alerts_triggered, 1):
            print(f"  {idx}. {alt.replace('**', '').replace('*', '')}")
        print("="*56)
        
        # 組合推播訊息文字
        msg_body = f"**觀測標的**：`{stock_id} 南亞科` ({latest_date})\n" \
                   f"**最新收盤**：`{close_price} 元`\n\n" \
                   f"**🔥 觸發緊急防禦紅線**：\n" + "\n".join([f"• {a}" for a in alerts_triggered]) + \
                   f"\n\n🤖 **AI 系統指令**：市場風險急遽升高！若您目前持有部位，建議立刻檢查前述【波段黃金網格防線】，嚴格執行減碼或停損避險！"
                   
        # 實時推播！
        send_discord_alert(f"{stock_id} 南亞科 ── 觸發黑天鵝防禦警報！", msg_body, color=15158332)
        send_telegram_alert(f"🚨 **{stock_id} 南亞科 黑天鵝警報** 🚨\n\n{msg_body}")
        
    else:
        print("🟢 狀態判定：【 籌碼與情緒處於安全水位，無黑天鵝風險 】")
        print("💡 系統提示：今日市場未偵測到極端利空與巨量倒貨，可照常執行原有之波段策略。")
        print("="*56)

if __name__ == "__main__":
    check_black_swan_and_alert("2408")