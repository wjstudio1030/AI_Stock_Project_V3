# scripts/fetch_whales.py
"""
AI Stock V3 - 集保大戶籌碼抓取與替代運算模組 (零成本突破版)
為解決官方股權分散表需付費(HTTP 400)的問題，
本模組依循專案「妥協與未來」架構，使用免費的【三大法人+融資融券】
合成大戶與散戶的每週籌碼消長指標，並寫入 SQLite 資料庫！
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
from db_manager import upsert_dataframe
from config import FINMIND_API_URL, FINMIND_TOKEN

def get_whales_data_free(stock_id: str = "2408", lookback_days: int = 365) -> pd.DataFrame:
    """
    以三大法人(大戶)與融資融券(散戶)的免費資料，合成每週大戶與散戶籌碼消長！
    """
    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    
    print(f"📡 正在以零成本方案計算 [{stock_id}] 從 {start_date} 到 {end_date} 的大戶籌碼...")
    
    # 1. 抓取免費的三大法人買賣超 (大戶特徵)
    inst_params = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    if FINMIND_TOKEN:
        inst_params["token"] = FINMIND_TOKEN
        
    resp_inst = requests.get(FINMIND_API_URL, params=inst_params, timeout=30)
    resp_inst.raise_for_status()
    inst_data = resp_inst.json().get("data", [])
    
    # 2. 抓取免費的融資融券 (散戶特徵)
    margin_params = {
        "dataset": "TaiwanStockMarginPurchaseShortSale",
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    if FINMIND_TOKEN:
        margin_params["token"] = FINMIND_TOKEN
        
    resp_margin = requests.get(FINMIND_API_URL, params=margin_params, timeout=30)
    resp_margin.raise_for_status()
    margin_data = resp_margin.json().get("data", [])
    
    if not inst_data or not margin_data:
        print("⚠️ 抓取法人或信用交易資料失敗。")
        return pd.DataFrame()
        
    # --- 資料清理與對齊 ---
    df_inst = pd.DataFrame(inst_data)
    df_inst["net_buy"] = pd.to_numeric(df_inst["buy"], errors="coerce") - pd.to_numeric(df_inst["sell"], errors="coerce")
    # 把三大法人按日加總
    daily_inst = df_inst.groupby("date")["net_buy"].sum().reset_index()
    daily_inst["date"] = pd.to_datetime(daily_inst["date"])
    
    df_margin = pd.DataFrame(margin_data)
    df_margin = df_margin.rename(columns={"MarginPurchaseTodayBalance": "margin_balance"})
    df_margin["margin_balance"] = pd.to_numeric(df_margin["margin_balance"], errors="coerce")
    df_margin["date"] = pd.to_datetime(df_margin["date"])
    
    # 合併每日資料
    merged = pd.merge(daily_inst, df_margin[["date", "margin_balance"]], on="date", how="inner")
    merged = merged.sort_values("date").set_index("date")
    
    # --- 依「週(W-FRI)」重採樣，合成週報表 ---
    weekly = merged.resample("W-FRI").agg({
        "net_buy": "sum",          # 該週法人累積買賣超
        "margin_balance": "last"   # 週五融資餘額
    }).dropna().reset_index()
    
    # 為了轉換成易讀的比例，以南亞科約 310 萬張總股本為基礎模擬持股消長特徵
    base_whale_pct = 55.0  # 基準大戶比例 55%
    base_retail_pct = 25.0 # 基準散戶比例 25%
    
    weekly_records = []
    cum_inst = 0
    
    for _, row in weekly.iterrows():
        date_str = row["date"].strftime("%Y-%m-%d")
        inst_net_shares = row["net_buy"] / 1000  # 轉為張數
        cum_inst += inst_net_shares
        
        # 依法人累積買賣微調大戶特徵
        whale_pct = round(base_whale_pct + (cum_inst / 3100000 * 100 * 5), 2)
        # 依融資餘額微調散戶特徵
        retail_pct = round(base_retail_pct + (row["margin_balance"] / 3100000 * 100 * 2), 2)
        
        # 產生自動量化籌碼評語
        if inst_net_shares > 5000:
            comment = "🔥 土洋同買(大戶強力進貨)"
        elif inst_net_shares < -5000:
            comment = "⚠️ 法人連賣(大戶減持)"
        elif row["margin_balance"] > 50000:
            comment = "🐑 融資偏高(散戶籌碼較亂)"
        else:
            comment = "⚖️ 籌碼中性穩定"
            
        weekly_records.append({
            "stock_id": stock_id,
            "date": date_str,
            "whale_pct": whale_pct,
            "retail_pct": retail_pct,
            "total_holders": int(row["margin_balance"]), # 以融資張數作為觀測基準
            "comment": comment
        })
        
    result_df = pd.DataFrame(weekly_records)
    print(f"✨ 成功合成 {len(result_df)} 週的大戶與散戶籌碼消長特徵！")
    return result_df

if __name__ == "__main__":
    whales_df = get_whales_data_free("2408", lookback_days=365)
    
    if not whales_df.empty:
        upsert_dataframe(whales_df, "weekly_whales")
        print("🎉 恭喜！零成本大戶籌碼特徵已經永久寫入 SQLite 資料庫！")