# scripts/ultimate_judge_ai_v4.py
"""
AI Stock V4 - 終極 AI 投資長 (CIO) 判決引擎
整合 XGBoost 數理機率、新聞情緒、波段網格與黑天鵝狀態，
輸出全系統唯一的「最終綜合上漲勝率 (%)」與微調邏輯！
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# 載入環境變數
load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("❌ 找不到 OPENAI_API_KEY！")

client = OpenAI(api_key=api_key)

# 路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(REPO_ROOT, "docs", "data")

def get_synthesized_data(stock_id: str = "2408"):
    """讀取散落在各處的 AI 報告與數據，打包成統合矩陣"""
    
    # 預設底線資料
    synth_data = {
        "stock_id": stock_id,
        "base_xgboost_prob": 50.0,
        "news_sentiment_score": 0.0,
        "grid_status": "未知",
        "trend_rating": "未知",
        "black_swan_alert": "無"
    }
    
    # 1. 讀取 AI 早報 (獲取 XGBoost 原始機率與趨勢評級)
    report_path = os.path.join(DATA_DIR, f"{stock_id}_ai_report.json")
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            rep = json.load(f)
            synth_data["trend_rating"] = rep.get("trend_rating", "未知")
            # 嘗試從摘要中提取勝率，或假設從其他來源讀取 (此處簡化為模擬預期格式)
            summary = rep.get("quant_summary", "")
            if "勝率" in summary:
                synth_data["base_xgboost_prob"] = summary # 讓語言模型自己解讀字串中的數字
                
    # 2. 讀取新聞情緒
    news_path = os.path.join(DATA_DIR, f"{stock_id}_news_ai_sentiment.json")
    if os.path.exists(news_path):
        with open(news_path, "r", encoding="utf-8") as f:
            news = json.load(f)
            synth_data["news_sentiment_score"] = news.get("overall_sentiment_score", 0.0)
            if float(synth_data["news_sentiment_score"]) <= -0.6:
                synth_data["black_swan_alert"] = "觸發情緒黑天鵝！"
                
    # 3. 讀取波段網格防線
    grid_path = os.path.join(DATA_DIR, f"{stock_id[:4]}_grid_strategy.json")
    if os.path.exists(grid_path):
        with open(grid_path, "r", encoding="utf-8") as f:
            grid = json.load(f)
            synth_data["grid_status"] = grid.get("strike_status", "未知")
            
    return synth_data

def run_ultimate_judge(stock_id: str = "2408"):
    """交由 GPT-4o-mini 進行最終機率融合"""
    synth_data = get_synthesized_data(stock_id)
    print("📡 正在彙整 5 大系統訊號，提交給 AI 投資長 (CIO) 進行最終判決...")
    
    system_prompt = """
    你是量化基金的「AI 投資長」。你的任務是將底層模型 (XGBoost) 的勝率，結合市場情緒、網格防線與黑天鵝警報，輸出「全系統唯一的最終上漲機率」。
    
    【加權微調邏輯指引】
    1. XGBoost 給出的是純數理基準 (Base Probability)。
    2. 如果 news_sentiment_score 為正，應適度上調機率 (+2% ~ +5%)；若為負，應下調。
    3. 如果 grid_status 顯示「進入打擊區/防線」，勝率應大幅上調；若為「空手等待/未觸發」，勝率應受到壓抑。
    4. 如果出現 black_swan_alert，最終機率強制壓低至 30% 以下。
    
    【JSON 嚴格輸出格式】
    {
      "ultimate_up_probability": 數值 (0.0 到 100.0 的浮點數，代表最終綜合看漲機率),
      "ultimate_down_probability": 數值 (100.0 減去看漲機率),
      "adjustment_logic": "用 40 字說明你是如何從 XGBoost 基準，依照新聞與網格狀態加減權重，得出這個最終機率的。"
    }
    """
    
    user_prompt = f"請根據以下 5 大模組彙整狀態，給出最終唯一的機率判決：\n{json.dumps(synth_data, ensure_ascii=False)}"
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        result = json.loads(response.choices[0].message.content)
        
        print("\n" + "="*60)
        print("⚖️ 【 AI Stock V4 ── 投資長最終判決報告 】 ⚖️")
        print("="*60)
        print(f"📈 終極上漲勝率： 【 {result.get('ultimate_up_probability')}% 】")
        print(f"📉 終極下跌機率： 【 {result.get('ultimate_down_probability')}% 】")
        print("-" * 60)
        print(f"🧠 【 投資長加權邏輯 】：\n   {result.get('adjustment_logic')}")
        print("="*60)
        
        # 存檔供前端讀取
        out_file = os.path.join(DATA_DIR, f"{stock_id}_ultimate_judge.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        print(f"💾 終極判決已存至：{out_file}")
        
    except Exception as e:
        print(f"❌ 判決引擎執行失敗：{e}")

if __name__ == "__main__":
    run_ultimate_judge("2408")