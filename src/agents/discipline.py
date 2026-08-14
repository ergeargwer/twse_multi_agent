# -*- coding: utf-8 -*-
from typing import Dict, Any, List

from src.core.rule_config import get_agent_rules


class DisciplineAgent:
    def __init__(self):
        self.is_active = True
        self.rules = get_agent_rules("discipline_agent")

    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Discipline Agent 已關閉。")

        history = ingested_data.get("journal_history") or []
        cooldown_passed = ingested_data.get("cooldown_passed", True)

        # 1. 檢查情緒化交易傾向
        # 近期日記的 emotion 欄位關鍵字檢查
        keywords = ["焦慮", "恐慌", "亢奮", "衝動", "貪婪", "害怕", "生氣", "挫折", "後悔", "盲目", "興奮"]
        lookback = int(self.rules["emotional_lookback_entries"])
        trigger_count = int(self.rules["emotional_trigger_count"])
        recent_entries = history[-lookback:]
        emotional_count = 0
        
        for entry in recent_entries:
            emotion = entry.get("emotion", "")
            if any(kw in emotion for kw in keywords):
                emotional_count += 1

        if len(recent_entries) >= trigger_count and emotional_count >= trigger_count:
            emotional_trading_pattern_signal = "情緒化交易傾向偏高"
        else:
            emotional_trading_pattern_signal = "情緒化交易傾向正常"

        # 2. 整合交易冷卻提醒
        cooldown_reminder = ""
        if not cooldown_passed:
            cooldown_reminder = "距離您上次對此標的產生交易衝動尚未滿一天，建議先離線散步 10 分鐘"

        objective_findings = []
        objective_findings.append(
            f"歷史日記分析數量: {len(history)} 筆（評估近期 {lookback} 筆中有 {emotional_count} 筆含有情緒波動紀錄）。"
        )
        objective_findings.append(f"情緒化交易傾向評估: {emotional_trading_pattern_signal}。")
        
        if cooldown_reminder:
            objective_findings.append(f"交易冷卻提醒: {cooldown_reminder}。")
        else:
            objective_findings.append("交易冷卻狀態: 已過冷卻期或未曾交易，無冷卻警訊。")

        report = {
            "agent_name": "Execution Discipline Agent",
            "emotional_trading_pattern_signal": emotional_trading_pattern_signal,
            "cooldown_reminder": cooldown_reminder,
            "objective_findings": objective_findings,
            "summary": f"執行紀律把關完成（情緒交易狀態: {emotional_trading_pattern_signal}，冷卻提醒狀態: {'有' if cooldown_reminder else '無'}）。"
        }
        return report

    def close(self):
        self.is_active = False
