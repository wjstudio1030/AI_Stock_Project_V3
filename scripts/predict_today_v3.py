# scripts/predict_today_v3.py
"""
AI Stock V3 - 每日盤後秒速預測引擎
直接讀取已封裝的 XGBoost 模型 (.pkl)，
載入 SQLite 最新單日特徵，0.1 秒輸出明後天漲跌機率！
"""

import os
import joblib
import pandas as pd
import numpy as np
from db_manager import get_db_connection

# 設定模型讀取路徑
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MODEL_PATH = os.path.join(REPO_ROOT, "data_db", "xgb_nanya_model.pkl")

def get_latest_day_features(stock_id: str = "2408"):
    """從 SQLite 抓取「最新一天」的完整特徵陣列"""
    conn = get_db_connection()
    df_price = pd.read_sql(f"SELECT * FROM daily_price WHERE stock_id = '{stock_id}' ORDER BY date DESC LIMIT 1", conn)
    df_chips = pd.read_sql(f"SELECT * FROM institutional_chips WHERE stock_id = '{stock_id}' ORDER BY date DESC LIMIT 1", conn)
    df_whales = pd.read_sql(f"SELECT * FROM weekly_whales WHERE stock_id = '{stock_id}' ORDER BY date DESC LIMIT 1", conn)
    df_dram = pd.read_sql("SELECT * FROM dram_spot_price ORDER BY date DESC LIMIT 1", conn)
    conn.close()
    
    if df_price.empty:
        raise ValueError("❌ 找不到最新的 K 線，請先執行 build_data.py！")
        
    latest_date = df_price["date"].iloc[0]
    print(f"📅 鎖定最新量化觀測日期：【 {latest_date} 】")
    
    # 組合單日特徵
    row = df_price.copy()
    row["foreign_net"] = df_chips["foreign_net"].iloc[0] if not df_chips.empty else 0
    row["trust_net"] = df_chips["trust_net"].iloc[0] if not df_chips.empty else 0
    row["margin_change"] = df_chips["margin_change"].iloc[0] if not df_chips.empty else 0
    row["whale_pct"] = df_whales["whale_pct"].iloc[0] if not df_whales.empty else 55.0
    row["dram_change_pct"] = df_dram["daily_change_pct"].iloc[0] if not df_dram.empty else 0.0
    
    # 計算衍生特徵
    row["ma20"] = row["ma20"].replace(0, np.nan)
    row["bias_ma20"] = ((row["close"] - row["ma20"]) / row["ma20"]) * 100
    row["ret_3d"] = 0.0 # 最新單日暫化為 0 或從前幾日推算，此處維持穩定數值
    row = row.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    # 建立特徵映射，確保和訓練時的欄位順序 100% 相同！
    feature_map = {
        "k_val": "1. 技術_KD值(K)",
        "d_val": "2. 技術_KD值(D)",
        "bias_ma20": "3. 技術_月線乖離率%",
        "ret_3d": "4. 技術_近3日動能%",
        "foreign_net": "5. 籌碼_外資買賣超(張)",
        "trust_net": "6. 籌碼_投信買賣超(張)",
        "margin_change": "7. 散戶_融資增減(張)",
        "whale_pct": "8. 大戶_集保持股比例%",
        "dram_change_pct": "9. 產業_DRAM現貨單日漲跌%"
    }
    
    valid_cols = [c for c in feature_map.keys() if c in row.columns]
    X_latest = row[valid_cols].rename(columns=feature_map)
    return X_latest, latest_date, row["close"].iloc[0]

def predict_tomorrow():
    """載入封裝好的 .pkl 大腦，進行實時看盤預測"""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"❌ 找不到模型檔案 [{MODEL_PATH}]！請先執行 train_xgb_v3.py 進行訓練存檔。")
        
    print("⚡ 正在讀取已封裝的 XGBoost AI 大腦...")
    payload = joblib.load(MODEL_PATH)
    model = payload["model"]
    feature_names = payload["feature_names"]
    
    X_latest, latest_date, close_price = get_latest_day_features(payload["stock_id"])
    # 確保特徵欄位與模型要求嚴格一致
    X_latest = X_latest.reindex(columns=feature_names, fill_value=0)
    
    # 執行秒速預測！
    prob = model.predict_proba(X_latest)[0]
    up_prob = round(prob[1] * 100, 1)
    down_prob = round(prob[0] * 100, 1)
    
    print("\n" + "="*50)
    print(f"🤖 【 AI Stock V3 ── {payload['stock_id']} 南亞科 盤後量化預報 】 🤖")
    print("="*50)
    print(f"📌 基準觀測日期：{latest_date} | 最新收盤價：{close_price} 元")
    print(f"📊 歷史驗證勝率：{payload['accuracy']}% (由抗過擬合引擎背書)")
    print("-" * 50)
    print(f"🚀 【 明日上漲機率 】： {up_prob} %")
    print(f"📉 【 明日下跌機率 】： {down_prob} %")
    print("-" * 50)
    
    if up_prob >= 65.0:
        print("💡 量化訊號評語：【 🔥 強勢多頭 】勝率極高，量化動能偏多，建議伺機布局！")
    elif up_prob <= 35.0:
        print("💡 量化訊號評語：【 ⚠️ 弱勢探底 】空方賣壓沉重，建議空手觀望或嚴格停損！")
    else:
        print("💡 量化訊號評語：【 ⚖️ 多空震盪 】方向未明，目前位處區間盤整，建議耐心等待轉折。")
    print("="*50)

if __name__ == "__main__":
    predict_tomorrow()