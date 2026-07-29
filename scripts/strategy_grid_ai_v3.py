# scripts/strategy_grid_ai_v3.py
"""
AI Stock V3 - 動態 Prompt 封裝與波段回吐網格策略模組
自動從 SQLite 掃描近期波段高低點，計算黃金分割回吐進場防線，
並封裝為動態 Prompt 餵給 OpenAI GPT-4o-mini，輸出嚴格的量化操盤指令！
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

# 1. 載入環境變數與初始化 OpenAI
load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("❌ 找不到 OPENAI_API_KEY！請檢查 .env 檔案。")

client = OpenAI(api_key=api_key)

# 檔案與模型路徑
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MODEL_PATH = os.path.join(REPO_ROOT, "data_db", "xgb_nanya_model.pkl")
OUTPUT_DIR = os.path.join(REPO_ROOT, "docs", "data")

def calculate_wave_grid(stock_id: str = "2408", lookback_days: int = 120):
    """
    從 SQLite 撈取近期 K 線，自動掃描波段起漲點 (P_start) 與最高點 (P_peak)，
    並以 Python 精確運算 38.2%、50.0%、61.8% 三道進場防線！
    """
    conn = get_db_connection()
    df_price = pd.read_sql(
        f"SELECT * FROM daily_price WHERE stock_id = '{stock_id}' ORDER BY date DESC LIMIT {lookback_days}", 
        conn
    )
    conn.close()
    
    if df_price.empty:
        raise ValueError(f"❌ 找不到 [{stock_id}] 的 K 線資料，請先執行 build_data.py！")
        
    # 將時間排序排回由舊到新
    df_price = df_price.sort_values("date").reset_index(drop=True)
    
    # --- 自動尋找波段高低點 ---
    # 最高點：過去 N 天內的最高收盤價 (P_peak)
    peak_idx = df_price["close"].idxmax()
    p_peak = float(df_price["close"].iloc[peak_idx])
    peak_date = str(df_price["date"].iloc[peak_idx])
    
    # 起漲點：最高點出現「之前」的最低收盤價 (P_start)
    df_before_peak = df_price.iloc[:peak_idx+1]
    if len(df_before_peak) > 1:
        start_idx = df_before_peak["close"].idxmin()
        p_start = float(df_before_peak["close"].iloc[start_idx])
        start_date = str(df_before_peak["date"].iloc[start_idx])
    else:
        # 如果最高點就在第一天，直接取整段期間最低價
        start_idx = df_price["close"].idxmin()
        p_start = float(df_price["close"].iloc[start_idx])
        start_date = str(df_price["date"].iloc[start_idx])
        
    # 最新觀測現價
    current_price = float(df_price["close"].iloc[-1])
    current_date = str(df_price["date"].iloc[-1])
    
    # 波段絕對漲幅
    delta_p = p_peak - p_start
    
    # --- 套用回吐公式：B_target = P_peak - (Delta_P * F_retrace) ---
    grid_targets = {
        "強勢防線_回吐38.2%": round(p_peak - (delta_p * 0.382), 2),
        "半山腰防線_回吐50.0%": round(p_peak - (delta_p * 0.500), 2),
        "最後防線_回吐61.8%": round(p_peak - (delta_p * 0.618), 2)
    }
    
    # 判定當前是否落入打擊區
    hit_status = "⏳ 尚未抵達任何防線，目前空手等待。"
    hit_level = "None"
    
    if current_price <= grid_targets["最後防線_回吐61.8%"]:
        hit_status = "🔥 警示：已超跌進入【最後防線 (回吐 61.8%)】極限打擊區！"
        hit_level = "回吐61.8%最後防線"
    elif current_price <= grid_targets["半山腰防線_回吐50.0%"]:
        hit_status = "⚠️ 警示：已觸發【半山腰防線 (回吐 50.0%)】中期打擊區！"
        hit_level = "回吐50.0%半山腰防線"
    elif current_price <= grid_targets["強勢防線_回吐38.2%"]:
        hit_status = "📍 警示：已進入【強勢防線 (回吐 38.2%)】第一打擊區！"
        hit_level = "回吐38.2%強勢防線"
        
    # 嘗試撈取 XGBoost 最新勝率 (若有)
    xgb_win_rate = "N/A"
    if os.path.exists(MODEL_PATH):
        try:
            payload = joblib.load(MODEL_PATH)
            xgb_win_rate = f"{payload.get('accuracy', '-')}%"
        except Exception:
            pass

    return {
        "stock_id": f"{stock_id} 南亞科",
        "current_date": current_date,
        "current_price": current_price,
        "p_start": p_start,
        "start_date": start_date,
        "p_peak": p_peak,
        "peak_date": peak_date,
        "delta_p": round(delta_p, 2),
        "grid_targets": grid_targets,
        "hit_status": hit_status,
        "hit_level": hit_level,
        "xgb_win_rate": xgb_win_rate
    }

def generate_grid_strategy_report(stock_id: str = "2408"):
    """把量化網格數據封裝為動態 Prompt，交由 OpenAI 輸出操盤報告"""
    grid_data = calculate_wave_grid(stock_id, lookback_days=120)
    print(f"📡 成功計算 [{stock_id}] 波段回吐網格，正在發送給 OpenAI 量化操盤智囊團...")
    
    # --- 💡 【Lesson 9 核心】專案書專屬的量化分析師系統提示詞 ---
    system_prompt = """
    你是一位嚴格遵守量化交易紀律的 AI 操盤教練，擅長透過「波段回吐邏輯」尋找強勢暴衝股的絕佳買點。
    你的任務是檢視後端傳來的波段起漲點、最高點、黃金分割回吐價位與最新股價，給出最冷酷、客觀的進出指令。
    
    【嚴格強制規範】
    1. 你必須只回傳純 JSON 格式，絕對不可包含 Markdown 標籤或其餘雜字。
    2. 請對比目前的最新收盤價與三個防線，如果沒跌到防線，請嚴厲提醒投資人「繼續空手等待，禁止追高」！
    3. JSON 結構必須嚴格遵照以下屬性命名：
       {
         "stock": "標的名稱與代號",
         "date": "觀測日期",
         "wave_summary": "用 40 字總結此波段從起漲點到最高點的絕對漲幅與目前價格位階",
         "grid_defense_lines": {
           "level_382": "38.2% 強勢防線價位與狀態",
           "level_500": "50.0% 半山腰防線價位與狀態",
           "level_618": "61.8% 最後防線價位與狀態"
         },
         "strike_status": "目前是否已進入打擊區 (例如：進入38.2%防線 / 尚未抵達空手等待)",
         "ai_execution_order": "給出 40 字以內的鐵血操盤指令（結合 XGBoost 勝率，明確指示該掛單分批承接還是維持觀望）"
       }
    """
    
    # 透過 f-string 注入精確的量化試算數據
    user_prompt = f"""
    請依照以下後端 Python 已嚴格驗證的量化波段回吐數據，生成操盤指令 JSON：
    {json.dumps(grid_data, ensure_ascii=False, indent=2)}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1  # 溫度設極低，確保操盤紀律鐵血如一
        )
        
        report_dict = json.loads(response.choices[0].message.content)
        
        # --- 美觀呈現於終端機 ---
        print("\n" + "="*62)
        print(f"📐 【 AI Stock V3 ── 波段回吐黃金網格策略早報 】 📐")
        print("="*62)
        print(f"📌 標的：{report_dict.get('stock')} | 觀測日：{report_dict.get('date')}")
        print(f"🎯 狀態判定： 【 {report_dict.get('strike_status')} 】")
        print("-" * 62)
        print(f"🌊 【 波段結構分析 】：\n   {report_dict.get('wave_summary')}")
        print("-" * 62)
        print("🛡️ 【 黃金分割回吐進場防線 】：")
        lines = report_dict.get("grid_defense_lines", {})
        print(f"   ▫ 強勢防線 (38.2%)： {lines.get('level_382', '-')}")
        print(f"   ▫ 中期防線 (50.0%)： {lines.get('level_500', '-')}")
        print(f"   ▫ 極限防線 (61.8%)： {lines.get('level_618', '-')}")
        print("-" * 62)
        print(f"🤖 【 AI 鐵血操盤指令 】：\n   {report_dict.get('ai_execution_order')}")
        print("="*62)
        
        # 保存至 JSON 檔案
        out_file = os.path.join(OUTPUT_DIR, f"{stock_id[:4]}_grid_strategy.json")
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)
        print(f"💾 網格策略指令已同步保存至：[{out_file}]")
        
        return report_dict
        
    except Exception as e:
        print(f"❌ OpenAI API 呼叫或解析失敗：{e}")
        return None

if __name__ == "__main__":
    generate_grid_strategy_report("2408")