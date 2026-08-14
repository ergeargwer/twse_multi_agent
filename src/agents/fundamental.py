from typing import Dict, Any

from src.core.rule_config import get_agent_rules


class FundamentalAgent:
    def __init__(self):
        self.is_active = True
        self.rules = get_agent_rules("fundamental_agent")
        
    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Fundamental Agent 已關閉，無法執行分析。")
            
        fundamentals = ingested_data.get("fundamentals", {})
        pe_ratio = fundamentals.get("pe_ratio")
        pe_ratio_5y_avg = fundamentals.get("pe_ratio_5y_avg")
        eps = fundamentals.get("eps", 0)
        rev_growth = fundamentals.get("monthly_revenue_growth_yoy", 0)
        pe_mult = self.rules["pe_attractive_multiplier"]
        rev_min = self.rules["revenue_achievement_min_ratio"]
        pe_high = self.rules["pe_high_threshold"]
        pe_low = self.rules["pe_low_threshold"]
        rev_strong = self.rules["revenue_growth_strong_pct"]
        
        # 1. pe_percentile_signal
        if pe_ratio is not None and pe_ratio_5y_avg is not None and pe_ratio_5y_avg > 0:
            if pe_ratio < pe_mult * pe_ratio_5y_avg:
                pe_percentile_signal = "估值具吸引力"
            else:
                pe_percentile_signal = "估值處於合理或偏高區間"
        else:
            pe_percentile_signal = "資料源待補"

        # 2. revenue_achievement_signal
        latest_rev = fundamentals.get("latest_revenue")
        last_year_rev = fundamentals.get("last_year_revenue")
        if latest_rev is not None and last_year_rev is not None and last_year_rev > 0:
            achievement_rate = latest_rev / last_year_rev
        elif rev_growth is not None:
            achievement_rate = 1.0 + (rev_growth / 100.0)
        else:
            achievement_rate = None
            
        if achievement_rate is not None:
            if achievement_rate > rev_min:
                revenue_achievement_signal = "符合預期"
            else:
                revenue_achievement_signal = "疑似價值陷阱"
        else:
            revenue_achievement_signal = "資料源待補"

        # 3. earnings_revision_signal
        earnings_revision_signal = "資料源待補"
        
        objective_findings = []
        if rev_growth is not None and rev_growth >= rev_strong:
            objective_findings.append("月營收呈現雙位數成長，歷史業績擴張。")
        elif rev_growth is not None and rev_growth < 0:
            objective_findings.append("月營收呈現衰退。")
            
        if pe_ratio is not None:
            if pe_ratio > pe_high:
                objective_findings.append("歷史本益比處於相對較高區間。")
            elif pe_ratio < pe_low:
                objective_findings.append("歷史本益比處於相對較低區間。")
                
        if pe_percentile_signal == "估值具吸引力":
            objective_findings.append(
                f"當前本益比 ({pe_ratio}) 低於5年平均本益比 ({pe_ratio_5y_avg}) 的 {pe_mult} 倍，估值具吸引力。"
            )
        if revenue_achievement_signal == "疑似價值陷阱":
            objective_findings.append(
                f"月營收表現低於去年同期{rev_min * 100:.0f}%，需留意疑似價值陷阱。"
            )
            
        report = {
            "agent_name": "Fundamental Agent",
            "metrics_extracted": ["pe_ratio", "eps", "monthly_revenue_growth_yoy", "pe_ratio_5y_avg", "latest_revenue", "last_year_revenue"],
            "objective_findings": objective_findings,
            "summary": f"基本面健康度評估完畢（EPS: {eps}, 營收成長率: {rev_growth}%），未涉及未來股價預估。",
            "pe_percentile_signal": pe_percentile_signal,
            "revenue_achievement_signal": revenue_achievement_signal,
            "earnings_revision_signal": earnings_revision_signal
        }
        return report

    def close(self):
        self.is_active = False
