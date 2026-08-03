# 從舊版升級

1. **先撤銷舊憑證**：重新建立 OpenAI API Key 與 Telegram Bot Token。不要只刪除本機 `.env`。
2. 用本專案內容覆蓋舊版程式，工作流程應放在 `.github/workflows/update_data.yml`。
3. 刪除舊的單一模型檔 `data_db/xgb_nanya_model.pkl`；新模型位於 `data_db/models/xgb_<stock_id>.pkl`。
4. 執行 `python scripts/db_manager.py`。升級器會建立 `weekly_position_proxy`，並清除舊版無來源標記的模擬 DRAM 資料。
5. 在 GitHub Secrets 設定 `FINMIND_TOKEN`、`OPENAI_API_KEY`，以及需要的通知或真實 DRAM 資料來源。
6. GitHub Pages 發布來源設為 `docs/`。

舊資料表 `weekly_whales` 不再使用。它可以保留供歷史比對，也可以自行備份後刪除。
