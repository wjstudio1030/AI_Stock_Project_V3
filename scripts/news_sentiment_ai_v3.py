# scripts/news_sentiment_ai_v3.py
"""
AI Stock V3 - OpenAI 新聞情緒零樣本分析模組
取代傳統關鍵字計數，利用 GPT-4o-mini 深度理解財經新聞標題的潛台詞、
利多出盡與反諷語境，產出 -1.0 ~ +1.0 的真實情緒評分，並保存至 SQLite！
"""

import os
import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from data_fetcher import get_stock_news
from db_manager import get_db_connection

# 1. 載入金鑰
load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("❌ 找不到 OPENAI_API_KEY！請檢查 .env 檔案。")

client = OpenAI(api_key=api_key)

# 檔案路徑
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(REPO_ROOT, "docs", "data")

def fetch_recent_news_for_ai(stock_id: str = "2408", days: int = 7):
    """抓取近期個股新聞，準備餵給 AI 進行深度情緒分析"""
    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    print(f"📡 正在從 FinMind 抓取 [{stock_id}] 近 {days} 天的新聞標題...")
    try:
        df_news = get_stock_news(stock_id, start_date, end_date)
        if df_news.empty:
            print("⚠️ 查無近期新聞資料。")
            return []
            
        # 整理為乾淨的字典清單
        news_list = []
        for idx, row in df_news.iterrows():
            news_list.append({
                "id": idx + 1,
                "date": row["date"].strftime("%Y-%m-%d") if isinstance(row["date"], pd.Timestamp) else str(row["date"])[:10],
                "title": row["title"],
                "source": row.get("source", "財經媒體")
            })
        print(f"✨ 成功整理出 {len(news_list)} 則相關財經新聞！")
        return news_list[:15] # 為了 API 反應速度與專注度，取最新前 15 則
    except Exception as e:
        print(f"❌ 新聞抓取失敗：{e}")
        return []

def analyze_news_sentiment_zeroshot(stock_id: str = "2408"):
    """呼叫 OpenAI 進行 Zero-shot 零樣本情緒深度評分"""
    news_list = fetch_recent_news_for_ai(stock_id, days=10)
    
    if not news_list:
        print("📭 沒有新聞可供分析，跳過評分。")
        return None
        
    print("🧠 正在將新聞矩陣發送給 OpenAI 進行深度語意解讀 (排除字面陷阱)...")
    
    # --- 💡 【Lesson 8 核心】防語意陷阱的 Zero-shot 提示詞 ---
    system_prompt = """
    你是一位專精於半導體與記憶體產業 (DRAM) 的頂級金融市場情緒分析師。
    你的任務是閱讀傳入的個股新聞標題，給出最客觀、最符合真實股市反應的情緒評分。
    
    【專業語意解讀原則 - 嚴格遵守】
    1. 警惕「利多出盡」與「利空出盡」：若標題顯示獲利創新高但提及市場擔憂後市、或外資趁機調節，應調降分數；若提及大跌後跌無可跌、利空築底，應給予回升評價。
    2. 識別多重語意：若同時提及成長與衰退，請以對股價趨勢影響最大的主軸線產品（如 DDR4/DDR5 現貨需求）為主。
    3. 忽略情緒化字眼：不要被「狂飆」、「崩盤」等浮誇記者字眼綁架，深入評估其實際商業影響力。

    【JSON 輸出格式規範】
    請必定回傳純 JSON 物件，結構如下：
    {
      "stock_id": "股票代號",
      "overall_sentiment_score": 數值 (介於 -1.0 到 +1.0 之間，小數點後二位。-1為極度看空，0為中性，+1為極度看多),
      "market_vibe_summary": "用 40 字總結這批新聞展現的市場主旋律與潛在情緒隱患",
      "article_analysis": [
        {
          "id": 對應的新聞編號,
          "title": "新聞標題",
          "score": 單篇分數 (-1.0 ~ +1.0),
          "ai_comment": "一條 15 字以內的短評，說明為什麼給這個分數（如：雖提及成長但有報價下滑隱憂）"
        }
      ]
    }
    """
    
    user_prompt = f"以下是南亞科 ({stock_id}) 近期財經新聞標題，請進行嚴格的 Zero-shot 情緒分析：\n{json.dumps(news_list, ensure_ascii=False)}"
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2  # 低溫度讓評分標準保持嚴謹一致
        )
        
        result_json_str = response.choices[0].message.content
        result_dict = json.loads(result_json_str)
        
        # --- 美觀呈現於終端機 ---
        score = result_dict.get("overall_sentiment_score", 0.0)
        vibe = "🚀 極度樂觀" if score > 0.5 else "📈 偏多看好" if score > 0.1 else "⚖️ 處於中性" if score > -0.1 else "📉 偏空謹慎" if score > -0.5 else "⚠️ 極度悲觀"
        
        print("\n" + "="*60)
        print(f"📰 【 AI Stock V3 ── OpenAI 財經新聞零樣本深度解讀 】 📰")
        print("="*60)
        print(f"📌 標的：{result_dict.get('stock_id', stock_id)} | 綜合情緒分數：【 {score:+.2f} 】 ({vibe})")
        print("-" * 60)
        print(f"🧠 【 市場氣氛總結 】：\n   {result_dict.get('market_vibe_summary', '-')}")
        print("-" * 60)
        print("🔍 【 關鍵標題深度診斷抽樣 】：")
        
        articles = result_dict.get("article_analysis", [])
        for art in articles[:5]: # 印出前 5 篇重點
            s = art.get('score', 0)
            tag = "🔴 [利多]" if s > 0.2 else "🟢 [利空]" if s < -0.2 else "⚪ [中性]"
            print(f"  {tag} {s:+.1f} | {art.get('title')[:26]}...")
            print(f"      💡 AI短評：{art.get('ai_comment')}")
        print("="*60)
        
        # 保存至 JSON 供網頁展示
        out_file = os.path.join(OUTPUT_DIR, f"{stock_id}_news_ai_sentiment.json")
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        print(f"💾 AI 情緒評分報告已同步保存至：[{out_file}]")
        
        return result_dict
        
    except Exception as e:
        print(f"❌ OpenAI API 呼叫或解析失敗：{e}")
        return None

if __name__ == "__main__":
    analyze_news_sentiment_zeroshot("2408")