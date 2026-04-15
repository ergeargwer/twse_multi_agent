from typing import Dict, Any

class FundamentalAgent:
    def __init__(self):
        self.is_active = True
        
    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Fundamental Agent 已關閉，無法執行分析。")
            
        fundamentals = ingested_data.get("fundamentals", {})
        pe_ratio = fundamentals.get("pe_ratio", 0)
        eps = fundamentals.get("eps", 0)
        rev_growth = fundamentals.get("monthly_revenue_growth_yoy", 0)
        
        objective_findings = []
        if rev_growth >= 10:
            objective_findings.append("月營收呈現雙位數成長，歷史業績擴張。")
        elif rev_growth < 0:
            objective_findings.append("月營收呈現衰退。")
            
        if pe_ratio > 20:
            objective_findings.append("歷史本益比處於相對較高區間。")
        elif pe_ratio < 10:
            objective_findings.append("歷史本益比處於相對較低區間。")
            
        report = {
            "agent_name": "Fundamental Agent",
            "metrics_extracted": ["pe_ratio", "eps", "monthly_revenue_growth_yoy"],
            "objective_findings": objective_findings,
            "summary": f"基本面健康度評估完畢（EPS: {eps}, 營收成長率: {rev_growth}%），未涉及未來股價預估。"
        }
        return report

    def close(self):
        self.is_active = False
