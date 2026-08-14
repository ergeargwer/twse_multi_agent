from datetime import datetime, timedelta
from typing import Dict

class CooldownTracker:
    def __init__(self):
        # 儲存每個標的想交易的時間戳記
        self.intents: Dict[str, datetime] = {}

    def request_trade_intent(self, symbol: str) -> None:
        self.intents[symbol] = datetime.now()

    def is_cooldown_passed(self, symbol: str, hours: float = None) -> bool:
        if hours is None:
            from src.core.rule_config import get_agent_rules
            hours = float(get_agent_rules("discipline_agent")["cooldown_hours"])
        last_intent = self.intents.get(symbol)
        if not last_intent:
            return True
        elapsed = datetime.now() - last_intent
        return elapsed >= timedelta(hours=hours)
