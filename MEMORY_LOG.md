# TWSE Multi-Agent AI — Memory Log

**上次更新**：2026-08-14  
給後續對話用。完整決策與里程碑見 [開發紀錄.md](./開發紀錄.md)，對外說明見 [README.md](./README.md)。

## 專案鐵律

- Phase 2 Agent 必須 Stateless、互不可見，不可互相呼叫
- 一切彙整只走 Phase 3 Synthesizer
- 禁止買賣點位與自動下單
- 開放來源即使雙 CLI 交叉也是 `unverified`

## 2026-08-14

### 行為風險

- 移植 `stock_risk_alert` → `src/analysis/behavior_risk.py` + `src/agents/behavior_risk.py`
- 只讀日線 `raw_history`；不否決交易
- UI：`src/ui/risk_chart.py`，分頁「行為風險」
- 測試：`scratch/test_behavior_risk.py`

### 雙 CLI 合作蒐集

- `src/integrations/cli_collectors.py`：Grok `-p` 與 Gemini `-p` 平行
- Gemini 必須 Node 22（本機 PATH node 是 v18）
- Event Agent 讀 `open_source_events`；`CLI_COLLECT_ENABLED=0` 可關
- 測試：`scratch/test_cli_collectors.py`

### 文件與版控

- 新增 `開發紀錄.md`、`requirements.txt`
- `.gitignore` 的 `trace/` 曾誤傷 `src/trace/`，已改 `/trace/`

## 現況架構

- Phase 1：FinMind + Shioaji 唯讀 + 雙 CLI
- Phase 2：九 Agent（含行為風險）
- Phase 3：LLM 後備 SpaceXAI → OpenRouter → Gemini
- UI：`src/ui/app.py`，入口埠 **8505**
- 必須用專案 `venv`（系統 python 沒有 shioaji）

## 啟動

```bash
PYTHONPATH=. venv/bin/streamlit run src/ui/app.py --server.port 8505 --server.address 127.0.0.1 --server.headless true
# 或
venv/bin/python main.py
```

## 仍待處理（不要當成沒做過 LLM）

- 行事曆欄位常缺（回補日／ETF 名單／融資維持率）
- 新聞情緒獨立 Agent
- asyncio
- `main.py` 標的改參數化（UI 已可輸入）
