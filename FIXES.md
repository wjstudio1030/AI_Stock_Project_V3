# 已修正項目

1. 訓練與預測共用 `model_features.py`，最新 `ret_3d` 不再填 0。
2. 回測改為 expanding-window walk-forward，下一交易日開盤進場，避免資料洩漏與同日收盤成交偏誤。
3. DRAM 模組不再產生隨機／擬合價格；只接受可驗證資料來源。
4. 原「大戶持股比例」改為清楚標示的法人＋融資籌碼代理分數。
5. 最終綜合機率直接讀取數值 XGBoost JSON，並由固定公式計算與驗證。
6. XGBoost 模型改為每檔股票獨立檔案，所有 V3/V4 腳本支援多股票 CLI。
7. SQLite 自動初始化與舊 Schema 遷移；寫入失敗會回滾並拋出錯誤。
8. 每日新聞情緒只統計最新交易日當天新聞，同日重跑採 upsert，空抓取不覆寫既有資料。
9. GitHub Actions 順序改為先更新市場資料，再訓練、預測、分析、打包。
10. 工作流程先初始化資料庫並執行靜態／單元測試。
11. GitHub Pages 資料路徑改為 `./data`。
12. 綜合機率使用獨立卡片，不再覆寫邏輯迴歸模型機率與命中率。
13. 多股比較表頭排序功能已實作。
14. `requirements.txt` 與程式直接依賴一致；workflow 只使用 requirements 安裝。
15. Discord Webhook 已加入 workflow Secrets；Telegram 使用純文字避免 Markdown 注入。
16. 深色模式套用到所有圖表並保存使用者偏好。
17. AI／外部文字以前端 DOM `textContent` 顯示，避免直接注入 HTML。
18. 前端新聞期間標示由 14 天修正為設定中的 7 天。
19. GitHub Actions 現在確實執行 `predict_today_v3.py`。
20. 最終交付不包含真實 `.env`，只提供 `.env.example`；舊憑證必須撤銷重建。
