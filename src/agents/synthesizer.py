from typing import Dict, Any, List

class DecisionSynthesizerAgent:
    def __init__(self):
        self.is_active = True
        
    def _extract_findings(self, report: Dict[str, Any]) -> List[str]:
        if not report:
            return []
        return report.get("objective_findings", [])

    def synthesize(self, context_store: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Decision Synthesizer Agent 已關閉，無法執行彙整。")
            
        fund_report = context_store.get("fundamental_report")
        tech_report = context_store.get("technical_report")
        flow_report = context_store.get("institutional_flow_report")
        event_report = context_store.get("event_calendar_report")
        
        all_findings = [
            *self._extract_findings(fund_report),
            *self._extract_findings(tech_report),
            *self._extract_findings(flow_report),
            *self._extract_findings(event_report)
        ]
        
        pos_keywords = ["成長", "多頭", "匯入", "買超", "軋空"]
        neg_keywords = ["衰退", "空頭", "流出", "賣超", "失守", "棄息", "偏高"]
        
        aligned_evidence = []
        conflicting_evidence = []
        
        p_count, n_count = 0, 0
        for text in all_findings:
            if any(k in text for k in pos_keywords):
                p_count += 1
            if any(k in text for k in neg_keywords):
                n_count += 1
            conflicting_evidence.append(text) 
                
        if (p_count > 0 and n_count > 0 and abs(p_count - n_count) <= 1) or (p_count == 0 and n_count == 0):
            scenario_conclusion = "結論：各維度論點存在強烈矛盾與互相抵銷（如：獲利成長但遭遇籌碼賣壓），無法形成高信心推演。目前系統落入多空膠著之盲區。"
            aligned_evidence = []
        else:
            scenario_conclusion = "結論：目前市場具備部分維度之明確趨勢特徵，惟須嚴防突發性事件及特定反向風險指標之發酵。"
            aligned_evidence = all_findings
            conflicting_evidence = []

        report = {
            "agent_name": "Decision Synthesizer Agent",
            "process": "conflict_resolution_and_alignment",
            "inputs_parsed": ["fundamental", "technical", "institutional", "event"],
            "aligned_evidence": aligned_evidence,
            "conflicting_evidence": conflicting_evidence,
            "scenario_synthesis": scenario_conclusion,
            "strict_disclaimer": "【系統警告】本綜合推演報告僅基於客觀數據聚集，不得作為交易投資建議、股價點位判斷或實盤操作依據。"
        }
        return report

    def close(self):
        self.is_active = False
