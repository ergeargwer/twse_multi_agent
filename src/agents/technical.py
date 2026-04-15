from typing import Dict, Any

class TechnicalAgent:
    def __init__(self):
        self.is_active = True
        
    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Technical Agent 已關閉，無法執行分析。")
            
        price_data = ingested_data.get("price_action", {})
        current_close = price_data.get("close", 0)
        ma5 = price_data.get("ma5", 805)
        ma20 = price_data.get("ma20", 790)
        ma60 = price_data.get("ma60", 760)
        
        objective_findings = []
        if ma5 > ma20 > ma60:
            objective_findings.append("短期、中期與長期均線 (5MA>20MA>60MA) 呈現多頭排列狀態。")
        elif ma5 < ma20 < ma60:
            objective_findings.append("各級均線反轉，目前呈現空頭排列。")
        else:
            objective_findings.append("各級均線目前處於糾結且方向不明朗之盤整階段。")
            
        if current_close >= ma5:
            objective_findings.append("當前收盤價位於 5 日均線之上，動能指標偏向強勢。")
        else:
            objective_findings.append("當前收盤價已失守 5 日短天期均線。")
            
        report = {
            "agent_name": "Technical Agent",
            "metrics_extracted": ["close_price", "ma5", "ma20", "ma60"],
            "objective_findings": objective_findings,
            "summary": f"技術面型態判定完成（目前收盤價為 {current_close}）。報告僅記錄當前量價與均線特徵，不含未來走勢預估。"
        }
        return report

    def close(self):
        self.is_active = False
