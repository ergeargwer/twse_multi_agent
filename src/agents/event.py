from typing import Dict, Any

class EventCalendarAgent:
    def __init__(self):
        self.is_active = True
        
    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("ETF & Event Agent 已關閉，無法執行分析。")
            
        events_data = ingested_data.get("calendar_events", {})
        days_to_ex_div = events_data.get("days_to_ex_dividend", -1)
        days_to_recall = events_data.get("days_to_margin_recall", -1)
        etf_rebalance = events_data.get("in_etf_rebalance_watchlist", False)
        
        objective_findings = []
        if days_to_recall > 0 and days_to_recall <= 10:
            objective_findings.append(f"距離融券最後強制回補日僅剩 {days_to_recall} 日，需留意空單強迫買進之制度性軋空/買盤現象。")
        
        if days_to_ex_div > 0 and days_to_ex_div <= 30:
            objective_findings.append(f"距離除權息交易日約 {days_to_ex_div} 日，可能面臨高殖利率參與買盤或持股避稅棄息賣壓之換手。")
            
        if etf_rebalance:
            objective_findings.append("該標的目前名列「巨型高股息 ETF」之潛在成分股增刪觀察名單中，極易受到與基本面無關之被動式資金拋售或灌入干擾。")
        else:
            objective_findings.append("短期內未見重大 ETF 季配/半年配換股審核重疊風險。")
            
        report = {
            "agent_name": "ETF & Event Agent",
            "metrics_extracted": ["days_to_margin_recall", "days_to_ex_dividend", "in_etf_rebalance_watchlist"],
            "objective_findings": objective_findings,
            "summary": "特有行事曆與事件風險梳理完畢。本報告僅指出『潛在被動資金或制度性行為發生之可能性』，嚴格禁止對事件發生後之價格方向、漲跌幅度做任何推測。"
        }
        return report

    def close(self):
        self.is_active = False
