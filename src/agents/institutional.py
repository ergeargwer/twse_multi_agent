from typing import Dict, Any

class InstitutionalFlowAgent:
    def __init__(self):
        self.is_active = True
        
    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Institutional Flow Agent 已關閉，無法執行分析。")
            
        flow_data = ingested_data.get("institutional_flow", {})
        foreign = flow_data.get("foreign_investor", 0)
        trust = flow_data.get("investment_trust", 0)
        margin_change = flow_data.get("margin_balance_change", 0)
        
        objective_findings = []
        if foreign > 0 and trust > 0:
            objective_findings.append("外資與投信同道，三大法人籌碼整體呈現匯入狀態。")
        elif foreign < 0 and trust < 0:
            objective_findings.append("外資與投信同步站在賣方，法人籌碼呈現流出狀態。")
        else:
            objective_findings.append("外資與投信買賣超方向分歧，法人籌碼流向未呈現明顯共識。")
            
        if margin_change > 0:
            objective_findings.append("融資餘額增加，顯示散戶/槓桿籌碼的部位參與度提升。")
        elif margin_change < 0:
            objective_findings.append("融資餘額減少，顯示籌碼沉澱或散戶部位呈現退場現象。")
            
        report = {
            "agent_name": "Institutional Flow Agent",
            "metrics_extracted": ["foreign_investor", "investment_trust", "margin_balance_change"],
            "objective_findings": objective_findings,
            "summary": f"籌碼面狀態描述完畢（外資淨部位：{foreign}，投信淨部位：{trust}）。報告僅客觀反映單日至多日之籌碼流動事實，不對未來股價進行背書或因果推測。"
        }
        return report

    def close(self):
        self.is_active = False
