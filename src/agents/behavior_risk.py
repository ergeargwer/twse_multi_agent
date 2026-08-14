# -*- coding: utf-8 -*-
from typing import Any, Dict

from src.analysis.behavior_risk import run_behavior_risk
from src.core.rule_config import get_agent_rules


class BehaviorRiskAgent:
    """Phase 2 行為風險觀察器：只讀價量歷史，不看其他 Agent 報告。"""

    def __init__(self):
        self.is_active = True
        self.rules = get_agent_rules("behavior_risk_agent")

    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Behavior Risk Agent 已關閉，無法執行分析。")

        price_data = ingested_data.get("price_action") or {}
        raw_history = price_data.get("raw_history") or []
        threshold_pct = ingested_data.get("ma20_dev_threshold_pct")
        if threshold_pct is None:
            threshold_pct = self.rules["ma20_overbought_dev_pct"]

        result = run_behavior_risk(raw_history, ma20_dev_threshold_pct=threshold_pct)

        report = {
            "agent_name": "Behavior Risk Agent",
            "metrics_extracted": ["ma20", "ma20_dev_pct", "atr", "support", "resistance", "volume_ma20"],
            "objective_findings": result["findings"],
            "summary": result["summary"],
            "behavior_risk_signal": result["signal"],
            "latest_risk_type": result["latest_risk_type"],
            "latest_risk_reason": result["latest_risk_reason"],
            "recent_events": result["recent_events"],
            "high_chase_count": result["high_chase_count"],
            "low_sell_count": result["low_sell_count"],
            "bars_analyzed": result["bars_analyzed"],
            "oversold_count": result.get("oversold_count", 0),
            "extreme_oversold_count": result.get("extreme_oversold_count", 0),
            "ma20_dev_threshold_pct": result["ma20_dev_threshold_pct"],
            "strict_disclaimer": "所有分析僅為市場行為風險提示，非投資建議，非主力判斷。",
        }
        return report

    def close(self):
        self.is_active = False
