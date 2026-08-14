from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class RiskProfile:
    expected_gain_pct: float
    max_loss_pct: float
    ratio: float
    is_qualified: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expected_gain_pct": self.expected_gain_pct,
            "max_loss_pct": self.max_loss_pct,
            "ratio": self.ratio,
            "is_qualified": self.is_qualified
        }

def calculate_risk_reward(
    expected_gain_pct: float,
    max_loss_pct: float,
    min_ratio: float = None,
) -> RiskProfile:
    if min_ratio is None:
        from src.core.rule_config import get_agent_rules
        min_ratio = get_agent_rules("risk_veto_agent")["min_risk_reward_ratio"]
    if max_loss_pct == 0:
        ratio = float("inf")
    else:
        ratio = expected_gain_pct / max_loss_pct
    is_qualified = ratio >= min_ratio
    return RiskProfile(
        expected_gain_pct=expected_gain_pct,
        max_loss_pct=max_loss_pct,
        ratio=ratio,
        is_qualified=is_qualified
    )

def suggest_position_step(current_position: float) -> float:
    from src.core.rule_config import get_agent_rules
    rules = get_agent_rules("asset_allocation_agent")
    switch_pct = rules["position_step_switch_pct"]
    if current_position <= switch_pct:
        return rules["position_step_small"]
    return rules["position_step_large"]
