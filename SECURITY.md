# Security

- 不要提交 `.env`、API Key、Bot Token 或 Webhook URL。
- 生產環境憑證只放 GitHub Actions Secrets。
- 若秘密曾經出現在 Git、聊天附件或 CI 日誌中，請視為已洩漏並立即撤銷。
- 前端只以 `textContent` 顯示 AI／新聞衍生文字，避免 DOM 注入。
- 外部 CSV 應只使用可信來源，並確認欄位與價格單位。
