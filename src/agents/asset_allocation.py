# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from src.core import risk
from src.core.rule_config import get_agent_rules


class AssetAllocationAgent:
    def __init__(self):
        self.is_active = True
        self.rules = get_agent_rules("asset_allocation_agent")

    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Asset Allocation Agent 已關閉。")

        account_data_status = ingested_data.get("account_data_status", "not_configured")
        
        if account_data_status != "ok":
            return {
                "agent_name": "Asset Allocation Agent",
                "data_available": False,
                "cash_ratio": None,
                "position_concentration": {},
                "concentration_alerts": [],
                "suggested_position_step": None,
                "objective_findings": ["帳戶資料目前不可用，無法進行資產配置分析。"],
                "summary": "資產配置分析未執行（帳戶資料不可用）。"
            }

        symbol = ingested_data.get("symbol", "未知標的")
        target_id = symbol.split(".")[0]
        
        balance = ingested_data.get("account_balance") or {"cash": 0.0, "total_limit": 0.0}
        position_list = ingested_data.get("position_list") or []

        cash = float(balance.get("cash", 0.0))
        
        # 計算持股總市值
        position_values = {}
        total_position_value = 0.0
        target_position_val = 0.0

        for pos in position_list:
            pos_symbol = pos.get("symbol", "")
            shares = pos.get("shares", 0)
            cost = pos.get("cost", 0.0)
            unrealized_pnl = pos.get("unrealized_pnl", 0.0)
            
            # 部位市值 = 成本 + 未實現損益
            market_val = cost + unrealized_pnl
            position_values[pos_symbol] = market_val
            total_position_value += market_val
            
            if pos_symbol == target_id:
                target_position_val = market_val

        total_assets = cash + total_position_value
        
        if total_assets == 0:
            cash_ratio = 1.0
            position_concentration = {}
        else:
            cash_ratio = cash / total_assets
            position_concentration = {k: v / total_assets for k, v in position_values.items()}

        alert_pct = self.rules["concentration_alert_pct"]
        concentration_alerts = []
        objective_findings = []
        objective_findings.append(f"現金部位金額: {cash:,.0f} 元，占總資產比例: {cash_ratio * 100:.2f}%。")
        objective_findings.append(f"持股總市值: {total_position_value:,.0f} 元，占總資產比例: {(1.0 - cash_ratio) * 100:.2f}%。")

        for pos_symbol, ratio in position_concentration.items():
            if ratio > alert_pct:
                concentration_alerts.append(
                    f"持股 {pos_symbol} 占比為 {ratio * 100:.1f}%，超過 {alert_pct * 100:.1f}% 的集中度警戒線。"
                )
                objective_findings.append(f"警訊：持股 {pos_symbol} 占比高達 {ratio * 100:.1f}%，處於過度集中狀態。")
            else:
                objective_findings.append(f"持股 {pos_symbol} 占比為 {ratio * 100:.1f}%，在安全範圍內。")

        # 呼叫 risk.py 計算建議調節部位比例
        target_concentration = position_concentration.get(target_id, 0.0)
        suggested_step = risk.suggest_position_step(target_concentration)

        report = {
            "agent_name": "Asset Allocation Agent",
            "cash_ratio": cash_ratio,
            "position_concentration": position_concentration,
            "concentration_alerts": concentration_alerts,
            "suggested_position_step": suggested_step,
            "objective_findings": objective_findings,
            "summary": f"資產配置分析完畢（當前目標標的集中度: {target_concentration * 100:.2f}%，建議單次調節幅度: {suggested_step * 100:.0f}%）。"
        }
        return report

    def close(self):
        self.is_active = False
