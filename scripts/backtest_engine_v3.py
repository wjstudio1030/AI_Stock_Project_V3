# scripts/backtest_engine_v3.py
"""
AI Stock V3 - 量化回測引擎 (Backtesting Engine)
模擬 100 萬本金在台股真實交易摩擦成本 (證交稅 0.3% + 手續費 0.1425%*2) 下，
對比【舊版 V2 技術指標策略】與【V3 XGBoost AI 預測策略】的真實績效！
"""

import os
import sqlite3
import joblib
import pandas as pd
import numpy as np
from db_manager import get_db_connection

# 檔案路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MODEL_PATH = os.path.join(REPO_ROOT, "data_db", "xgb_nanya_model.pkl")

# 台股真實交易成本設定
TAX_RATE = 0.0030          # 證交稅 0.3% (賣出時收取)
FEE_RATE = 0.001425        # 券商手續費 0.1425% (買賣皆收，此處設為嚴格無折讓)
HOLD_DAYS = 5              # 預設固定持有天數 (波段短線)

def load_backtest_data(stock_id: str = "2408") -> pd.DataFrame:
    """從 SQLite 載入歷史資料並準備特徵"""
    conn = get_db_connection()
    df_price = pd.read_sql(f"SELECT * FROM daily_price WHERE stock_id = '{stock_id}' ORDER BY date", conn)
    df_chips = pd.read_sql(f"SELECT * FROM institutional_chips WHERE stock_id = '{stock_id}' ORDER BY date", conn)
    df_whales = pd.read_sql(f"SELECT * FROM weekly_whales WHERE stock_id = '{stock_id}' ORDER BY date", conn)
    df_dram = pd.read_sql("SELECT * FROM dram_spot_price ORDER BY date", conn)
    conn.close()
    
    if df_price.empty:
        raise ValueError(f"❌ 找不到 [{stock_id}] 的資料，請先執行 build_data.py！")
        
    # 合併多維度特徵
    df = pd.merge(df_price, df_chips.drop(columns=["stock_id"], errors="ignore"), on="date", how="left") if not df_chips.empty else df_price.copy()
    if not df_whales.empty:
        df = pd.merge(df, df_whales[["date", "whale_pct"]], on="date", how="left")
        df["whale_pct"] = df["whale_pct"].ffill().fillna(55.0)
    else:
        df["whale_pct"] = 55.0
        
    if not df_dram.empty:
        df = pd.merge(df, df_dram[["date", "ddr4_8gb_price", "daily_change_pct"]], on="date", how="left")
        df["ddr4_8gb_price"] = df["ddr4_8gb_price"].ffill().fillna(1.75)
        df.rename(columns={"daily_change_pct": "dram_change_pct"}, inplace=True)
        df["dram_change_pct"] = df["dram_change_pct"].ffill().fillna(0)
    else:
        df["ddr4_8gb_price"] = 1.75
        df["dram_change_pct"] = 0
        
    df = df.ffill().fillna(0)
    
    # 衍生特徵
    df["ma20"] = df["ma20"].replace(0, np.nan)
    df["bias_ma20"] = ((df["close"] - df["ma20"]) / df["ma20"]) * 100
    df["ret_3d"] = df["close"].pct_change(3) * 100
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0)
    return df

def simulate_trade(df: pd.DataFrame, signal_series: pd.Series, strategy_name: str, initial_capital: float = 1000000.0):
    """
    通用交易模擬器：依據進場訊號，持有 HOLD_DAYS 天後平倉，計算真實淨利
    """
    capital = initial_capital
    trades = []
    
    # 為了避免重複進場，用常數記錄目前是否持有部位
    in_position = False
    buy_day_idx = 0
    buy_price = 0.0
    
    for i in range(len(df) - HOLD_DAYS):
        # 如果目前空手，且當天出現買進訊號 -> 以隔天開盤價或當天收盤價買進 (這裡採取嚴格的當天收盤價進場)
        if not in_position and signal_series.iloc[i]:
            in_position = True
            buy_day_idx = i
            buy_price = df["close"].iloc[i]
            
        # 如果持有部位，且達到固定持有天數 -> 賣出平倉
        elif in_position and (i - buy_day_idx == HOLD_DAYS):
            sell_price = df["close"].iloc[i]
            
            # --- 真實交易摩擦成本計算 ---
            # 總買進成本 = 股價 * (1 + 手續費)
            cost_buy = buy_price * (1 + FEE_RATE)
            # 總賣出收入 = 股價 * (1 - 手續費 - 證交稅)
            rev_sell = sell_price * (1 - FEE_RATE - TAX_RATE)
            
            # 單筆交易報酬率 %
            net_return_pct = ((rev_sell - cost_buy) / cost_buy) * 100
            net_profit = capital * (net_return_pct / 100)
            capital += net_profit
            
            trades.append({
                "buy_date": df["date"].iloc[buy_day_idx],
                "sell_date": df["date"].iloc[i],
                "buy_price": round(buy_price, 2),
                "sell_price": round(sell_price, 2),
                "net_return_pct": round(net_return_pct, 2),
                "net_profit": round(net_profit, 0)
            })
            in_position = False
            
    # --- 結算報表 ---
    df_trades = pd.DataFrame(trades)
    total_trades = len(df_trades)
    
    if total_trades == 0:
        print(f"⚠️ 【 {strategy_name} 】：在測試期間內從未觸發任何進場訊號！")
        return None
        
    win_trades = len(df_trades[df_trades["net_return_pct"] > 0])
    win_rate = (win_trades / total_trades) * 100
    total_return_pct = ((capital - initial_capital) / initial_capital) * 100
    
    print(f"📈 【 {strategy_name} 】 回測結算報告")
    print(f"   ▫ 初始本金： {initial_capital:,.0f} 元  ➔  最終淨值： {capital:,.0f} 元")
    print(f"   ▫ 總報酬率： 【 {total_return_pct:+.2f}% 】 | 總交易次數： {total_trades} 次")
    print(f"   ▫ 真實勝率： 【 {win_rate:.1f}% 】 (已扣除 0.585% 稅費摩擦成本)")
    print("-" * 55)
    return df_trades

def run_backtest_showdown(stock_id: str = "2408"):
    """執行雙策略擂台對決"""
    df = load_backtest_data(stock_id)
    
    # 為了測試真實性，我們只取「最近 1 年 (約 250 個交易日)」來做近期的實戰驗證
    test_df = df.tail(250).reset_index(drop=True)
    print(f"⚔️ 啟動 [{stock_id} 南亞科] 雙策略回測大擂台！")
    print(f"📅 回測期間： {test_df['date'].min()} ➔ {test_df['date'].max()} (共 {len(test_df)} 個交易日)\n")
    print("=" * 55)
    
    # =========================================================================
    # 🐢 策略 A：舊版 V2 技術指標策略 (黃金交叉 + KD<20 + 趨勢向上)
    # =========================================================================
    # 模擬上一筆 K 數值與均線趨勢
    k_prev = test_df["k_val"].shift(1)
    d_prev = test_df["d_val"].shift(1)
    ma60_prev = test_df["ma60"].shift(1)
    
    cond1 = (k_prev <= 20)
    cond2 = (k_prev < d_prev) & (test_df["k_val"] > test_df["d_val"]) # 黃金交叉
    cond3 = (test_df["close"] > test_df["ma60"]) & (test_df["ma60"] > ma60_prev)
    
    # 三條件同時滿足即為「黃金買點」
    signal_old = (cond1 & cond2 & cond3)
    simulate_trade(test_df, signal_old, "策略 A：舊版 V2 技術指標黃金買點")
    
    # =========================================================================
    # 🤖 策略 B：升級 V3 XGBoost AI 預測策略
    # =========================================================================
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"❌ 找不到 AI 模型 [{MODEL_PATH}]！請先執行 train_xgb_v3.py 存檔。")
        
    payload = joblib.load(MODEL_PATH)
    model = payload["model"]
    feature_names = payload["feature_names"]
    
    # 建立模型所需的特徵表
    feature_map = {
        "k_val": "1. 技術_KD值(K)", "d_val": "2. 技術_KD值(D)", "bias_ma20": "3. 技術_月線乖離率%",
        "ret_3d": "4. 技術_近3日動能%", "foreign_net": "5. 籌碼_外資買賣超(張)",
        "trust_net": "6. 籌碼_投信買賣超(張)", "margin_change": "7. 散戶_融資增減(張)",
        "whale_pct": "8. 大戶_集保持股比例%", "dram_change_pct": "9. 產業_DRAM現貨單日漲跌%"
    }
    
    valid_cols = [c for c in feature_map.keys() if c in test_df.columns]
    X_test = test_df[valid_cols].rename(columns=feature_map)
    X_test = X_test.reindex(columns=feature_names, fill_value=0)
    
    # 預測每日上漲機率
    probs = model.predict_proba(X_test)[:, 1]
    
    # 策略進場條件：AI 預測上漲機率 >= 65%，且當日外資沒有狂賣超 (> -3000張)
    signal_ai = pd.Series((probs >= 0.65) & (test_df["foreign_net"] > -3000))
    simulate_trade(test_df, signal_ai, "策略 B：V3 XGBoost AI 高勝率波段")
    
    print("=" * 55)
    print("💡 擂台總結：真實的量化交易不能只看進場次數，更要看扣除手續費與稅金後的【真實淨利】與【勝率】！")

if __name__ == "__main__":
    run_backtest_showdown("2408")