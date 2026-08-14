# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from src.core import risk
from src.core.rule_config import get_agent_rules


class RiskVetoAgent:
    def __init__(self):
        self.is_active = True
        self.rules = get_agent_rules("risk_veto_agent")

    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Risk Veto Agent 已關閉。")

        account_data_status = ingested_data.get("account_data_status", "not_configured")
        
        if account_data_status != "ok":
            veto = True
            if account_data_status == "not_configured":
                reason = "未設定 Shioaji 帳戶金鑰，系統無真實帳戶資料可供風控判斷，已預設攔截，僅能提供不涉及部位集中度的一般性分析。"
            else:
                error_detail = ingested_data.get("account_data_error", "未知錯誤")
                reason = f"帳戶資料查詢失敗（{error_detail}），系統無法確認實際部位與資金水位，基於安全考量已預設攔截。"
            
            report = {
                "agent_name": "Risk Veto Agent",
                "veto": True,
                "veto_reason": reason,
                "objective_findings": [f"風控攔截：{reason}"],
                "summary": "風控煞車評估完成（因帳戶資料不可用，預設為否決狀態）。"
            }
            return report

        symbol = ingested_data.get("symbol", "未知標的")
        target_id = symbol.split(".")[0]
        
        expected_gain = ingested_data.get("expected_gain_pct", 30.0)
        max_loss = ingested_data.get("max_loss_pct", 10.0)
        
        balance = ingested_data.get("account_balance") or {"cash": 0.0, "total_limit": 0.0}
        position_list = ingested_data.get("position_list") or []

        min_ratio = self.rules["min_risk_reward_ratio"]
        max_conc = self.rules["max_position_concentration_pct"]
        # 1. 檢查風暴比門檻
        profile = risk.calculate_risk_reward(expected_gain, max_loss, min_ratio=min_ratio)
        
        # 2. 檢查目標部位集中度是否超過上限
        cash = float(balance.get("cash", 0.0))
        total_position_val = 0.0
        target_position_val = 0.0
        
        for pos in position_list:
            pos_symbol = pos.get("symbol", "")
            cost = pos.get("cost", 0.0)
            unrealized_pnl = pos.get("unrealized_pnl", 0.0)
            m_val = cost + unrealized_pnl
            total_position_val += m_val
            if pos_symbol == target_id:
                target_position_val = m_val

        total_assets = cash + total_position_val
        target_concentration = target_position_val / total_assets if total_assets > 0 else 0.0

        veto = False
        veto_reasons = []
        objective_findings = []

        if not profile.is_qualified:
            veto = True
            reason_msg = (
                f"預期風暴比為 {profile.ratio:.2f}:1，未達 {min_ratio:.2f}:1 的風控安全底線 "
                f"(預估漲幅: {expected_gain}%, 可容忍停損: {max_loss}%)。"
            )
            veto_reasons.append(reason_msg)
            objective_findings.append(f"風控攔截：{reason_msg}")
        else:
            objective_findings.append(f"風暴比檢測通過：{profile.ratio:.2f}:1，符合安全標準。")

        if target_concentration > max_conc:
            veto = True
            reason_msg = (
                f"目標標的 {target_id} 占總資產比率達 {target_concentration * 100:.2f}%，"
                f"已超過單一部位 {max_conc * 100:.1f}% 的風控上限。"
            )
            veto_reasons.append(reason_msg)
            objective_findings.append(f"風控攔截：{reason_msg}")
        else:
            objective_findings.append(
                f"部位集中度檢測通過：目標標的占比 {target_concentration * 100:.2f}%，"
                f"未達 {max_conc * 100:.1f}% 上限。"
            )

        report = {
            "agent_name": "Risk Veto Agent",
            "veto": veto,
            "veto_reason": " 且 ".join(veto_reasons) if veto_reasons else "",
            "objective_findings": objective_findings,
            "summary": f"風控煞車評估完成（否決狀態: {veto}）。"
        }
        return report

    def close(self):
        self.is_active = False
