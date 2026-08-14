from typing import Dict, Any

from src.core.rule_config import get_agent_rules


class InstitutionalFlowAgent:
    def __init__(self):
        self.is_active = True
        self.rules = get_agent_rules("institutional_flow_agent")
        
    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Institutional Flow Agent 已關閉，無法執行分析。")
            
        flow_data = ingested_data.get("institutional_flow", {})
        foreign = flow_data.get("foreign_investor", 0)
        trust = flow_data.get("investment_trust", 0)
        margin_change = flow_data.get("margin_balance_change", 0)
        
        # Calculate foreign_flow_reversal_signal using raw_history
        raw_history = flow_data.get("raw_history", [])
        foreign_flow_reversal_signal = "無明顯訊號"
        
        if len(raw_history) >= 5:
            last_2_days = raw_history[-2:]
            preceding_days = raw_history[-5:-2]
            
            last_2_sell = all(x.get("foreign_investor_net", 0) < 0 for x in last_2_days)
            sum_last_2_sell = sum(x.get("foreign_investor_net", 0) for x in last_2_days)
            
            preceding_buys = sum(1 for x in preceding_days if x.get("foreign_investor_net", 0) > 0)
            sum_preceding_buy = sum(x.get("foreign_investor_net", 0) for x in preceding_days)
            
            if last_2_sell and preceding_buys >= 2 and sum_preceding_buy > 0:
                min_sell = self.rules["reversal_min_sell_amount"]
                sell_ratio = self.rules["reversal_sell_vs_buy_ratio"]
                if sum_last_2_sell < -min_sell or abs(sum_last_2_sell) > sell_ratio * sum_preceding_buy:
                    foreign_flow_reversal_signal = "資金轉向警訊"

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
            
        if foreign_flow_reversal_signal == "資金轉向警訊":
            objective_findings.append("外資由連續買超快速轉為連續大額賣超，觸發資金轉向警訊。")
            
        report = {
            "agent_name": "Institutional Flow Agent",
            "metrics_extracted": ["foreign_investor", "investment_trust", "margin_balance_change"],
            "objective_findings": objective_findings,
            "summary": f"籌碼面狀態描述完畢（外資淨部位：{foreign}，投信淨部位：{trust}）。報告僅客觀反映單日至多日之籌碼流動事實，不對未來股價進行背書或因果推測。",
            "foreign_flow_reversal_signal": foreign_flow_reversal_signal
        }
        return report

    def close(self):
        self.is_active = False
