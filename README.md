# AI Stock Final

這是修正後的完整版本，包含 FinMind 資料建置、統計／邏輯迴歸、每檔獨立 XGBoost、walk-forward 回測、結構化新聞分析、風險警報與 GitHub Pages 前端。

## 重要安全步驟

先前上傳的 `.env` 已暴露 OpenAI 與 Telegram 憑證。請立即在 OpenAI 與 Telegram 後台撤銷舊憑證並建立新憑證。此專案只提供 `.env.example`，不包含任何真實秘密。

## 本機執行

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/db_manager.py
python scripts/build_data.py
python scripts/fetch_dram.py
python scripts/fetch_whales.py
python scripts/train_xgb_v3.py
python scripts/predict_today_v3.py
python scripts/news_sentiment_ai_v3.py
python scripts/strategy_grid_ai_v3.py
python scripts/ai_analyst_v3.py
python scripts/alert_system_v3.py
python scripts/ultimate_judge_ai_v4.py
python scripts/build_data.py --refresh-v3-only
```

在 `docs/` 啟動靜態伺服器：

```bash
python -m http.server 8000 --directory docs
```

開啟 `http://localhost:8000/`。

## DRAM 資料

系統不再生成模擬 DRAM 價格。請透過 `.env` 或 GitHub Secrets 提供真實 CSV URL／路徑，或人工驗證的單日報價。未設定時程式會保留既有真實資料，並以缺失旗標告知模型該特徵不可用。

## 籌碼代理分數

`weekly_position_proxy` 是由法人資金流與融資變化計算的相對代理分數，不是集保大戶持股比例。前端與模型均使用「代理分數」名稱，避免誤導。

## GitHub Pages

將 Pages 發布來源設為 `docs/`。前端使用 `./data/...` 相對路徑，可正確對應 Pages 網站根目錄。

## GitHub Secrets / Variables

必要 Secrets：`FINMIND_TOKEN`。要啟用 OpenAI 結構化報告時再設定 `OPENAI_API_KEY`。通知可選擇 `DISCORD_WEBHOOK_URL`、`TG_BOT_TOKEN`、`TG_CHAT_ID`。真實 DRAM 資料可使用 `DRAM_DATA_URL` 或單日報價設定。

詳細升級步驟請見 `MIGRATION.md`。

## 20 檔台股與 FinMind 額度備援（2026-11-15）

預設追蹤 20 檔台股：`2330,2454,2317,2308,3711,1303,2881,2882,2891,2383,2408,3037,2412,2303,3017,3443,2382,2887,2885,6669`。

- 每日與週末 GitHub Actions 工作流程都明確使用上述 20 檔，以避免舊的 GitHub Actions `vars.STOCK_LIST`（原本僅 6/12 檔）覆蓋新版清單。**目前 Actions 中既有的 `STOCK_LIST` Variable 不再控制這兩個排程**；要更換清單，請同步修改兩個 workflow 的 `env.STOCK_LIST` 與 `scripts/config.py` 的預設值；本機仍可透過環境變數 `STOCK_LIST` 覆蓋。
- 前端比較表的股票清單完全來自 `docs/data/manifest.json`，會保留清單全部股票的排序。個別 JSON 失敗時顯示「資料待更新」，不會悄悄排除；無法載入的股票不可點選。
- FinMind HTTP 402 依官方文件代表 API 額度達上限。遇到此情況，當次 Python 執行會停止後續 FinMind 請求，股票**日線價格**改以 Yahoo Finance `.TW`（必要時 `.TWO`）資料備援，不會將估計值冒充實際法人、基本面或新聞資料。日線備援與行情觀測日寫入個別股票 JSON；前端有額度提示。
- 若某檔 FinMind 與 Yahoo 日線均不可用，保留既有 JSON，並將失敗代號列入 manifest 的 `failed_stocks`；最新成功更新時間不因所有股票失敗而刷新。若所有股票都無法取得行情，流程仍會明確失敗，避免將完全過期的行情標示為成功。
- 財報、法人與新聞仍主要依賴 FinMind 的使用額度；Yahoo 備援**僅保證行情欄位的可用性，不代表所有 20 檔的進階分析資料一定能完整刷新**。部分進階步驟設定為可降級，以確保已成功擷取的股價能被儲存。

更新後可用 `python -m unittest discover -s tests -v`、`node --check docs/app.js` 檢查，並至 Actions 手動執行 Daily Pipeline 檢查新行情與額度狀態。台灣股市休市日通常會沿用最近交易日的行情日期。
