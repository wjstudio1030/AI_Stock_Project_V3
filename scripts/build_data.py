# scripts/build_data.py
"""
給 GitHub Actions 排程執行的主程式。
流程: 抓股價 -> 算均線/RSI/KD -> 產生投資建議 -> 輸出成 docs/data/{stock_id}.json 給前端讀取, 並匯出 CSV。

用法:
    python build_data.py                # 抓 config.py 裡 STOCK_LIST 全部
    python build_data.py 2330 2317      # 只抓指定股票代號
"""

import sys
import os
import json
import math
import pandas as pd
from datetime import datetime, timedelta, timezone

# 確保無論從哪個目錄執行,都能正確定位到 repo 根目錄下的 docs/data
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

from config import (
    STOCK_LIST, LOOKBACK_DAYS, RSI_PERIODS, MA_WINDOWS, FUNDAMENTALS_QUARTERS,
    ANALYSIS_LOOKBACK_YEARS, NEWS_LOOKBACK_DAYS, NEWS_MAX_ARTICLES, NEWS_TODAY_MAX_ARTICLES,
    ANOMALY_STREAK_THRESHOLD, NEWS_SENTIMENT_MIN_FOR_ML, OUTPUT_DIR,
)
from data_fetcher import (
    get_stock_price, get_institutional_investors, get_margin_trading,
    get_valuation_ratios, get_financial_statements, get_balance_sheet, get_cash_flow,
    get_stock_names, get_stock_news, get_market_index,
)
from indicators import add_moving_averages, add_rsi_columns
from analysis import generate_trend_narrative, compute_next_day_probability, compute_streak, get_latest_state
from ml_model import train_and_predict as ml_train_and_predict
from news_analysis import summarize_news
from news_sentiment_log import (
    load_log as news_sentiment_load_log,
    save_log as news_sentiment_save_log,
    add_daily_entry as news_sentiment_add_daily_entry,
)
from prediction_tracker import (
    load_log, save_log, resolve_pending, add_new_prediction, compute_track_record, analyze_errors,
)
from db_manager import upsert_dataframe, get_db_connection, init_database

OUTPUT_DIR_ABS = os.path.join(REPO_ROOT, OUTPUT_DIR)


def _clean(value):
    """NaN / None 統一轉成 JSON 合法的 null"""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _series_from_df(df, value_cols: list) -> dict:
    """把 dataframe(需有 date 欄位)轉成 {col: [{time, value}, ...]} 格式,自動跳過NaN"""
    series = {col: [] for col in value_cols}
    for _, row in df.iterrows():
        t = row["date"].strftime("%Y-%m-%d")
        for col in value_cols:
            v = _clean(row[col])
            if v is not None:
                series[col].append({"time": t, "value": v})
    return series


def _load_json_if_exists(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  讀取 JSON 失敗 {path}: {exc}")
        return None


def _load_v3_features(stock_id: str) -> dict:
    """讀取已生成的模型、AI、風險與產業資料，供前端 JSON 使用。"""
    mapping = {
        "ai_report": f"{stock_id}_ai_report.json",
        "grid_strategy": f"{stock_id}_grid_strategy.json",
        "ai_news_sentiment": f"{stock_id}_news_ai_sentiment.json",
        "xgb_prediction": f"{stock_id}_xgb_prediction.json",
        "xgb_metrics": f"{stock_id}_xgb_metrics.json",
        "risk_alert": f"{stock_id}_risk_alert.json",
        "ultimate_judge": f"{stock_id}_ultimate_judge.json",
        "backtest": f"{stock_id}_backtest.json",
    }
    result = {}
    for key, filename in mapping.items():
        value = _load_json_if_exists(os.path.join(OUTPUT_DIR_ABS, filename))
        if value is not None:
            result[key] = value

    conn = get_db_connection()
    try:
        df_dram = pd.read_sql_query(
            "SELECT date, ddr4_8gb_price, ddr4_4gb_price, daily_change_pct, source "
            "FROM dram_spot_price ORDER BY date DESC LIMIT 250",
            conn,
        )
        df_proxy = pd.read_sql_query(
            "SELECT date, position_proxy_score, retail_proxy_score, comment, source "
            "FROM weekly_position_proxy WHERE stock_id = ? ORDER BY date DESC LIMIT 52",
            conn,
            params=(stock_id,),
        )
    finally:
        conn.close()

    if not df_dram.empty:
        df_dram["date"] = pd.to_datetime(df_dram["date"], errors="coerce")
        df_dram = df_dram.dropna(subset=["date"]).sort_values("date")
        result["dram_series"] = _series_from_df(df_dram, ["ddr4_8gb_price", "ddr4_4gb_price", "daily_change_pct"])
        result["dram_source"] = str(df_dram.iloc[-1].get("source", ""))
    if not df_proxy.empty:
        df_proxy["date"] = pd.to_datetime(df_proxy["date"], errors="coerce")
        df_proxy = df_proxy.dropna(subset=["date"]).sort_values("date")
        result["position_proxy_series"] = _series_from_df(
            df_proxy, ["position_proxy_score", "retail_proxy_score"]
        )
        result["position_proxy_disclaimer"] = "籌碼代理分數，不是集保持股比例。"
    return result


def add_kd_and_signals(df: pd.DataFrame) -> pd.DataFrame:
    """新增 KD 指標與新手投資建議的條件判斷"""
    df = df.copy()
    
    # 1. 計算 9日 RSV, K值與 D值
    min_low_9 = df['low'].rolling(window=9).min()
    max_high_9 = df['high'].rolling(window=9).max()
    df['RSV'] = 100 * (df['close'] - min_low_9) / (max_high_9 - min_low_9)
    df['K'] = df['RSV'].ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    
    # 2. 準備昨日數據
    df['昨日K'] = df['K'].shift(1)
    df['昨日D'] = df['D'].shift(1)
    if 'MA60' not in df.columns:
        df['MA60'] = df['close'].rolling(window=60).mean()
    df['昨日MA60'] = df['MA60'].shift(1)
    
    # 3. 建立技術條件判斷
    df['KD落入20以下'] = (df['昨日K'] <= 20).fillna(False)
    df['出現黃金交叉'] = ((df['昨日K'] < df['昨日D']) & (df['K'] > df['D'])).fillna(False)
    df['趨勢向上非鈍化'] = ((df['close'] > df['MA60']) & (df['MA60'] > df['昨日MA60'])).fillna(False)
    
    df['符合條件數'] = df['KD落入20以下'].astype(int) + \
                    df['出現黃金交叉'].astype(int) + \
                    df['趨勢向上非鈍化'].astype(int)
                    
    return df


def build_one(stock_id: str, token: str = None, stock_name: str = None, market_df: pd.DataFrame = None) -> dict:
    end_date = datetime.today().strftime("%Y-%m-%d")

    analysis_start_date = (datetime.today() - timedelta(days=int(ANALYSIS_LOOKBACK_YEARS * 365))).strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=int(LOOKBACK_DAYS * 1.6))).strftime("%Y-%m-%d")

    full_df = get_stock_price(stock_id, analysis_start_date, end_date, token=token)
    full_df = add_moving_averages(full_df, windows=MA_WINDOWS)
    full_df = add_rsi_columns(full_df, periods=RSI_PERIODS)
    
    # 新增 KD 與投資建議欄位
    full_df = add_kd_and_signals(full_df)

    # 計算布林通道上下軌
    full_df['BB_std'] = full_df['close'].rolling(window=20).std()
    full_df['BB_upper'] = full_df['MA20'] + (full_df['BB_std'] * 2)
    full_df['BB_lower'] = full_df['MA20'] - (full_df['BB_std'] * 2)

    # 只保留最近 LOOKBACK_DAYS 個交易日給圖表顯示,避免檔案太大
    df = full_df.tail(LOOKBACK_DAYS).reset_index(drop=True)

    price = []
    volume = []
    ma_series = {f"MA{w}": [] for w in MA_WINDOWS}
    rsi_series = {f"RSI{p}": [] for p in RSI_PERIODS}
    kd_series = {"K": [], "D": []}

    for _, row in df.iterrows():
        t = row["date"].strftime("%Y-%m-%d")
        price.append({
            "time": t,
            "open": _clean(row["open"]),
            "high": _clean(row["high"]),
            "low": _clean(row["low"]),
            "close": _clean(row["close"]),
        })
        volume.append({"time": t, "value": _clean(row["volume"])})

        for w in MA_WINDOWS:
            v = _clean(row[f"MA{w}"])
            if v is not None:
                ma_series[f"MA{w}"].append({"time": t, "value": v})

        for p in RSI_PERIODS:
            v = _clean(row[f"RSI{p}"])
            if v is not None:
                rsi_series[f"RSI{p}"].append({"time": t, "value": v})

        k_val = _clean(row.get("K"))
        d_val = _clean(row.get("D"))
        if k_val is not None:
            kd_series["K"].append({"time": t, "value": k_val})
        if d_val is not None:
            kd_series["D"].append({"time": t, "value": d_val})

    # ---------- 三大法人 ----------
    try:
        inst_full_df = get_institutional_investors(stock_id, analysis_start_date, end_date, token=token)
        for col in ["foreign_net", "trust_net", "dealer_net", "total_net"]:
            inst_full_df[col] = (inst_full_df[col] / 1000).round().astype(int)

        inst_df = inst_full_df[inst_full_df["date"] >= df["date"].min()].reset_index(drop=True)
        institutional = _series_from_df(inst_df, ["foreign_net", "trust_net", "dealer_net", "total_net"])

        anomalies = {}
        for key, label in [("foreign_net", "foreign"), ("trust_net", "trust"), ("dealer_net", "dealer")]:
            streak_info = compute_streak(inst_df[key].tolist())
            if streak_info["streak"] >= ANOMALY_STREAK_THRESHOLD:
                anomalies[label] = streak_info
        institutional["anomalies"] = anomalies
    except Exception as e:
        print(f"  三大法人資料抓取失敗({stock_id}): {e}")
        institutional = {"foreign_net": [], "trust_net": [], "dealer_net": [], "total_net": [], "anomalies": {}}
        inst_full_df = None

    # ---------- 財經新聞 ----------
    news_df = pd.DataFrame(columns=["date", "title", "source", "link"])
    try:
        news_end_date = end_date
        news_start_date = (datetime.today() - timedelta(days=NEWS_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        news_df = get_stock_news(stock_id, news_start_date, news_end_date, token=token)
        news = summarize_news(news_df, max_articles=NEWS_MAX_ARTICLES, today_max_articles=NEWS_TODAY_MAX_ARTICLES)
    except Exception as e:
        print(f"  財經新聞資料抓取失敗({stock_id}): {e}")
        news = {"total": 0, "positive_count": 0, "negative_count": 0, "neutral_count": 0, "articles": []}

    # ---------- 新聞情緒每日累積記錄 ----------
    # 只記錄最新交易日當天的新聞，不再把近 7 天重疊新聞包成「每日」分數。
    try:
        sentiment_log_path = os.path.join(OUTPUT_DIR_ABS, f"{stock_id}_news_sentiment.json")
        sentiment_log = news_sentiment_load_log(sentiment_log_path)
        latest_trade_date = full_df["date"].max().strftime("%Y-%m-%d")
        if not news_df.empty:
            daily_news_df = news_df[news_df["date"].dt.strftime("%Y-%m-%d") == latest_trade_date]
            daily_news = summarize_news(
                daily_news_df,
                max_articles=NEWS_TODAY_MAX_ARTICLES,
                today_max_articles=NEWS_TODAY_MAX_ARTICLES,
            ) if not daily_news_df.empty else {
                "total": 0, "positive_count": 0, "negative_count": 0,
                "neutral_count": 0, "articles": [],
            }
        else:
            daily_news = {"total": 0, "positive_count": 0, "negative_count": 0, "neutral_count": 0, "articles": []}
        existing_daily = next((entry for entry in sentiment_log if entry.get("date") == latest_trade_date), None)
        if daily_news.get("total", 0) > 0 or existing_daily is None:
            sentiment_log = news_sentiment_add_daily_entry(sentiment_log, latest_trade_date, daily_news)
            news_sentiment_save_log(sentiment_log_path, sentiment_log)
        else:
            print(f"  [新聞情緒] {latest_trade_date} 本次抓取為空，保留既有記錄")
        news["sentiment_history"] = sentiment_log[-90:]
        news["sentiment_history_total"] = len(sentiment_log)
        news["sentiment_log_method"] = "latest-trading-day-only"
    except Exception as e:
        print(f"  新聞情緒累積記錄失敗({stock_id}): {e}")
        sentiment_log = []
        news["sentiment_history"] = []
        news["sentiment_history_total"] = 0

    # ---------- 近期走向分析 + 隔日漲跌機率 ----------
    try:
        narrative = generate_trend_narrative(full_df)
    except Exception as e:
        print(f"  近期走向分析產生失敗({stock_id}): {e}")
        narrative = ""

    try:
        next_day = compute_next_day_probability(full_df)
    except Exception as e:
        print(f"  隔日漲跌機率統計失敗({stock_id}): {e}")
        next_day = {"up_pct": None, "down_pct": None, "sample_size": 0,
                    "match_level": "error", "state_label": "統計時發生錯誤"}

    # ---------- 預測準確率追蹤 ----------
    try:
        pred_log_path = os.path.join(OUTPUT_DIR_ABS, f"{stock_id}_predictions.json")
        pred_log = load_log(pred_log_path)
        pred_log = resolve_pending(pred_log, full_df[["date", "close"]])

        latest_date_str = full_df["date"].max().strftime("%Y-%m-%d")
        pred_log = add_new_prediction(pred_log, latest_date_str, next_day)

        save_log(pred_log_path, pred_log)
        track_record = compute_track_record(pred_log)
        track_record["error_analysis"] = analyze_errors(pred_log, sentiment_log=sentiment_log)
    except Exception as e:
        print(f"  預測準確率追蹤失敗({stock_id}): {e}")
        track_record = {"total_predictions": 0, "resolved_count": 0, "correct_count": 0,
                         "accuracy_pct": None, "recent": [], "error_analysis": None}

    next_day["track_record"] = track_record

    # ---------- 機器學習模型預測 ----------
    try:
        if len(sentiment_log) >= NEWS_SENTIMENT_MIN_FOR_ML:
            sentiment_df = pd.DataFrame(sentiment_log)
            sentiment_df["date"] = pd.to_datetime(sentiment_df["date"])
        else:
            sentiment_df = None
        ml_next_day = ml_train_and_predict(full_df, inst_df=inst_full_df, market_df=market_df, sentiment_df=sentiment_df)
    except Exception as e:
        print(f"  ML模型預測失敗({stock_id}): {e}")
        ml_next_day = {"up_pct": None, "down_pct": None, "sample_size": 0,
                        "state_label": "模型訓練失敗或資料不足"}

    try:
        ml_log_path = os.path.join(OUTPUT_DIR_ABS, f"{stock_id}_predictions_ml.json")
        ml_log = load_log(ml_log_path)
        ml_log = resolve_pending(ml_log, full_df[["date", "close"]])

        latest_date_str = full_df["date"].max().strftime("%Y-%m-%d")
        ml_log = add_new_prediction(ml_log, latest_date_str, ml_next_day)

        save_log(ml_log_path, ml_log)
        ml_track_record = compute_track_record(ml_log)
        ml_track_record["error_analysis"] = analyze_errors(ml_log, sentiment_log=sentiment_log)
    except Exception as e:
        print(f"  ML預測準確率追蹤失敗({stock_id}): {e}")
        ml_track_record = {"total_predictions": 0, "resolved_count": 0, "correct_count": 0,
                            "accuracy_pct": None, "recent": [], "error_analysis": None}

    ml_next_day["track_record"] = ml_track_record
    analysis = {"narrative": narrative, "next_day": next_day, "next_day_ml": ml_next_day}

    # ---------- 融資融券 ----------
    try:
        margin_df = get_margin_trading(stock_id, start_date, end_date, token=token)
        margin_df = margin_df[margin_df["date"] >= df["date"].min()].reset_index(drop=True)
        margin = _series_from_df(
            margin_df,
            ["margin_balance", "margin_buy", "margin_sell", "short_balance", "short_buy", "short_sell"],
        )
    except Exception as e:
        print(f"  融資融券資料抓取失敗({stock_id}): {e}")
        margin = {k: [] for k in
                  ["margin_balance", "margin_buy", "margin_sell", "short_balance", "short_buy", "short_sell"]}
        margin_df = None

    # ---------- 本益比 / 淨值比 / 殖利率 ----------
    try:
        val_df = get_valuation_ratios(stock_id, start_date, end_date, token=token)
        val_df = val_df[val_df["date"] >= df["date"].min()].reset_index(drop=True)
        valuation = _series_from_df(val_df, ["PER", "PBR", "dividend_yield"])
    except Exception as e:
        print(f"  本益比/淨值比資料抓取失敗({stock_id}): {e}")
        valuation = {"PER": [], "PBR": [], "dividend_yield": []}

    # ---------- 基本面季報 ----------
    try:
        fund_start_date = (datetime.today() - timedelta(days=3 * 365)).strftime("%Y-%m-%d")

        fin_df = get_financial_statements(stock_id, fund_start_date, end_date, token=token)
        bs_df = get_balance_sheet(stock_id, fund_start_date, end_date, token=token)
        cf_df = get_cash_flow(stock_id, fund_start_date, end_date, token=token)

        merged = fin_df.merge(bs_df, on="date", how="inner").merge(cf_df, on="date", how="left")
        merged["roe"] = merged["net_income"] / merged["equity"] * 100
        merged["roa"] = merged["net_income"] / merged["total_assets"] * 100

        merged["revenue_yi"] = merged["revenue"] / 1e8
        merged["operating_cash_flow_yi"] = merged["operating_cash_flow"] / 1e8

        merged = merged.sort_values("date").tail(FUNDAMENTALS_QUARTERS).reset_index(drop=True)

        quarters = []
        for _, row in merged.iterrows():
            quarters.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "eps": _clean(row.get("eps")),
                "revenue_yi": _clean(row.get("revenue_yi")),
                "gross_margin": _clean(row.get("gross_margin")),
                "operating_margin": _clean(row.get("operating_margin")),
                "roe": _clean(row.get("roe")),
                "roa": _clean(row.get("roa")),
                "debt_ratio": _clean(row.get("debt_ratio")),
                "operating_cash_flow_yi": _clean(row.get("operating_cash_flow_yi")),
            })
        fundamentals = {"quarters": quarters}
    except Exception as e:
        print(f"  基本面季報資料抓取失敗({stock_id}): {e}")
        fundamentals = {"quarters": []}

    # ---------- 總覽 ----------
    try:
        latest_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) >= 2 else latest_row
        prev_close = prev_row["close"] if len(df) >= 2 else None
        change = None if prev_close is None else latest_row["close"] - prev_close
        change_pct = None if not prev_close else (change / prev_close * 100)

        state = get_latest_state(full_df)

        def _last_value(series_list):
            return series_list[-1]["value"] if series_list else None

        overview = {
            "close": _clean(latest_row["close"]),
            "change": _clean(change),
            "change_pct": _clean(round(change_pct, 2)) if change_pct is not None else None,
            "per": _clean(_last_value(valuation.get("PER", []))),
            "pbr": _clean(_last_value(valuation.get("PBR", []))),
            "rsi14": state["rsi14"],
            "rsi_state": state["rsi_state"],
            "ma_state": state["ma_state"],
            "foreign_net_today": _clean(_last_value(institutional.get("foreign_net", []))),
            "trust_net_today": _clean(_last_value(institutional.get("trust_net", []))),
            "dealer_net_today": _clean(_last_value(institutional.get("dealer_net", []))),
            "next_day_up_pct": analysis["next_day"].get("up_pct"),
            "next_day_down_pct": analysis["next_day"].get("down_pct"),
            "news_positive": news.get("positive_count", 0),
            "news_negative": news.get("negative_count", 0),
            "news_neutral": news.get("neutral_count", 0),
            "conditions": {
                "kd_under_20": bool(latest_row.get("KD落入20以下", False)),
                "kd_golden_cross": bool(latest_row.get("出現黃金交叉", False)),
                "ma60_uptrend": bool(latest_row.get("趨勢向上非鈍化", False)),
                # 布林跌破下軌 與 RSI超賣 判斷 
                "bb_lower_breakout": bool(latest_row.get("close", 0) < latest_row.get("BB_lower", 0)), 
                "rsi_oversold": bool(latest_row.get("RSI14", 50) < 30),
                "details": {
                    "k_today": _clean(latest_row.get("K")),
                    "d_today": _clean(latest_row.get("D")),
                    "k_yest": _clean(prev_row.get("K")),
                    "d_yest": _clean(prev_row.get("D")),
                    "close": _clean(latest_row.get("close")),
                    "ma60_today": _clean(latest_row.get("MA60")),
                    "ma60_yest": _clean(prev_row.get("MA60")),
                    # 新增布林上下軌 與 RSI 數值給前端 
                    "bb_upper": _clean(latest_row.get("BB_upper")),
                    "bb_lower": _clean(latest_row.get("BB_lower")),
                    "rsi14_today": _clean(latest_row.get("RSI14")),
                }
            }
        }
    except Exception as e:
        print(f"  總覽資料整理失敗({stock_id}): {e}")
        overview = {}

# ---------- 數據整合與 CSV 匯出 & V3 資料庫寫入 ----------
    try:
        export_df = full_df.copy().set_index("date")
        
        if inst_full_df is not None and not inst_full_df.empty:
            inst_export = inst_full_df.copy().set_index("date")
            inst_export = inst_export.rename(columns={
                "foreign_net": "外資",
                "trust_net": "投信",
                "dealer_net": "自營商",
                "total_net": "三大法人合計(張)"
            })
            export_df = export_df.join(inst_export[["外資", "投信", "自營商", "三大法人合計(張)"]], how="left")
        else:
            export_df["外資"] = 0
            export_df["投信"] = 0
            export_df["自營商"] = 0
            export_df["三大法人合計(張)"] = 0
            
        if margin_df is not None and not margin_df.empty:
            margin_export = margin_df.copy().set_index("date")
            margin_export["融資增減(張)"] = (margin_export["margin_buy"] - margin_export["margin_sell"]) / 1000
            export_df = export_df.join(margin_export[["融資增減(張)"]], how="left")
        else:
            export_df["融資增減(張)"] = 0

        export_cols = [
            'close', 'volume', '外資', '投信', '自營商', '三大法人合計(張)', '融資增減(張)',
            'K', 'D', 'RSI14', 'BB_upper', 'BB_lower', 
            'KD落入20以下', '出現黃金交叉', '趨勢向上非鈍化'
        ]
        export_cols = [c for c in export_cols if c in export_df.columns]
        
        final_export_df = export_df[export_cols].round(2)
        csv_path = os.path.join(OUTPUT_DIR_ABS, f"{stock_id}_unified.csv")
        final_export_df.to_csv(csv_path, encoding="utf-8-sig")
        print(f"  已匯出 CSV: {csv_path}")

        # =====================================================================
        # 👇 【V3 新增】無痛無縫升級！直接把歷史數據寫入 SQLite 資料庫
        # =====================================================================
        print(f"  [SQLite] 正在將 [{stock_id}] 寫入 V3 資料庫...")
        
        # 1. 準備寫入 daily_price (日 K 線與指標表)
        db_price_df = full_df.copy()
        db_price_df["stock_id"] = stock_id
        db_price_df["date"] = db_price_df["date"].dt.strftime("%Y-%m-%d")
        
        # 對齊資料庫欄位
        price_cols_map = {
            "stock_id": "stock_id", "date": "date", "open": "open", "high": "high",
            "low": "low", "close": "close", "volume": "volume",
            "K": "k_val", "D": "d_val",
            "MA5": "ma5", "MA10": "ma10", "MA20": "ma20", "MA60": "ma60"
        }
        # 只取存在的欄位並重命名
        avail_cols = [c for c in price_cols_map.keys() if c in db_price_df.columns]
        db_price_to_save = db_price_df[avail_cols].rename(columns=price_cols_map)
        upsert_dataframe(db_price_to_save, "daily_price")

        # 2. 準備寫入 institutional_chips (籌碼與信用交易表)
        if inst_full_df is not None and not inst_full_df.empty:
            db_chips_df = inst_full_df.copy()
            db_chips_df["stock_id"] = stock_id
            db_chips_df["date"] = pd.to_datetime(db_chips_df["date"]).dt.strftime("%Y-%m-%d")
            
            # 如果有融資融券，併入籌碼表一起存
            if margin_df is not None and not margin_df.empty:
                m_temp = margin_df.copy()
                m_temp["date"] = pd.to_datetime(m_temp["date"]).dt.strftime("%Y-%m-%d")
                m_temp["margin_change"] = (m_temp["margin_buy"] - m_temp["margin_sell"]) / 1000
                m_temp["margin_balance"] = m_temp["margin_balance"] / 1000
                m_temp["short_balance"] = m_temp["short_balance"] / 1000
                db_chips_df = db_chips_df.merge(
                    m_temp[["date", "margin_balance", "margin_change", "short_balance"]],
                    on="date", how="left"
                )
            else:
                db_chips_df["margin_balance"] = None
                db_chips_df["margin_change"] = None
                db_chips_df["short_balance"] = None
                
            chips_cols = [
                "stock_id", "date", "foreign_net", "trust_net", "dealer_net",
                "total_net", "margin_balance", "margin_change", "short_balance"
            ]
            avail_chips_cols = [c for c in chips_cols if c in db_chips_df.columns]
            upsert_dataframe(db_chips_df[avail_chips_cols], "institutional_chips")
        # =====================================================================

    except Exception as e:
        raise RuntimeError(f"CSV 匯出或資料庫寫入失敗({stock_id}): {e}") from e

    v3_data = _load_v3_features(stock_id)

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "price": price,
        "volume": volume,
        "ma": ma_series,
        "rsi": rsi_series,
        "kd": kd_series,
        "institutional": institutional,
        "margin": margin,
        "valuation": valuation,
        "fundamentals": fundamentals,
        "analysis": analysis,
        "news": news,
        "overview": overview,
        "v3_features": v3_data,
    }


def refresh_v3_only(stock_ids: list[str]) -> None:
    """不重新呼叫外部 API，只把後續模型/AI 產物注入既有前端 JSON。"""
    refreshed = []
    for stock_id in stock_ids:
        out_path = os.path.join(OUTPUT_DIR_ABS, f"{stock_id}.json")
        if not os.path.exists(out_path):
            print(f"⚠️ [{stock_id}] 尚無基礎 JSON，略過進階資料刷新")
            continue
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["v3_features"] = _load_v3_features(stock_id)
        data["enriched_at"] = datetime.now(timezone.utc).isoformat()
        temp_path = out_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(temp_path, out_path)
        refreshed.append(stock_id)
        print(f"✅ [{stock_id}] 已刷新模型與 AI 前端資料")

    manifest_path = os.path.join(OUTPUT_DIR_ABS, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["enriched_at"] = datetime.now(timezone.utc).isoformat()
        temp_manifest_path = manifest_path + ".tmp"
        with open(temp_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        os.replace(temp_manifest_path, manifest_path)


def main():
    args = sys.argv[1:]
    refresh_only = "--refresh-v3-only" in args
    stock_ids = [arg for arg in args if not arg.startswith("--")] or STOCK_LIST
    init_database()
    os.makedirs(OUTPUT_DIR_ABS, exist_ok=True)

    if refresh_only:
        refresh_v3_only(stock_ids)
        return

    token = os.environ.get("FINMIND_TOKEN", "")
    try:
        name_map = get_stock_names(token=token)
        print(f"已取得股票名稱對照表，共 {len(name_map)} 檔")
    except Exception as e:
        print(f"股票名稱對照表抓取失敗: {e}")
        name_map = {}

    try:
        market_start_date = (datetime.today() - timedelta(days=int(ANALYSIS_LOOKBACK_YEARS * 365))).strftime("%Y-%m-%d")
        market_end_date = datetime.today().strftime("%Y-%m-%d")
        market_df = get_market_index(market_start_date, market_end_date, token=token)
        print(f"已取得大盤加權指數，共 {len(market_df)} 筆")
    except Exception as e:
        print(f"大盤加權指數抓取失敗，ML 會使用缺失旗標/0 值: {e}")
        market_df = None

    manifest = []
    manifest_names = {}
    failures = []
    for stock_id in stock_ids:
        print(f"抓取並計算 {stock_id} ...")
        stock_name = name_map.get(stock_id)
        try:
            data = build_one(stock_id, token=token, stock_name=stock_name, market_df=market_df)
        except Exception as e:
            failures.append(stock_id)
            print(f"❌ 跳過 {stock_id}: {e}")
            continue

        out_path = os.path.join(OUTPUT_DIR_ABS, f"{stock_id}.json")
        temp_path = out_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(temp_path, out_path)
        print(f"✅ 已輸出: {out_path} ({len(data['price'])} 筆)")
        manifest.append(stock_id)
        manifest_names[stock_id] = stock_name

    manifest_path = os.path.join(OUTPUT_DIR_ABS, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "stocks": manifest,
            "stock_names": manifest_names,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "news_lookback_days": NEWS_LOOKBACK_DAYS,
        }, f, ensure_ascii=False)
    print(f"已輸出股票清單索引: {manifest_path}")
    if failures and len(failures) == len(stock_ids):
        raise RuntimeError("所有股票資料建置皆失敗")


if __name__ == "__main__":
    main()
