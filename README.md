# TWSE Multi-Agent AI（台股多智能體決策架構）

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![Architecture](https://img.shields.io/badge/Architecture-Multi--Agent-success)
![License](https://img.shields.io/badge/License-MIT-green.svg)

專為台灣股市（TWSE / TPEx）設計的多 Agent **分析**架構（MVP）。用平行盲測與多空矛盾推演，模擬不同研究部門獨立審查，而不是單一模型預測股價。

本系統**不是投資建議，也不會下單**。與券商只做唯讀查詢。

---

## 核心架構

所有 Phase 2 Agent 必須 **Stateless**，彼此看不到對方報告，只能讀 Shared Context 裡自己負責的欄位。

```mermaid
graph TD
    A[FinMind / Shioaji / 雙 CLI 開放來源] --> B(Phase 1: Data Ingestion)
    B --> C{Shared Context}
    C -.-> D[基本面]
    C -.-> E[技術面]
    C -.-> F[法人籌碼]
    C -.-> G[制度事件]
    C -.-> BR[行為風險]
    C -.-> H[資產配置 / 定價 / 風控 / 紀律]
    D --> S[Phase 3: Decision Synthesizer]
    E --> S
    F --> S
    G --> S
    BR --> S
    H --> S
    S --> R[情境推演報告<br/>禁止點位與買賣指令]
```

### Phase 1 資料收集

- FinMind：日線價量、三大法人、財報估值、除權息等
- Shioaji：帳戶餘額與庫存（未設定金鑰則略過，風控預設否決）
- **Grok Build CLI + Gemini CLI** 平行蒐集近兩週新聞／公告（只搜尋與抓頁），合併去重後寫入 `open_source_events`，品質一律 `unverified`

### Phase 2 平行盲測

九個 Agent 同時跑：基本面、技術面、法人籌碼、制度事件、資產配置、定價把關、風控煞車、執行紀律、**行為風險**（VWAP 乖離／量價背離／假跌破）。

### Phase 3 決策合成

LLM 比對多空矛盾並做情境推演。金鑰後備順序：SpaceXAI → OpenRouter → Gemini。風控否決會置頂攔截說明。

---

## 目錄

```text
twse_multi_agent/
├── main.py                      # 終端機 Pipeline 入口
├── requirements.txt
├── 開發紀錄.md                   # 決策與里程碑
├── MEMORY_LOG.md                 # 給後續對話的記憶
├── src/
│   ├── core/                    # SharedContext、日記、冷卻、風暴比
│   ├── orchestrator/pipeline.py
│   ├── integrations/
│   │   ├── shioaji_client.py    # 唯讀帳戶／庫存
│   │   └── cli_collectors.py    # Grok / Gemini 合作蒐集
│   ├── analysis/behavior_risk.py
│   ├── agents/                  # Phase 2 / 3 Agent
│   ├── trace/                   # Collector + Mermaid 視覺化
│   └── ui/
│       ├── app.py               # Streamlit 儀表板
│       └── risk_chart.py
└── scratch/                     # 單元／煙霧測試
```

執行期 dump 在根目錄 `trace/task_id=<UUID>/`（不進 Git）。

---

## 快速開始

儲存庫：https://github.com/ergeargwer/twse_multi_agent

```bash
git clone https://github.com/ergeargwer/twse_multi_agent.git
cd twse_multi_agent
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

在專案根目錄建立 `.env`（不要提交）：

```bash
# 擇一或並存；Synthesizer 依序嘗試
XAI_API_KEY=
OPENROUTER_API_KEY=
GEMINI_API_KEY=

FINMIND_API_KEY=
SHIOAJI_API_KEY=          # 或 SJ_API_KEY
SHIOAJI_SECRET_KEY=       # 或 SJ_SECRET_KEY

# 雙 CLI 蒐集（預設開啟）
# CLI_COLLECT_ENABLED=0
# CLI_COLLECT_TIMEOUT=180
# CLI_COLLECT_MAX_TURNS=8
```

終端機：

```bash
./venv/bin/python main.py
```

儀表板（建議）：

```bash
PYTHONPATH=. ./venv/bin/streamlit run src/ui/app.py \
  --server.port 8505 --server.address 127.0.0.1
```

本機入口網（Antigravity Portal）一鍵啟動同一組指令，開 [http://127.0.0.1:8505](http://127.0.0.1:8505)。

### Gemini CLI 注意

蒐集端會用 **Node 22** 啟動 Gemini CLI。系統 PATH 若是 Node 18，直接打 `gemini` 會 `Invalid regular expression flags`。可用 `GEMINI_CLI_NODE` / `GEMINI_CLI_BIN` 覆寫。

### 測試

```bash
./venv/bin/python scratch/test_behavior_risk.py
./venv/bin/python scratch/test_cli_collectors.py
```

---

## 藍圖

- [x] FinMind 真實價量／籌碼／財報
- [x] LLM 合成（SpaceXAI / OpenRouter / Gemini 後備）
- [x] Trace 與 Mermaid 流程圖
- [x] Shioaji 唯讀帳戶
- [x] 輔助人格：資產配置、定價把關、風控煞車、執行紀律
- [x] Streamlit 儀表板
- [x] 行為風險（移植 stock_risk_alert）
- [x] Grok Build CLI + Gemini CLI 合作蒐集
- [ ] 新聞情緒獨立 Agent（只讀已蒐集 JSON）
- [ ] 更穩定的除權息／停券資料源
- [ ] Threading 升級 asyncio

開發歷程與限制見 [開發紀錄.md](./開發紀錄.md)。

---

## 免責聲明

**本系統為技術概念驗證，不構成任何財務、投資或交易建議。**

台股風險高。設計者與貢獻者不以分析結果承擔損益責任。使用者請獨立思考，盈虧自負。

系統與證券帳戶僅唯讀串接，不具備、也不會實作自動下單。實際交易須由使用者本人在券商官方 App 或網頁完成。
