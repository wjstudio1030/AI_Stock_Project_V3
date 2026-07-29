# scripts/train_xgb_v3.py
"""
AI Stock V3 - XGBoost 預測引擎與模型存檔模組 (Lesson 5 封裝升級版)
從 SQLite 讀取量化特徵，訓練抗過擬合 XGBoost 模型，
將訓練好的最佳模型封裝為本地實體檔案 (.pkl)，供每日即時預測呼叫！
"""

import os
import sqlite3
import pandas as pd
import numpy as np
import xgboost as xgb
import joblib  # 👈 【Lesson 5 新增】模型封裝工具
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from db_manager import get_db_connection

# 設定模型保存路徑
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MODEL_DIR = os.path.join(REPO_ROOT, "data_db")
MODEL_PATH = os.path.join(MODEL_DIR, "xgb_nanya_model.pkl")

def load_and_merge_data(stock_id: str = "2408") -> pd.DataFrame:
    conn = get_db_connection()
    df_price = pd.read_sql(f"SELECT * FROM daily_price WHERE stock_id = '{stock_id}' ORDER BY date", conn)
    df_chips = pd.read_sql(f"SELECT * FROM institutional_chips WHERE stock_id = '{stock_id}' ORDER BY date", conn)
    df_whales = pd.read_sql(f"SELECT * FROM weekly_whales WHERE stock_id = '{stock_id}' ORDER BY date", conn)
    df_dram = pd.read_sql("SELECT * FROM dram_spot_price ORDER BY date", conn)
    conn.close()
    
    if df_price.empty:
        raise ValueError(f"❌ 資料庫中找不到 [{stock_id}] 的 K 線資料！")

    if not df_chips.empty:
        df = pd.merge(df_price, df_chips.drop(columns=["stock_id"], errors="ignore"), on="date", how="left")
    else:
        df = df_price.copy()
        
    if not df_whales.empty:
        df = pd.merge(df, df_whales[["date", "whale_pct", "retail_pct"]], on="date", how="left")
        df["whale_pct"] = df["whale_pct"].ffill().fillna(55.0)
        df["retail_pct"] = df["retail_pct"].ffill().fillna(25.0)
    else:
        df["whale_pct"] = 55.0
        df["retail_pct"] = 25.0
        
    if not df_dram.empty:
        df = pd.merge(df, df_dram[["date", "ddr4_8gb_price", "daily_change_pct"]], on="date", how="left")
        df["ddr4_8gb_price"] = df["ddr4_8gb_price"].ffill().fillna(1.75)
        df.rename(columns={"daily_change_pct": "dram_change_pct"}, inplace=True)
        df["dram_change_pct"] = df["dram_change_pct"].ffill().fillna(0)
    else:
        df["ddr4_8gb_price"] = 1.75
        df["dram_change_pct"] = 0
        
    df = df.ffill().fillna(0)
    return df

def build_features_and_target(df: pd.DataFrame):
    work_df = df.copy()
    work_df["ma20"] = work_df["ma20"].replace(0, np.nan)
    work_df["bias_ma20"] = ((work_df["close"] - work_df["ma20"]) / work_df["ma20"]) * 100
    work_df["ret_3d"] = work_df["close"].pct_change(3) * 100
    work_df = work_df.replace([np.inf, -np.inf], np.nan).fillna(0)
    
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
    
    valid_cols = [c for c in feature_map.keys() if c in work_df.columns]
    X = work_df[valid_cols].rename(columns=feature_map)
    work_df["target"] = (work_df["close"].shift(-1) > work_df["close"]).astype(int)
    
    X = X.iloc[:-1]
    y = work_df["target"].iloc[:-1]
    return X, y

def train_and_save_model(stock_id: str = "2408"):
    """訓練 XGBoost，並將模型保存為 .pkl 實體檔案"""
    df = load_and_merge_data(stock_id)
    X, y = build_features_and_target(df)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    print(f"🧠 啟動抗過擬合 XGBoost 訓練！(訓練集: {len(X_train)} 天, 測試驗證集: {len(X_test)} 天)")
    
    # --- 💡 【Lesson 5 重點】防擬合參數調優 ---
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=3,          # 限制樹深為 3，防止死記考題
        learning_rate=0.03,   # 降低學習率，讓每一步學得更穩固
        subsample=0.8,        # 每次只隨機抽 80% 題目來練，增加泛化能力
        colsample_bytree=0.8, # 每次隨機抽 80% 特徵來建樹
        random_state=42,
        eval_metric="logloss"
    )
    
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred) * 100
    print(f"🎯 驗證集預測勝率：【 {test_acc:.1f}% 】\n")
    
    # --- 💾 【Lesson 5 新增】將模型與特徵名稱一起封裝存檔 ---
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_payload = {
        "model": model,
        "feature_names": list(X.columns),
        "stock_id": stock_id,
        "accuracy": round(test_acc, 2)
    }
    joblib.dump(model_payload, MODEL_PATH)
    print(f"💾 🎉 恭喜！模型大腦成功封裝保存至：[{MODEL_PATH}]")
    print(f"💡 未來每日排程將直接讀取此檔案，不需再重新訓練！")

if __name__ == "__main__":
    train_and_save_model("2408")