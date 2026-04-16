import os
import json
import requests
from typing import Dict, Any

class DecisionSynthesizerAgent:
    def __init__(self):
        self.is_active = True
        
    def synthesize(self, context_store: Dict[str, Any], collector=None) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Decision Synthesizer Agent 已關閉，無法執行彙整。")
            
        fund_report = context_store.get("fundamental_report") or {}
        tech_report = context_store.get("technical_report") or {}
        flow_report = context_store.get("institutional_flow_report") or {}
        event_report = context_store.get("event_calendar_report") or {}
        
        system_prompt = (
            "你是一個系統分析文字生成引擎。你的角色定位僅為「整理、排序與對齊衝突」，不得自行推斷投資結論。\n"
            "嚴格禁止：\n"
            "- 不得產生 Buy / Sell / 看多 / 看空 等投資建議語句。\n"
            "- 不得新增原始資料中不存在的觀點或預測價格。\n"
            "輸出要求：\n"
            "- 明確標示不確定性元素與可能的衝突。\n"
            "- 若資料存在重大矛盾，必須允許並輸出「無法形成高信心推演」。\n"
            "請基於以下 JSON 報告進行客觀之文字彙總。"
        )
        
        user_prompt = json.dumps({
            "fundamental": fund_report,
            "technical": tech_report,
            "institutional": flow_report,
            "event": event_report
        }, ensure_ascii=False, indent=2)
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "google/gemma-4-31b-it",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        
        scenario_conclusion = ""
        
        try:
            r = requests.post(url, headers=headers, json=data, timeout=30)
            if r.status_code == 200:
                resp_json = r.json()
                scenario_conclusion = resp_json["choices"][0]["message"]["content"]
            else:
                scenario_conclusion = f"LLM API 請求失敗 (HTTP {r.status_code})。可能為缺少金鑰或模型不支援。"
        except Exception as e:
            scenario_conclusion = f"LLM API 請求發生例外錯誤: {str(e)}"
            
        # 從各報告匯總客觀數據點
        all_findings = []
        for rpt in [fund_report, tech_report, flow_report, event_report]:
            all_findings.extend(rpt.get("objective_findings", []))

        report = {
            "agent_name": "Decision Synthesizer Agent",
            "process": "conflict_resolution_and_alignment",
            "inputs_parsed": ["fundamental", "technical", "institutional", "event"],
            "aligned_evidence": all_findings,
            "conflicting_evidence": [],
            "scenario_synthesis": scenario_conclusion,
            "strict_disclaimer": "【系統警告】本綜合推演報告僅基於客觀數據聚集，不得作為交易投資建議、股價點位判斷或實盤操作依據。"
        }
        
        if collector:
            collector.record_llm_trace(
                model="google/gemma-4-31b-it",
                provider="OpenRouter",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_output=scenario_conclusion,
                final_report=report
            )
            
        return report

    def close(self):
        self.is_active = False
