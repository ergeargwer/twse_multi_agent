# -*- coding: utf-8 -*-
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.prompt_config import build_system_prompt, get_persona_version, load_persona
from src.core.rule_config import get_agent_rules, get_rules_version, load_rules
from src.agents.fundamental import FundamentalAgent
from src.agents.risk_veto import RiskVetoAgent
from src.core import risk


def test_load_rules_and_version():
    rules = load_rules(force_reload=True)
    assert rules["version"] == "1.0.0"
    assert get_rules_version() == "1.0.0"
    fund = get_agent_rules("fundamental_agent")
    assert fund["pe_attractive_multiplier"] == 1.5
    assert fund["revenue_achievement_min_ratio"] == 0.96
    print("ok load rules")


def test_missing_agent_key_raises():
    try:
        get_agent_rules("not_a_real_agent")
    except KeyError as exc:
        assert "not_a_real_agent" in str(exc)
        print("ok missing key")
        return
    raise AssertionError("缺少區塊時應拋 KeyError")


def test_fundamental_uses_yaml_threshold():
    agent = FundamentalAgent()
    report = agent.analyze({
        "fundamentals": {
            "pe_ratio": 14.0,
            "pe_ratio_5y_avg": 10.0,
            "eps": 1,
            "monthly_revenue_growth_yoy": 12,
            "latest_revenue": 100,
            "last_year_revenue": 100,
        }
    })
    assert report["pe_percentile_signal"] == "估值具吸引力"
    agent.close()
    print("ok fundamental threshold")


def test_risk_veto_concentration_from_yaml():
    agent = RiskVetoAgent()
    report = agent.analyze({
        "account_data_status": "ok",
        "symbol": "2330.TW",
        "expected_gain_pct": 30.0,
        "max_loss_pct": 10.0,
        "account_balance": {"cash": 700000.0},
        "position_list": [
            {"symbol": "2330", "cost": 300000.0, "unrealized_pnl": 0.0},
        ],
    })
    assert report["veto"] is False
    agent.close()

    profile = risk.calculate_risk_reward(30.0, 10.0)
    assert profile.is_qualified is True
    print("ok risk veto yaml")


def test_changing_rules_changes_judgment():
    """驗收：Agent 讀 self.rules，改門檻後判斷結果跟著變。"""
    ingested = {
        "fundamentals": {
            "pe_ratio": 14.0,
            "pe_ratio_5y_avg": 10.0,
            "eps": 1,
            "monthly_revenue_growth_yoy": 12,
            "latest_revenue": 100,
            "last_year_revenue": 100,
        }
    }
    agent = FundamentalAgent()
    default_report = agent.analyze(ingested)
    assert default_report["pe_percentile_signal"] == "估值具吸引力"
    agent.rules = dict(agent.rules)
    agent.rules["pe_attractive_multiplier"] = 1.1
    tight_report = agent.analyze(ingested)
    assert tight_report["pe_percentile_signal"] == "估值處於合理或偏高區間"
    agent.close()
    print("ok rules change judgment")


def test_all_phase2_agents_init():
    from src.agents.asset_allocation import AssetAllocationAgent
    from src.agents.behavior_risk import BehaviorRiskAgent
    from src.agents.discipline import DisciplineAgent
    from src.agents.event import EventCalendarAgent
    from src.agents.institutional import InstitutionalFlowAgent
    from src.agents.pricing_gatekeeper import PricingGatekeeperAgent
    from src.agents.technical import TechnicalAgent

    classes = [
        FundamentalAgent,
        PricingGatekeeperAgent,
        RiskVetoAgent,
        AssetAllocationAgent,
        InstitutionalFlowAgent,
        TechnicalAgent,
        BehaviorRiskAgent,
        DisciplineAgent,
        EventCalendarAgent,
    ]
    for cls in classes:
        inst = cls()
        assert inst.rules
        inst.close()
    print("ok nine agents init")


def test_persona_builds_same_constraints():
    persona = load_persona(force_reload=True)
    prompt = build_system_prompt(False, "")
    assert "樹之修行者" in prompt
    assert "輸出限制（非常重要）" in prompt
    for item in persona["output_constraints"]:
        assert item in prompt
    vetoed = build_system_prompt(True, "測試否決原因")
    assert "測試否決原因" in vetoed
    assert get_persona_version() == "1.0.0"
    print("ok persona")


if __name__ == "__main__":
    test_load_rules_and_version()
    test_missing_agent_key_raises()
    test_fundamental_uses_yaml_threshold()
    test_changing_rules_changes_judgment()
    test_all_phase2_agents_init()
    test_risk_veto_concentration_from_yaml()
    test_persona_builds_same_constraints()
    print("all rule/prompt config tests passed")
