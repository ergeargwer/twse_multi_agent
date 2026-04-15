# TWSE Multi-Agent AI 投資決策系統 - 開發記憶保存 (Memory Log)

本文件自動生成於對話結尾，旨在為未來的重啟或新對話提供完整的專案上下文與進度備忘。

## 專案核心宗旨
建立一個專為「台灣股市（TWSE / TPEx）」打造的多 Agent 分析架構 (MVP)。
有別於預設效率市場的美股 AI，本系統引進台股特有的「淺碟市場、籌碼戰、強制融券回補、ETF被動資金吃豆腐」等邏輯，捨棄單一 Pipeline 機制，採用 **「平行盲測運算 (Parallel Blackbox Execution) 與衝突推演」**。

## 系統架構與已實作 Agent（存放於本目錄）

全部 Agent 均嚴格遵守「無狀態 (Stateless)、讀寫分離隔離、禁用投資操作建議」的最高約束。

1. **Phase 1: `phase_one.py`**
   - **Data Ingestion Agent**: 負責模擬對接外部資料，將台股特有的價量、三大法人、融資券變化、除權息與 ETF 名單洗成單一 JSON，並寫入 `SharedContext` 的 `ingested_data`。
2. **Phase 2 平行基層 Agent (Blind Parallel Analysers):**
   - **Fundamental Agent (`phase_two_fundamental.py`)**: 僅負責讀取財報數據，給出財務健康度。
   - **Technical Agent (`phase_two_technical.py`)**: 僅讀取均線與價量，描述多空排列動能。
   - **Institutional Flow Agent (`phase_two_institutional.py`)**: 僅讀取外資/投信/融資券變化，描述籌碼匯入、斷頭等流動狀態。
   - **ETF & Event Agent (`phase_two_event.py`)**: 僅讀取台股行事曆，針對「除權息、ETF 候選換股名單、融券強制回補」提出潛在的被動資金買賣壓風險。
   - 附註：`phase_two_parallel_test.py` 已驗證平行同啟動時，各 Agent 能以 Thread-Safe 的方式互不干擾、獨立寫回自身報告。
3. **Phase 3: `phase_three_synthesizer.py`**
   - **Decision Synthesizer Agent**: 收割所有基層 Agent 的報告，進行邏輯斷詞與矛盾比對。若論點多空抵銷，會觸發嚴格限制：輸出「無法形成高信心推演」，且無條件附加免責聲明。

## 未來啟動與延續指南

下一次重啟對話時，您可以直接請 AI 讀取本目錄 `/home/sweet/.gemini/antigravity/scratch/twse_multi_agent/` 下的 Python 腳本。

**建議的下一步延伸方向：**
1. 將 `Data Ingestion Agent` 接上真實的 TWSE / TPEx API 或開源爬蟲庫 (如 `FinMind` 或 `twstock`)。
2. 將 `Decision Synthesizer Agent` 內簡單的 keyword 計數機制，替換為封裝真實的 LLM API (如 Gemini / GPT-4) 提示詞呼叫。
3. 將目前拆散在各 `phase_xxx.py` 的類別，整併成單一架構的模組 (e.g. `agents/`, `core/`)。
