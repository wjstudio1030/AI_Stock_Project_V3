# scripts/build_global_data.py
import yfinance as yf
import pandas as pd
import json
import os
import math
from datetime import datetime, timezone
from config import OUTPUT_DIR
from indicators import add_moving_averages, add_rsi_columns, add_kd_columns
from deep_translator import GoogleTranslator
from datetime import datetime

# 欲抓取的全球權值股清單
GLOBAL_STOCKS = {
    "^TWII": "台灣加權指數",  # 替換這行，改用最穩定的加權指數
    "^SOX": "費城半導體",
    "^IXIC": "那斯達克",
    "MU": "美光",
    "005930.KS": "三星",
    "000660.KS": "海力士"
}
OUTPUT_DIR_ABS = os.path.abspath(OUTPUT_DIR)

def _clean(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value

def classify_rsi(rsi_val):
    if pd.isna(rsi_val) or rsi_val is None:
        return "未知"
    if rsi_val >= 80: return "強勢(極度超買)"
    if rsi_val >= 70: return "超買"
    if rsi_val <= 20: return "弱勢(極度超賣)"
    if rsi_val <= 30: return "超賣"
    return "中性"

def classify_ma_trend(close, ma5, ma20, ma60):
    vals = [close, ma5, ma20, ma60]
    if any(pd.isna(v) for v in vals) or any(v is None for v in vals):
        return "盤整"
    if close > ma5 > ma20 > ma60:
        return "多頭排列"
    if close < ma5 < ma20 < ma60:
        return "空頭排列"
    return "盤整"

def build_global_stock(ticker: str, name: str):
    print(f"抓取全球股 {ticker} ({name})...")
    stock = yf.Ticker(ticker)
    df = stock.history(period="1y")
    
    if df.empty:
        raise ValueError(f"{ticker} 抓取不到歷史資料")

    df = df.reset_index()
    # 統一欄位名稱為小寫，相容前端
    # 統一欄位名稱為小寫，相容前端
    rename_map = {"Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close"}
    if "Volume" in df.columns:
        rename_map["Volume"] = "volume"
    df = df.rename(columns=rename_map)
    
    # 防呆：如果該指數沒有成交量，自動補上 0
    if "volume" not in df.columns:
        df["volume"] = 0

    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None) # 移除時區以便格式化

    # 套用共用的技術指標計算
    df = add_moving_averages(df, windows=[5, 10, 20, 60])
    df = add_rsi_columns(df, periods=[6, 14])
    df = add_kd_columns(df)  # 👇 這裡補上計算 KD 指標
    
    # 計算布林通道
    df['BB_std'] = df['close'].rolling(window=20).std()
    df['BB_upper'] = df['MA20'] + (df['BB_std'] * 2)
    df['BB_lower'] = df['MA20'] - (df['BB_std'] * 2)

    latest_row = df.iloc[-1]
    prev_row = df.iloc[-2] if len(df) >= 2 else latest_row
    change = latest_row["close"] - prev_row["close"]
    change_pct = (change / prev_row["close"]) * 100

    # 👇 這裡補上前端畫圖表需要的陣列資料 👇
    price_series = []
    ma_series = {"MA5": [], "MA10": [], "MA20": [], "MA60": []}
    rsi_series = {"RSI6": [], "RSI14": []}
    kd_series = {"K": [], "D": []}

    for _, row in df.iterrows():
        t = row["date"].strftime("%Y-%m-%d")
        # K線資料
        price_series.append({
            "time": t, "open": _clean(row["open"]), "high": _clean(row["high"]),
            "low": _clean(row["low"]), "close": _clean(row["close"])
        })
        # 均線資料
        for w in [5, 10, 20, 60]:
            v = _clean(row.get(f"MA{w}"))
            if v is not None: ma_series[f"MA{w}"].append({"time": t, "value": v})
        # RSI資料
        for p in [6, 14]:
            v = _clean(row.get(f"RSI{p}"))
            if v is not None: rsi_series[f"RSI{p}"].append({"time": t, "value": v})
        # KD資料
        k_val, d_val = _clean(row.get("K")), _clean(row.get("D"))
        if k_val is not None: kd_series["K"].append({"time": t, "value": k_val})
        if d_val is not None: kd_series["D"].append({"time": t, "value": d_val})

    # 抓取 Yahoo Finance 國際新聞並進行翻譯
    news_data = []
    try:
        raw_news = stock.news
        for item in raw_news[:5]:
            # 👇 核心修復：兼容 Yahoo Finance 新版 API 的嵌套結構 (content)
            content = item.get("content", item)
            
            title_en = content.get("title", "")
            
            # 🛡️ 防呆機制：如果連英文標題都抓不到，代表這是一筆無效資料，直接跳過不顯示
            if not title_en:
                continue
                
            # 找連結 (新舊版欄位可能不同)
            link = content.get("link", "")
            if not link and isinstance(content.get("clickThroughUrl"), dict):
                link = content["clickThroughUrl"].get("url", "")
                
            # 找發布者 (媒體來源)
            publisher = content.get("publisher", "")
            if not publisher and isinstance(content.get("provider"), dict):
                publisher = content["provider"].get("displayName", "")
                
            # 找發布時間並格式化
            pub_time = content.get("providerPublishTime") or content.get("pubDate")
            dt_str = ""
            if pub_time:
                try:
                    if isinstance(pub_time, str):
                        dt_str = pub_time[:10]
                    else:
                        dt_str = datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

            # 進行翻譯
            title_zh = title_en
            try:
                title_zh = GoogleTranslator(source='auto', target='zh-TW').translate(title_en)
            except Exception as e:
                print(f"翻譯失敗 ({ticker}): {e}")

            news_data.append({
                "time": dt_str,
                "title_zh": title_zh,
                "title_en": title_en,
                "link": link,
                "source": publisher
            })
    except Exception as e:
        print(f"新聞抓取失敗 ({ticker}): {e}")

    # 全球股專屬的 Overview
    overview = {
        "close": _clean(latest_row["close"]),
        "change": _clean(change),
        "change_pct": _clean(round(change_pct, 2)),
        "rsi14": round(latest_row.get("RSI14"), 2) if pd.notna(latest_row.get("RSI14")) else None,
        "rsi_state": classify_rsi(latest_row.get("RSI14")),
        "ma_state": classify_ma_trend(latest_row["close"], latest_row.get("MA5"), latest_row.get("MA20"), latest_row.get("MA60")),
        "conditions": {
            "ma60_uptrend": bool(latest_row.get("close", 0) > latest_row.get("MA60", 0) and latest_row.get("MA60", 0) > prev_row.get("MA60", 0)),
            "bb_lower_breakout": bool(latest_row.get("close", 0) < latest_row.get("BB_lower", 0)),
            "rsi_oversold": bool(latest_row.get("RSI14", 50) < 30),
            # 👇 補上全球股的 KD 判斷邏輯 👇
            "kd_under_20": bool(latest_row.get("K", 100) <= 20),
            "kd_golden_cross": bool(prev_row.get("K", 0) < prev_row.get("D", 0) and latest_row.get("K", 0) > latest_row.get("D", 0)),
            "details": {
                "close": _clean(latest_row["close"]),
                "ma60_today": _clean(latest_row.get("MA60")),
                "ma60_yest": _clean(prev_row.get("MA60")),
                "bb_upper": _clean(latest_row.get("BB_upper")),
                "bb_lower": _clean(latest_row.get("BB_lower")),
                "rsi14_today": _clean(latest_row.get("RSI14")),
                "k_today": _clean(latest_row.get("K")),
                "d_today": _clean(latest_row.get("D")),
                "k_yest": _clean(prev_row.get("K")),
                "d_yest": _clean(prev_row.get("D")),
            }
        }
    }

    data = {
        "stock_id": ticker,
        "stock_name": name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "price": price_series,
        "ma": ma_series,       # 👇 這裡補上輸出給圖表用的陣列
        "rsi": rsi_series,     
        "kd": kd_series,       
        "overview": overview,
        "institutional": {}, "margin": {}, "fundamentals": {}, "news": news_data
    }

    out_path = os.path.join(OUTPUT_DIR_ABS, f"{ticker}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"✅ {ticker} 輸出成功")
    return ticker

def update_manifest(success_tickers):
    manifest_path = os.path.join(OUTPUT_DIR_ABS, "manifest.json")
    
    # 1. 建立空字典作為預設值
    manifest = {}
    
    # 2. 安全讀取機制：加入 try...except 保護傘
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            # 如果檔案壞掉 (例如 Git 衝突造成的 JSONDecodeError)，就印出警告並從空字典重新開始
            print(f"⚠️ 讀取 manifest.json 發生錯誤 ({e})，將自動重建檔案。")
            manifest = {}

    # 3. 只寫入全球股專屬欄位，絕對不碰台股的 "stocks" 欄位
    manifest["global_stocks"] = success_tickers
    manifest["global_stock_names"] = GLOBAL_STOCKS
    
    # (可選) 加上更新時間，幫助我們之後追蹤除錯
    from datetime import datetime, timezone
    manifest["global_updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # 4. 安全寫回檔案
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        
    print(f"✅ manifest.json 全球股清單已更新 (成功寫入 {len(success_tickers)} 檔)")

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR_ABS, exist_ok=True)
    success = []
    for ticker, name in GLOBAL_STOCKS.items():
        try:
            build_global_stock(ticker, name)
            success.append(ticker)
        except Exception as e:
            print(f"❌ {ticker} 失敗: {e}")
    update_manifest(success)