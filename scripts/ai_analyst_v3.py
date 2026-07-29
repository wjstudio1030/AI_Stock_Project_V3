# scripts/ai_analyst_v3.py
"""
AI Stock V3 - OpenAI 量化智囊團診斷模組
讀取 SQLite 最新量化特徵與 XGBoost 勝率，
呼叫 OpenAI GPT-4o-mini 並啟用 JSON Mode，生成結構化的專業白話文診斷書！
"""

import os
import json
import joblib
import sqlite3
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from db_manager import get_db_connection

# 1. 載入 .env 檔案中的環境變數
load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")

if not api_key or "請在這裡填入" in api_key:
    raise ValueError("❌ 找不到有效的 OPENAI_API_KEY！請檢查專案根目錄下的 .env 檔案是否已填入正確的金鑰。")

# 初始化 OpenAI 客戶端
client = OpenAI(api_key=api_key)

# 路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MODEL_PATH = os.path.join(REPO_ROOT, "data_db", "xgb_nanya_model.pkl")

def get_latest_quant_data(stock_id: str = "2408"):
    """讀取 SQLite 與 XGBoost，打包最新的全方位量化數據"""
    conn = get_db_connection()
    df_price = pd.read_sql(f"SELECT * FROM daily_price WHERE stock_id = '{stock_id}' ORDER BY date DESC LIMIT 1", conn)
    df_chips = pd.read_sql(f"SELECT * FROM institutional_chips WHERE stock_id = '{stock_id}' ORDER BY date DESC LIMIT 1", conn)
    df_whales = pd.read_sql(f"SELECT * FROM weekly_whales WHERE stock_id = '{stock_id}' ORDER BY date DESC LIMIT 1", conn)
    df_dram = pd.read_sql("SELECT * FROM dram_spot_price ORDER BY date DESC LIMIT 1", conn)
    conn.close()
    
    if df_price.empty:
        raise ValueError("❌ 找不到最新 K 線資料，請先執行 build_data.py！")
        
    # 讀取 XGBoost 預測機率
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("❌ 找不到 XGBoost 模型，請先執行 train_xgb_v3.py！")
    
    payload = joblib.load(MODEL_PATH)
    model = payload["model"]
    feature_names = payload["feature_names"]
    
    # 組裝特徵進行預測
    row = df_price.copy()
    row["foreign_net"] = df_chips["foreign_net"].iloc[0] if not df_chips.empty else 0
    row["trust_net"] = df_chips["trust_net"].iloc[0] if not df_chips.empty else 0
    row["margin_change"] = df_chips["margin_change"].iloc[0] if not df_chips.empty else 0
    row["whale_pct"] = df_whales["whale_pct"].iloc[0] if not df_whales.empty else 55.0
    row["dram_change_pct"] = df_dram["daily_change_pct"].iloc[0] if not df_dram.empty else 0.0
    row["ma20"] = row["ma20"].replace(0, np.nan)
    row["bias_ma20"] = ((row["close"] - row["ma20"]) / row["ma20"]) * 100
    row["ret_3d"] = 0.0
    row = row.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    feature_map = {
        "k_val": "1. 技術_KD值(K)", "d_val": "2. 技術_KD值(D)", "bias_ma20": "3. 技術_月線乖離率%",
        "ret_3d": "4. 技術_近3日動能%", "foreign_net": "5. 籌碼_外資買賣超(張)",
        "trust_net": "6. 籌碼_投信買賣超(張)", "margin_change": "7. 散戶_融資增減(張)",
        "whale_pct": "8. 大戶_集保持股比例%", "dram_change_pct": "9. 產業_DRAM現貨單日漲跌%"
    }
    
    valid_cols = [c for c in feature_map.keys() if c in row.columns]
    X_latest = row[valid_cols].rename(columns=feature_map).reindex(columns=feature_names, fill_value=0)
    
    prob_up = round(model.predict_proba(X_latest)[0][1] * 100, 1)
    
    # 封裝為簡明字典供 AI 閱讀
    quant_data = {
        "觀測日期": str(df_price["date"].iloc[0]),
        "股票名稱": f"{stock_id} 南亞科",
        "最新收盤價": float(df_price["close"].iloc[0]),
        "XGBoostAI預測上漲勝率": f"{prob_up}%",
        "技術面_KD值K": round(float(df_price["k_val"].iloc[0]), 1),
        "技術面_月線乖離率": f"{round(float(row['bias_ma20'].iloc[0]), 2)}%",
        "籌碼面_外資單日買賣超": f"{int(row['foreign_net'].iloc[0])} 張",
        "籌碼面_投信單日買賣超": f"{int(row['trust_net'].iloc[0])} 張",
        "籌碼面_集保大戶持股比例": f"{float(row['whale_pct'].iloc[0])}%",
        "產業面_DRAM現貨單日漲跌": f"{float(row['dram_change_pct'].iloc[0])}%"
    }
    return quant_data

def generate_ai_report(stock_id: str = "2408"):
    """呼叫 OpenAI GPT-4o-mini，生成 JSON Mode 診斷報告"""
    quant_data = get_latest_quant_data(stock_id)
    print(f"📡 成功撈取 [{stock_id}] 最新量化數據，正在發送給 OpenAI 首席智囊團...")
    
    # --- 💡 【Lesson 7 核心】系統提示詞與 JSON 規範 ---
    system_prompt = """
    你是一位擁有 20 年資歷的頂級證券量化首席分析師，專精於台股記憶體景氣循環股（南亞科 2408）。
    你的任務是解讀後端傳來的量化數據，並產出給投資人看的「白話文專業早報」。
    
    【嚴格強制規範】
    1. 你必須只回傳純 JSON 格式，絕對不可以包含任何 Markdown 標籤（如 ```json）或多餘的文字敘述。
    2. 回傳的 JSON 結構必須嚴格遵照以下屬性命名：
       {
         "date": "觀測日期",
         "stock": "股票代號與名稱",
         "trend_rating": "用 1~5 顆星標示多空評級（例如：⭐⭐⭐ 偏多觀察 或 ⭐⭐ 區間震盪）",
         "quant_summary": "用 50 字以內的白話文，綜合總結 XGBoost 勝率、法人籌碼與 DRAM 現貨報價的交互關係",
         "action_advice": "給出明確、具體的短線操作或觀察建議（30 字以內）",
         "risk_warning": "點出一個當前最需要注意的潛在市場或技術風險（30 字以內）"
       }
    """
    
    user_prompt = f"請解讀以下最新量化數據，並依據規範回傳 JSON 診斷報告：\n{json.dumps(quant_data, ensure_ascii=False)}"
    
    try:
        # 呼叫 OpenAI API (啟用 JSON Mode)
        response = client.chat.completions.create(
            model="gpt-4o-mini",   # 使用最具性價比且反應極快的 gpt-4o-mini
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}, # 👈 強制 JSON Mode！
            temperature=0.3  # 降低隨機性，讓分析更加嚴謹穩定
        )
        
        # 解析回傳結果
        report_json_str = response.choices[0].message.content
        report_dict = json.loads(report_json_str)
        
        # --- 美觀呈現於終端機 ---
        print("\n" + "="*58)
        print(f"🏢 【 AI Stock V3 ── OpenAI 首席量化智囊早報 】 🏢")
        print("="*58)
        print(f"📅 日期：{report_dict.get('date', '-')} | 標的：{report_dict.get('stock', '-')}")
        print(f"📊 多空趨勢評級： 【 {report_dict.get('trend_rating', '-')} 】")
        print("-" * 58)
        print(f"🧠 【 量化綜合摘要 】：\n   {report_dict.get('quant_summary', '-')}")
        print(f"💡 【 白話操作建議 】：\n   {report_dict.get('action_advice', '-')}")
        print(f"⚠️ 【 風險提示與防線 】：\n   {report_dict.get('risk_warning', '-')}")
        print("="*58)
        
        # 順手存檔成 json，方便下階段 Streamlit 網頁讀取！
        out_file = os.path.join(REPO_ROOT, "docs", "data", f"{stock_id}_ai_report.json")
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)
        print(f"💾 結構化診斷書已同步保存至：[{out_file}]")
        
        return report_dict
        
    except Exception as e:
        print(f"❌ OpenAI API 呼叫或解析失敗：{e}")
        return None

if __name__ == "__main__":
    generate_ai_report("2408")