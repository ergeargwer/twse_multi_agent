# TWSE Multi-Agent AI 投資決策系統 - 開發記憶保存 (Memory Log)

本文件旨在為未來的重啟或新對話提供完整的專案上下文與進度備忘。
**上次更新日期**: 2026-04-15

## 專案核心宗旨
建立一個專為「台灣股市（TWSE / TPEx）」打造的多 Agent 分析架構 (MVP)。
本系統引進台股特有的「淺碟市場、籌碼戰、強制融券回補、ETF被動資金吃豆腐」等邏輯，採用 **「平行盲測運算 (Parallel Blackbox Execution) 與衝突推演」**，以避免單一 LLM 分析的偏誤。所有的 Agent 必須嚴格保持 **無狀態 (Stateless)** 且 **讀寫分離**。

---

## 🎯 已完成進度 (Current Status)

### 1. 結構重構模組化 (Refactoring Completed)
專案已從零散的腳本重構為具備軟體工程標準的架構：
- `main.py`: 全局啟動入口。
- `src/core/context.py`: 提供基於 `threading.Lock()` 防護的 `SharedContext` 記憶體中樞。
- `src/orchestrator/pipeline.py`: 控制所有階段的調度器，負責以多執行緒 (`threading`) 平行啟動 Base Agents。
- `src/agents/`: 存放所有獨立的 Agent (`ingestion.py`, `fundamental.py`, `technical.py`, `institutional.py`, `event.py`, `synthesizer.py`)。

### 2. 真實數據串接 (Data Provider Integration)
`Phase 1` (`ingestion.py`) 已完成與真實 API 的串接，並且具備防止斷線的 **Fallback 容錯機制**，保護後方 Agent 不至於崩潰：
- **環境設定**: 已建立 Python 虛擬環境 (`venv`) 解決樹莓派環境衝突，必須使用 `./venv/bin/python main.py` 啟動。
- **價量與基本面**: 整合 `yfinance` 獲取真實歷史 K 線並計算 MA 均線，以及擷取 PE/PB 等財報估值。
- **籌碼面**: 整合 `FinMind.data` 擷取外資、投信、自營商買賣超淨額，以及融資餘額狀況。
- **測試點驗證**: 已針對 `2330.TW` (台積電)、`5425.TWO` (台半) 與 `2327.TW` (國巨) 驗證真實數據抓取，Phase 2/3 的盲測推演運作一切正常。

---

## 🚀 未來啟動與延續指南 (Next Steps)

下一次重啟對話時，請 AI 讀取本目錄 `/home/sweet/.gemini/antigravity/scratch/twse_multi_agent/` 下的 `README.md` 與 `MEMORY_LOG.md` 即可無縫接軌。

**強烈建議優先執行的後續任務：**

1. **整合真實 LLM (Large Language Model API)**
   - 目前 `src/agents/synthesizer.py` (`DecisionSynthesizerAgent`) 的決策推演是採用「簡單關鍵字掃描 (Keyword Counting)」來判斷多空矛盾。
   - **下一步**：應該在此處接入 `openai` 或 `google.generativeai`，將前方 4 個 Base Agent 吐出來的 JSON 餵給 GPT-4 或 Gemini，利用 `Prompt` 規範它進行深度的邏輯辯證。

2. **優化 Event Agent 數據源**
   - 目前 `fetch_calendar_events()` 仍採用模擬的回傳值（因為除權息與 ETF 審核更動很難有免費即時 API）。
   - **下一步**：尋找能抓取「強制回補日」或「ETF 候選換股名單」的爬蟲方式注入其中。

3. **優化依賴注入與配置**
   - 提供一份 `config.yaml` 或 `.env` 讓使用者可以自由抽換 `target_symbol`，而不是寫死在 `main.py` 裡面。

**【開發鐵律提醒未來 AI】**：
永遠不得干涉 Phase 2 四個 Base Agent 的平行獨立性。它們不能互相呼叫，也不能試圖看到別人的報告。一切交流只能透過最終的 Phase 3 Synthesizer 來執行。
