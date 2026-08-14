# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.analysis.behavior_risk import run_behavior_risk, SIGNAL_HIGH_CHASE, SIGNAL_LOW_SELL, SIGNAL_NONE
from src.agents.behavior_risk import BehaviorRiskAgent
from src.core.context import SharedContext
from src.orchestrator.pipeline import run_agent_in_thread
from src.trace.collector import TraceCollector


def _bars(closes, volumes=None, lows=None, highs=None):
    start = datetime(2026, 1, 2)
    history = []
    for i, close in enumerate(closes):
        open_px = close
        high = highs[i] if highs is not None else close
        low = lows[i] if lows is not None else close
        vol = volumes[i] if volumes is not None else 1000
        history.append({
            "date": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
            "open": float(open_px),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": float(vol),
        })
    return history


def test_empty_history():
    result = run_behavior_risk([])
    assert result["signal"] == SIGNAL_NONE
    assert result["bars_analyzed"] == 0
    agent = BehaviorRiskAgent()
    report = agent.analyze({"price_action": {"raw_history": []}})
    assert report["behavior_risk_signal"] == SIGNAL_NONE
    agent.close()
    print("ok empty")


def test_high_chase_vwap_deviation():
    closes = [100.0] * 25 + [120.0]
    volumes = [1000] * 26
    result = run_behavior_risk(_bars(closes, volumes), vwap_dev_threshold_pct=5.0)
    assert result["high_chase_count"] >= 1
    assert result["latest_risk_type"] == "High Chase"
    assert result["signal"] == SIGNAL_HIGH_CHASE
    print("ok high chase")


def test_low_sell_support_breakdown_no_volume():
    # 前段墊高支撐，最後一根跌破且量能萎縮
    closes = [100.0] * 10 + [110.0] * 14 + [90.0]
    lows = [99.0] * 10 + [108.0] * 14 + [88.0]
    highs = [101.0] * 10 + [112.0] * 14 + [91.0]
    volumes = [2000] * 24 + [400]
    result = run_behavior_risk(_bars(closes, volumes, lows=lows, highs=highs), vwap_dev_threshold_pct=15.0)
    assert result["low_sell_count"] >= 1
    assert result["latest_risk_type"] == "Low Sell"
    assert result["signal"] == SIGNAL_LOW_SELL
    print("ok low sell")


def test_phase_two_writes_behavior_report(tmp_path=None):
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    closes = [100.0] * 25 + [120.0]
    ingested = {
        "symbol": "2327.TW",
        "vwap_dev_threshold_pct": 5.0,
        "price_action": {"raw_history": _bars(closes)},
    }
    context = SharedContext(task_id="test_behavior_risk", symbol="2327.TW")
    context.write("ingested_data", ingested)
    collector = TraceCollector("test_behavior_risk")
    run_agent_in_thread(BehaviorRiskAgent, context, "behavior_risk_report", collector, "02_behavior_risk")
    report = context.read("behavior_risk_report")
    assert report is not None
    assert report["agent_name"] == "Behavior Risk Agent"
    assert report["behavior_risk_signal"] == SIGNAL_HIGH_CHASE
    print("ok pipeline thread")


if __name__ == "__main__":
    test_empty_history()
    test_high_chase_vwap_deviation()
    test_low_sell_support_breakdown_no_volume()
    test_phase_two_writes_behavior_report()
    print("all behavior risk tests passed")
