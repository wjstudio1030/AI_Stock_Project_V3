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
