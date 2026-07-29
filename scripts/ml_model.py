# scripts/ml_model.py
"""
機器學習版的隔日漲跌預測(實驗性功能)。

跟「歷史統計法」(analysis.py)並存,兩邊各自透過 prediction_tracker
累積實際命中率,跑一段時間後可以客觀比較哪個方法比較準。

方法說明:
- 模型: 邏輯迴歸(LogisticRegression),刻意選最簡單的模型,
  降低在歷史資料上過度配適(overfitting)的風險。
- 特徵: 全部由既有的股價資料衍生(報酬率、RSI、均線乖離率、均線排列、量比),
  不需要多打任何API。
- 驗證: 透過 sklearn 的 train_test_split (shuffle=False) 進行嚴格的時間序列切割,
  回測準確率會誠實顯示在畫面上。
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split

# 用最後幾個交易日做回測驗證(不參與第一次訓練,當作誠實的考卷)
BACKTEST_DAYS = 60

# 至少要有幾筆有效樣本才訓練(太少會不穩定)
MIN_TRAIN_SAMPLES = 200


def build_features(df: pd.DataFrame, inst_df: pd.DataFrame = None, market_df: pd.DataFrame = None,
                    sentiment_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    從既有的股價資料(close/volume/MA/RSI欄位)衍生模型特徵。
    所有特徵都只用「當天以前」的資訊,不能摻入任何未來資料。
    """
    feat = pd.DataFrame(index=df.index)
    close = df["close"]
    volume = df["volume"]
    dates = df["date"]

    # 動能: 近1/5/20日報酬率
    feat["ret_1"] = close.pct_change(1)
    feat["ret_5"] = close.pct_change(5)
    feat["ret_20"] = close.pct_change(20)

    # RSI (縮到0-1之間)
    feat["rsi14"] = df["RSI14"] / 100
    feat["rsi6"] = df["RSI6"] / 100

    # 均線乖離率: 股價偏離均線的程度
    feat["bias_ma5"] = (close - df["MA5"]) / df["MA5"]
    feat["bias_ma20"] = (close - df["MA20"]) / df["MA20"]
    feat["bias_ma60"] = (close - df["MA60"]) / df["MA60"]

    # 均線排列(多頭/空頭的0-1旗標)
    feat["ma5_gt_ma20"] = (df["MA5"] > df["MA20"]).astype(float)
    feat["ma20_gt_ma60"] = (df["MA20"] > df["MA60"]).astype(float)

    # 量比: 今天成交量相對近20日均量
    vol_ma20 = volume.rolling(20).mean()
    feat["vol_ratio"] = volume / vol_ma20

    # ---- 三大法人買賣超 ----
    if inst_df is not None and not inst_df.empty:
        inst_lookup = inst_df.drop_duplicates("date").set_index("date")[["foreign_net", "trust_net", "dealer_net"]]
        inst_aligned = inst_lookup.reindex(dates.values)
        feat["foreign_net"] = inst_aligned["foreign_net"].fillna(0).values
        feat["trust_net"] = inst_aligned["trust_net"].fillna(0).values
        feat["dealer_net"] = inst_aligned["dealer_net"].fillna(0).values
    else:
        feat["foreign_net"] = 0.0
        feat["trust_net"] = 0.0
        feat["dealer_net"] = 0.0

    # ---- 大盤同期漲跌 ----
    if market_df is not None and not market_df.empty:
        market_sorted = market_df.sort_values("date").drop_duplicates("date").copy()
        market_sorted["market_ret_1"] = market_sorted["market_close"].pct_change(1)
        market_sorted["market_ret_5"] = market_sorted["market_close"].pct_change(5)
        market_lookup = market_sorted.set_index("date")[["market_ret_1", "market_ret_5"]]
        market_aligned = market_lookup.reindex(dates.values)
        feat["market_ret_1"] = market_aligned["market_ret_1"].values
        feat["market_ret_5"] = market_aligned["market_ret_5"].values
    else:
        feat["market_ret_1"] = 0.0
        feat["market_ret_5"] = 0.0

    # ---- 新聞情緒分數 ----
    if sentiment_df is not None and not sentiment_df.empty:
        sentiment_lookup = sentiment_df.drop_duplicates("date").set_index("date")["score"]
        sentiment_aligned = sentiment_lookup.reindex(dates.values)
        feat["news_sentiment"] = sentiment_aligned.fillna(0).values
    else:
        feat["news_sentiment"] = 0.0

    feat = feat.replace([np.inf, -np.inf], np.nan)
    return feat


def train_and_predict(df: pd.DataFrame, inst_df: pd.DataFrame = None, market_df: pd.DataFrame = None,
                       sentiment_df: pd.DataFrame = None) -> dict:
    """
    訓練模型並預測「最新一個交易日的隔天」漲跌機率。
    回傳格式與統計法一致,可以直接餵給 prediction_tracker。
    """
    feat = build_features(df, inst_df=inst_df, market_df=market_df, sentiment_df=sentiment_df)

    has_inst = inst_df is not None and not inst_df.empty
    has_market = market_df is not None and not market_df.empty
    has_sentiment = sentiment_df is not None and not sentiment_df.empty
    print(f"    [ML特徵] 三大法人資料: {'有帶入' if has_inst else '缺失,用0頂替'}"
          f" | 大盤資料: {'有帶入' if has_market else '缺失,用0頂替'}"
          f" | 新聞情緒資料: {'有帶入(累積' + str(len(sentiment_df)) + '筆)' if has_sentiment else '累積不足,用0頂替'}")
    print(f"    [ML特徵] 共 {len(feat.columns)} 個特徵: {list(feat.columns)}")

    target = (df["close"].shift(-1) > df["close"]).astype(float)
    target[df["close"].shift(-1).isna()] = np.nan  # 最新一天沒有「明天」,不能當訓練樣本

    combined = pd.concat([feat, target.rename("target")], axis=1).dropna()
    if len(combined) < MIN_TRAIN_SAMPLES:
        raise ValueError(f"有效訓練樣本只有{len(combined)}筆,少於下限{MIN_TRAIN_SAMPLES},不訓練")

    feature_cols = list(feat.columns)
    X = combined[feature_cols].values
    y = combined["target"].values.astype(int)

    # ---- 時間序列切分回測 (使用 train_test_split, shuffle=False 保留時間順序) ----
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=BACKTEST_DAYS, 
        shuffle=False
    )
    
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    model.fit(X_train, y_train)
    backtest_accuracy = round(float(model.score(X_test, y_test)) * 100, 1)

    # ---- 用全部歷史重新訓練,對最新一天做預測 ----
    model.fit(X, y)

    latest_feat = feat.iloc[[-1]].values
    if np.isnan(latest_feat).any():
        raise ValueError("最新一天的特徵含有缺值,無法預測")

    prob_up = float(model.predict_proba(latest_feat)[0][1])
    up_pct = round(prob_up * 100, 1)
    down_pct = round(100 - up_pct, 1)

    return {
        "up_pct": up_pct,
        "down_pct": down_pct,
        "sample_size": len(combined),
        "backtest_accuracy": backtest_accuracy,
        "backtest_days": BACKTEST_DAYS,
        "state_label": f"邏輯迴歸 · 訓練樣本{len(combined)}天 · 近{BACKTEST_DAYS}天回測準確率{backtest_accuracy}%",
    }