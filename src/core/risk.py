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

def calculate_risk_reward(expected_gain_pct: float, max_loss_pct: float) -> RiskProfile:
    if max_loss_pct == 0:
        ratio = float("inf")
    else:
        ratio = expected_gain_pct / max_loss_pct
    is_qualified = ratio >= 3.0
    return RiskProfile(
        expected_gain_pct=expected_gain_pct,
        max_loss_pct=max_loss_pct,
        ratio=ratio,
        is_qualified=is_qualified
    )

def suggest_position_step(current_position: float) -> float:
    # 每次調節幅度依據目前部位決定：若小於等於 40% 建議調節 20%，否則建議調節 10%
    # 固定回傳 0.1 或 0.2
    if current_position <= 0.4:
        return 0.2
    return 0.1
