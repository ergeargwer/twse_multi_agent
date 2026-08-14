import os
import json
from typing import Dict, Any

class TraceVisualizer:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.trace_dir = os.path.join("trace", f"task_id={self.task_id}")

    def load_traces(self) -> Dict[str, Any]:
        data = {}
        if not os.path.exists(self.trace_dir):
            return data
            
        for filename in os.listdir(self.trace_dir):
            if filename.endswith(".trace.json"):
                with open(os.path.join(self.trace_dir, filename), 'r', encoding='utf-8') as f:
                    data[filename.replace(".trace.json", "")] = json.load(f)
        return data

    AGENT_CATALOG = [
        ("01_ingestion", "資料收集", "src/agents/ingestion.py"),
        ("02_fundamental", "基本面", "src/agents/fundamental.py"),
        ("02_technical", "技術面", "src/agents/technical.py"),
        ("02_institutional", "法人籌碼", "src/agents/institutional.py"),
        ("02_event", "制度事件", "src/agents/event.py"),
        ("02_asset_allocation", "資產配置", "src/agents/asset_allocation.py"),
        ("02_pricing_gatekeeper", "定價把關", "src/agents/pricing_gatekeeper.py"),
        ("02_risk_veto", "風控煞車", "src/agents/risk_veto.py"),
        ("02_discipline", "執行紀律", "src/agents/discipline.py"),
        ("02_behavior_risk", "行為風險", "src/agents/behavior_risk.py"),
        ("03_llm_prompt", "LLM Prompt", "src/agents/synthesizer.py"),
        ("03_llm_output", "決策合成 / LLM 輸出", "src/agents/synthesizer.py"),
    ]

    PHASE2_AGENTS = [
        ("02_fundamental", "F", "基本面"),
        ("02_technical", "T", "技術面"),
        ("02_institutional", "I", "法人籌碼"),
        ("02_event", "E", "制度事件"),
        ("02_asset_allocation", "A", "資產配置"),
        ("02_pricing_gatekeeper", "G", "定價把關"),
        ("02_risk_veto", "V", "風控煞車"),
        ("02_discipline", "D", "執行紀律"),
        ("02_behavior_risk", "BR", "行為風險"),
    ]

    @staticmethod
    def generate_pipeline_flowchart() -> str:
        """個股分析報告的三階段架構圖（不依賴單次 trace）。"""
        lines = [
            "flowchart TB",
            "    classDef phase fill:#1e3c72,color:#ffffff,stroke:#1e3c72",
            "    classDef store fill:#f8fafc,color:#1e3c72,stroke:#2a5298",
            "    classDef agent fill:#eef2ff,color:#1e3c72,stroke:#2a5298",
            "    classDef gate fill:#fef2f2,color:#991b1b,stroke:#dc2626",
            "    classDef out fill:#ecfdf5,color:#065f46,stroke:#059669",
            '    U["使用者輸入標的與風險參數"]:::phase',
            '    ING["Phase 1 資料收集<br/>價量 / 財報 / 籌碼 / 行事曆 / 帳戶 / 雙 CLI 開放來源"]:::phase',
            '    CTX[("Shared Context<br/>唯讀分發")]:::store',
            "    U --> ING --> CTX",
            '    subgraph P2["Phase 2 平行盲測（Agent 彼此不可見）"]',
            "        direction LR",
            '        F["基本面"]:::agent',
            '        T["技術面"]:::agent',
            '        I["法人籌碼"]:::agent',
            '        E["制度事件"]:::agent',
            '        A["資產配置"]:::agent',
            '        G["定價把關"]:::agent',
            '        V["風控煞車 可否決"]:::gate',
            '        D["執行紀律"]:::agent',
            '        BR["行為風險"]:::agent',
            "    end",
            "    CTX --> F & T & I & E",
            "    CTX --> A & G & V & D & BR",
            '    SYN["Phase 3 決策合成"]:::phase',
            '    LLM["LLM 情境推演<br/>禁止點位與買賣指令"]:::agent',
            '    R["個股分析報告<br/>附風暴比與分批提醒"]:::out',
            "    F & T & I & E --> SYN",
            "    A & G & V & D & BR --> SYN",
            "    SYN --> LLM --> R",
        ]
        return "\n".join(lines)

    def generate_run_flowchart(self) -> str:
        """依本次 trace 標示各 Agent 是否完成，以及風控是否否決。"""
        traces = self.load_traces()
        lines = [
            "flowchart TB",
            "    classDef done fill:#ecfdf5,color:#065f46,stroke:#059669",
            "    classDef miss fill:#f1f5f9,color:#64748b,stroke:#94a3b8,stroke-dasharray: 4 3",
            "    classDef veto fill:#fef2f2,color:#991b1b,stroke:#dc2626",
            "    classDef phase fill:#1e3c72,color:#ffffff,stroke:#1e3c72",
            '    U["開始分析"]:::phase',
        ]

        ing_ok = "01_ingestion" in traces
        ing_cls = "done" if ing_ok else "miss"
        lines.append(f'    ING["Phase 1 資料收集"]:::{ing_cls}')
        lines.append("    U --> ING")

        for key, node_id, label in self.PHASE2_AGENTS:
            trace = traces.get(key, {})
            output = trace.get("output_trace") or {}
            status = "完成" if key in traces else "未產出"
            extra = ""
            node_cls = "done" if key in traces else "miss"
            if key == "02_risk_veto" and output.get("veto"):
                reason = str(output.get("veto_reason") or "已否決")
                extra = f"<br/>否決：{reason[:40]}"
                node_cls = "veto"
            elif key == "02_pricing_gatekeeper":
                signal = output.get("price_reasonableness_signal")
                if signal:
                    extra = f"<br/>{signal}"
            elif key == "02_behavior_risk":
                signal = output.get("behavior_risk_signal")
                if signal:
                    extra = f"<br/>{signal}"
            lines.append(f'    {node_id}["{label}<br/>{status}{extra}"]:::{node_cls}')
            lines.append(f"    ING --> {node_id}")

        syn_ok = "03_llm_output" in traces or "03_llm_prompt" in traces
        syn_cls = "done" if syn_ok else "miss"
        lines.append(f'    SYN["Phase 3 決策合成 / LLM"]:::{syn_cls}')
        for _, node_id, _ in self.PHASE2_AGENTS:
            lines.append(f"    {node_id} --> SYN")
        lines.append('    SYN --> R["輸出個股分析報告"]:::done' if syn_ok else '    SYN --> R["尚未產出報告"]:::miss')
        return "\n".join(lines)

    @staticmethod
    def compact_payload(obj: Any, max_list: int = 6) -> Any:
        """展開給開發者看時，裁掉過長的 raw_history 等列表。"""
        if isinstance(obj, dict):
            out = {}
            for key, value in obj.items():
                if key == "raw_history" and isinstance(value, list):
                    out[key] = f"[省略 {len(value)} 筆 K 線，避免畫面過長]"
                elif key == "open_source_items" and isinstance(value, list) and len(value) > max_list:
                    out[key] = value[:max_list] + [f"... 另有 {len(value) - max_list} 筆未展開"]
                else:
                    out[key] = TraceVisualizer.compact_payload(value, max_list)
            return out
        if isinstance(obj, list):
            if len(obj) > max_list:
                head = [TraceVisualizer.compact_payload(item, max_list) for item in obj[:max_list]]
                head.append(f"... 另有 {len(obj) - max_list} 筆未展開")
                return head
            return [TraceVisualizer.compact_payload(item, max_list) for item in obj]
        return obj

    def iter_agent_reports(self) -> list:
        """回傳各 Agent 的可檢視摘要，供修改 agent 時對照。"""
        traces = self.load_traces()
        reports = []
        for stage, title, source in self.AGENT_CATALOG:
            raw = traces.get(stage)
            item = {
                "stage": stage,
                "title": title,
                "source": source,
                "present": raw is not None,
                "findings": [],
                "signals": {},
                "summary": "",
                "input": {},
                "output": {},
                "raw": raw,
            }
            if not raw:
                reports.append(item)
                continue

            output = raw.get("output_trace") or raw.get("final_report") or {}
            if stage == "03_llm_prompt":
                item["summary"] = f"{raw.get('provider', '')} / {raw.get('model', '')}".strip(" /")
                item["output"] = {
                    "model": raw.get("model"),
                    "provider": raw.get("provider"),
                    "system_prompt": raw.get("system_prompt"),
                    "user_prompt": raw.get("user_prompt"),
                }
            elif stage == "03_llm_output":
                item["summary"] = (output.get("scenario_synthesis") or raw.get("raw_output") or "")[:200]
                item["output"] = self.compact_payload(raw)
            else:
                item["findings"] = (
                    raw.get("processing_trace")
                    or output.get("objective_findings")
                    or []
                )
                item["summary"] = output.get("summary") or ""
                item["input"] = self.compact_payload(raw.get("input_trace") or {})
                item["output"] = self.compact_payload(output)
                item["signals"] = {
                    key: value
                    for key, value in output.items()
                    if key.endswith("_signal") or key in {
                        "veto",
                        "veto_reason",
                        "price_reasonableness_signal",
                        "latest_risk_type",
                    }
                }
            reports.append(item)
        return reports

    def generate_mermaid_sequence(self) -> str:
        traces = self.load_traces()
        agents = []
        for key in traces.keys():
            if key.startswith("02_"):
                agent_name = key.replace("02_", "").capitalize()
                agents.append(agent_name)
                
        diagram = []
        diagram.append("sequenceDiagram")
        diagram.append("    participant User")
        diagram.append("    participant Orchestrator")
        
        for a in agents:
            diagram.append(f"    participant {a}Agent")
            
        diagram.append("    participant Synthesizer")
        diagram.append("    participant LLM")
        
        diagram.append("    User->>Orchestrator: Start Task")
        diagram.append("    Orchestrator->>Orchestrator: Ingest Data (Phase 1)")
        
        for a in agents:
            diagram.append(f"    Orchestrator->>{a}Agent: Send Input Data")
            diagram.append(f"    {a}Agent-->>Orchestrator: Return Report JSON")
            
        diagram.append("    Orchestrator->>Synthesizer: Forward All Reports")
        diagram.append("    Synthesizer->>LLM: Send System & User Prompt")
        diagram.append("    LLM-->>Synthesizer: Return Scenario Conclusion")
        diagram.append("    Synthesizer-->>Orchestrator: Return Final Synthesis")
        diagram.append("    Orchestrator-->>User: Output Result")
        
        return "\n".join(diagram)

    def generate_human_summary(self) -> str:
        traces = self.load_traces()
        summary = ["# Observability Trace Summary\n"]
        
        summary.append("## [Phase 2] Base Agents")
        for key in sorted(traces.keys()):
            if key.startswith("02_"):
                agent_name = key.replace("02_", "").capitalize()
                data = traces[key]
                summary.append(f"### {agent_name} Agent")
                summary.append("**Used Data Mapping:**")
                for k, v in data.get("input_trace", {}).items():
                    if isinstance(v, dict):
                        summary_parts = []
                        for sub_k, sub_v in v.items():
                            if sub_k == "raw_history" and isinstance(sub_v, list):
                                summary_parts.append(f"'{sub_k}': [list of {len(sub_v)} items]")
                            else:
                                summary_parts.append(f"'{sub_k}': {repr(sub_v)}")
                        summary.append(f"- `{k}`: {{{', '.join(summary_parts)}}}")
                    else:
                        summary.append(f"- `{k}`: {v}")
                summary.append("\n**Processing Summary (Judgement):**")
                for finding in data.get("processing_trace", []):
                    summary.append(f"- {finding}")
                summary.append("")
        
        if "03_llm_output" in traces:
            summary.append("## [Phase 3] Synthesizer & LLM")
            llm_trace = traces["03_llm_output"]
            report = llm_trace.get("final_report", {})
            conflicts = report.get("conflicting_evidence", [])
            has_conflict = len(conflicts) > 0 or "無法形成高信心推演" in llm_trace.get("raw_output", "")
            summary.append(f"**Has Conflict:** {has_conflict}")
            if has_conflict and conflicts:
                summary.append("**Conflict Details:**")
                for c in conflicts:
                    summary.append(f"- {c}")
            summary.append("\n**Final Synthesis:**")
            summary.append(llm_trace.get("raw_output", ""))
            
        return "\n".join(summary)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        task_id = sys.argv[1]
        v = TraceVisualizer(task_id)
        print(v.generate_human_summary())
        print("\n\n```mermaid\n" + v.generate_mermaid_sequence() + "\n```")
