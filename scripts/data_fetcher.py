"""FinMind 資料抓取與欄位正規化。"""

from __future__ import annotations

import time
from datetime import date

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import FINMIND_API_URL, FINMIND_TOKEN


def _session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "AI-Stock/4.0"})
    return session


_SESSION = _session()


def _auth_headers(token: str | None) -> dict[str, str]:
    use_token = (token or FINMIND_TOKEN).strip()
    return {"Authorization": f"Bearer {use_token}"} if use_token else {}


def _request(params: dict, token: str | None = None, timeout: int = 30) -> dict:
    response = _SESSION.get(
        FINMIND_API_URL,
        params=params,
        headers=_auth_headers(token),
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind API 錯誤: {payload.get('msg', payload)}")
    return payload


def _fetch(dataset: str, data_id: str, start_date: str, end_date: str, token: str | None = None) -> pd.DataFrame:
    payload = _request(
        {
            "dataset": dataset,
            "data_id": data_id,
            "start_date": start_date,
            "end_date": end_date,
        },
        token=token,
    )
    df = pd.DataFrame(payload.get("data", []))
    if df.empty:
        raise ValueError(f"查無資料: dataset={dataset}, data_id={data_id}")
    return df


def get_stock_price(stock_id: str, start_date: str, end_date: str, token: str | None = None) -> pd.DataFrame:
    df = _fetch("TaiwanStockPrice", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"max": "high", "min": "low", "Trading_Volume": "volume"})
    numeric = ["open", "high", "low", "close", "volume"]
    df[numeric] = df[numeric].apply(pd.to_numeric, errors="coerce")
    return df[["date", *numeric]].dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)


def get_stock_names(token: str | None = None) -> dict[str, str]:
    payload = _request({"dataset": "TaiwanStockInfo"}, token=token, timeout=20)
    df = pd.DataFrame(payload.get("data", []))
    if df.empty:
        raise ValueError("查無 TaiwanStockInfo 資料")
    df = df.drop_duplicates(subset="stock_id", keep="first")
    return dict(zip(df["stock_id"].astype(str), df["stock_name"].astype(str)))


def get_institutional_investors(stock_id: str, start_date: str, end_date: str, token: str | None = None) -> pd.DataFrame:
    df = _fetch("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df["buy"] = pd.to_numeric(df["buy"], errors="coerce").fillna(0)
    df["sell"] = pd.to_numeric(df["sell"], errors="coerce").fillna(0)
    df["net"] = df["buy"] - df["sell"]
    pivot = df.pivot_table(index="date", columns="name", values="net", aggfunc="sum").fillna(0)

    def sum_cols(candidates: list[str]) -> pd.Series:
        cols = [c for c in candidates if c in pivot.columns]
        return pivot[cols].sum(axis=1) if cols else pd.Series(0.0, index=pivot.index)

    result = pd.DataFrame(index=pivot.index)
    result["foreign_net"] = sum_cols(["Foreign_Investor", "Foreign_Dealer_Self"])
    result["trust_net"] = sum_cols(["Investment_Trust"])
    result["dealer_net"] = sum_cols(["Dealer_self", "Dealer_Hedging"])
    result["total_net"] = result[["foreign_net", "trust_net", "dealer_net"]].sum(axis=1)
    return result.reset_index().sort_values("date").reset_index(drop=True)


def get_margin_trading(stock_id: str, start_date: str, end_date: str, token: str | None = None) -> pd.DataFrame:
    df = _fetch("TaiwanStockMarginPurchaseShortSale", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(
        columns={
            "MarginPurchaseTodayBalance": "margin_balance",
            "MarginPurchaseBuy": "margin_buy",
            "MarginPurchaseSell": "margin_sell",
            "ShortSaleTodayBalance": "short_balance",
            "ShortSaleBuy": "short_buy",
            "ShortSaleSell": "short_sell",
        }
    )
    cols = ["date", "margin_balance", "margin_buy", "margin_sell", "short_balance", "short_buy", "short_sell"]
    for col in cols[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[cols].sort_values("date").drop_duplicates("date").reset_index(drop=True)


def get_valuation_ratios(stock_id: str, start_date: str, end_date: str, token: str | None = None) -> pd.DataFrame:
    df = _fetch("TaiwanStockPER", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    cols = ["PER", "PBR", "dividend_yield"]
    df[cols] = df[cols].apply(pd.to_numeric, errors="coerce")
    return df[["date", *cols]].sort_values("date").drop_duplicates("date").reset_index(drop=True)


def _pick_series(df: pd.DataFrame, candidates: list[str], label: str, exclude: list[str] | None = None) -> pd.DataFrame:
    exclude = exclude or []
    for keyword in candidates:
        exact = df[df["type"] == keyword]
        if not exact.empty:
            return exact[["date", "value"]].rename(columns={"value": label})
    for keyword in candidates:
        matched = df[df["type"].str.contains(keyword, case=False, na=False)]
        for ex in exclude:
            matched = matched[~matched["type"].str.contains(ex, case=False, na=False)]
        if not matched.empty:
            picked = matched["type"].iloc[0]
            return df[df["type"] == picked][["date", "value"]].rename(columns={"value": label})
    available = sorted(df["type"].dropna().unique().tolist())
    raise ValueError(f"找不到 {label}，候選={candidates}，可用 type={available}")


def get_financial_statements(stock_id: str, start_date: str, end_date: str, token: str | None = None) -> pd.DataFrame:
    df = _fetch("TaiwanStockFinancialStatements", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    parts = [
        _pick_series(df, ["EPS"], "eps"),
        _pick_series(df, ["Revenue"], "revenue"),
        _pick_series(df, ["GrossProfit", "GrossProfitLoss"], "gross_profit"),
        _pick_series(df, ["OperatingIncome"], "operating_income"),
        _pick_series(df, ["IncomeAfterTaxes", "ProfitLoss"], "net_income"),
    ]
    merged = parts[0]
    for part in parts[1:]:
        merged = merged.merge(part, on="date", how="outer")
    merged = merged.sort_values("date").drop_duplicates("date", keep="last")
    merged["gross_margin"] = merged["gross_profit"] / merged["revenue"] * 100
    merged["operating_margin"] = merged["operating_income"] / merged["revenue"] * 100
    return merged.reset_index(drop=True)


def get_balance_sheet(stock_id: str, start_date: str, end_date: str, token: str | None = None) -> pd.DataFrame:
    df = _fetch("TaiwanStockBalanceSheet", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    total_assets = _pick_series(df, ["TotalAssets"], "total_assets")
    equity = _pick_series(
        df,
        ["EquityAttributableToOwnersOfParent", "TotalEquity", "Equity"],
        "equity",
        exclude=["Liabilities"],
    )
    merged = total_assets.merge(equity, on="date", how="outer").sort_values("date")
    merged["total_liabilities"] = merged["total_assets"] - merged["equity"]
    merged["debt_ratio"] = merged["total_liabilities"] / merged["total_assets"] * 100
    return merged.reset_index(drop=True)


def get_cash_flow(stock_id: str, start_date: str, end_date: str, token: str | None = None) -> pd.DataFrame:
    df = _fetch("TaiwanStockCashFlowsStatement", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return _pick_series(
        df,
        ["CashFlowsFromOperatingActivities", "NetCashFlowsFromOperatingActivities"],
        "operating_cash_flow",
    ).sort_values("date").reset_index(drop=True)


def get_stock_news(stock_id: str, start_date: str, end_date: str, token: str | None = None) -> pd.DataFrame:
    """FinMind 官方限制為單次一天，因此逐日抓取並合併。"""
    frames: list[pd.DataFrame] = []
    for day in pd.date_range(start=start_date, end=end_date):
        day_str = day.strftime("%Y-%m-%d")
        try:
            payload = _request(
                {"dataset": "TaiwanStockNews", "data_id": stock_id, "start_date": day_str},
                token=token,
                timeout=25,
            )
            records = payload.get("data", [])
            if records:
                frames.append(pd.DataFrame(records))
        except Exception as exc:
            print(f"    [新聞] {stock_id} {day_str} 抓取失敗: {exc}")
        time.sleep(0.05)

    if not frames:
        raise ValueError(f"查無新聞資料: stock_id={stock_id}")
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "title"])
    for col in ("source", "link"):
        if col not in df:
            df[col] = ""
    return (
        df[["date", "title", "source", "link"]]
        .drop_duplicates(subset=["title", "link"], keep="first")
        .sort_values("date", ascending=False)
        .reset_index(drop=True)
    )


def get_market_index(start_date: str, end_date: str, token: str | None = None) -> pd.DataFrame:
    df = _fetch("TaiwanStockPrice", "TAIEX", start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df["market_close"] = pd.to_numeric(df["close"], errors="coerce")
    return df[["date", "market_close"]].dropna().sort_values("date").drop_duplicates("date").reset_index(drop=True)
