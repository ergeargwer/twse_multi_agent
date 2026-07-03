from typing import Dict, Any

class EventCalendarAgent:
    def __init__(self):
        self.is_active = True
        
    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("ETF & Event Agent 已關閉，無法執行分析。")
            
        events_data = ingested_data.get("calendar_events", {})
        days_to_ex_div = events_data.get("days_to_ex_dividend") or -1
        days_to_recall = events_data.get("days_to_margin_recall") or -1
        etf_rebalance = events_data.get("in_etf_rebalance_watchlist") or False
        
        margin_maintenance_ratio = events_data.get("margin_maintenance_ratio")
        has_large_buyback = events_data.get("has_large_buyback")
        
        margin_ratio_signal = "無明顯訊號"
        if margin_maintenance_ratio is not None:
            if 140.0 <= margin_maintenance_ratio <= 150.0:
                margin_ratio_signal = "恐慌指標鈍化"
        else:
            margin_ratio_signal = "資料源待補"
            
        buyback_signal = "無明顯訊號"
        if has_large_buyback is not None:
            if has_large_buyback:
                buyback_signal = "信心指標浮現"
        else:
            buyback_signal = "資料源待補"

        objective_findings = []
        if days_to_recall > 0 and days_to_recall <= 10:
            objective_findings.append(f"距離融券最後強制回補日僅剩 {days_to_recall} 日，需留意空單強迫買進之制度性軋空/買盤現象。")
        
        if days_to_ex_div > 0 and days_to_ex_div <= 30:
            objective_findings.append(f"距離除權息交易日約 {days_to_ex_div} 日，可能面臨高殖利率參與買盤或持股避稅棄息賣壓之換手。")
            
        if etf_rebalance:
            objective_findings.append("該標的目前名列「巨型高股息 ETF」之潛在成分股增刪觀察名單中，極易受到與基本面無關之被動式資金拋售或灌入干擾。")
        else:
            objective_findings.append("短期內未見重大 ETF 季配/半年配換股審核重疊風險。")
            
        if margin_ratio_signal == "恐慌指標鈍化":
            objective_findings.append("融資維持率落在 140%-150% 區間止穩，恐慌指標鈍化。")
        if buyback_signal == "信心指標浮現":
            objective_findings.append("大型公司宣布庫藏股，信心指標浮現。")
            
        report = {
            "agent_name": "ETF & Event Agent",
            "metrics_extracted": ["days_to_margin_recall", "days_to_ex_dividend", "in_etf_rebalance_watchlist"],
            "objective_findings": objective_findings,
            "summary": "特有行事曆與事件風險梳理完畢。本報告僅指出『潛在被動資金或制度性行為發生之可能性』，嚴格禁止對事件發生後之價格方向、漲跌幅度做任何推測。",
            "margin_ratio_signal": margin_ratio_signal,
            "buyback_signal": buyback_signal
        }
        return report

    def close(self):
        self.is_active = False
