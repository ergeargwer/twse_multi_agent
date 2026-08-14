# -*- coding: utf-8 -*-
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.integrations.cli_collectors import (
    canonicalize_title,
    canonicalize_url,
    extract_json_value,
    items_from_payload,
    merge_items,
    probe_collectors,
)
from src.agents.event import EventCalendarAgent


def test_extract_json_from_fence_and_wrapper():
    raw = '前言\n```json\n{"items":[{"title":"庫藏股","summary":"公司買回","kind":"buyback"}]}\n```\n'
    payload = extract_json_value(raw)
    items = items_from_payload(payload)
    assert items[0]["title"] == "庫藏股"

    grok_wrap = {
        "text": '{"items":[{"title":"除息","summary":"即將除息","kind":"dividend","url":"https://a.example/x"}]}',
        "stopReason": "end_turn",
    }
    items = items_from_payload(grok_wrap)
    assert items[0]["kind"] == "dividend"

    structured = {"structuredOutput": {"items": [{"title": "x", "summary": "y", "kind": "news"}]}, "text": "{}"}
    assert items_from_payload(structured)[0]["title"] == "x"

    gemini_wrap = {"session_id": "abc", "response": '{"items":[{"title":"測試","summary":"摘要","kind":"other"}]}'}
    assert items_from_payload(gemini_wrap)[0]["title"] == "測試"
    print("ok extract")


def test_merge_dedup_by_url_and_title():
    grok = [
        {"title": "國巨庫藏股", "url": "https://News.example.com/a?utm_source=x", "summary": "短", "kind": "buyback"},
        {"title": "只有 Grok", "url": "https://g.example/1", "summary": "g", "kind": "news"},
    ]
    gemini = [
        {"title": "國巨庫藏股", "url": "https://news.example.com/a", "summary": "較長的摘要內容", "kind": "buyback"},
        {"title": "只有 Gemini", "url": "https://m.example/2", "summary": "m", "kind": "etf"},
    ]
    merged = merge_items({"grok": grok, "gemini": gemini})
    assert len(merged) == 3
    both = [item for item in merged if item["agreement"] == "both"]
    assert len(both) == 1
    assert both[0]["summary"] == "較長的摘要內容"
    assert set(both[0]["sources"]) == {"grok", "gemini"}
    assert canonicalize_url("https://News.example.com/a?utm_source=x") == "https://news.example.com/a"
    assert canonicalize_title("國 巨 庫藏股") == canonicalize_title("國巨庫藏股")
    print("ok merge")


def test_event_agent_reads_open_source():
    agent = EventCalendarAgent()
    report = agent.analyze({
        "calendar_events": {},
        "open_source_events": {
            "status": "partial",
            "both_count": 1,
            "items": [
                {
                    "title": "庫藏股公告",
                    "summary": "董事會通過買回",
                    "kind": "buyback",
                    "date": "2026-08-10",
                    "sources": ["grok", "gemini"],
                    "agreement": "both",
                    "url": "https://example.com/a",
                    "quality": "unverified",
                }
            ],
        },
    })
    assert report["open_source_signal"] == "雙源交叉印證"
    assert any("雙源交叉" in line for line in report["objective_findings"])
    agent.close()
    print("ok event agent")


def test_event_agent_without_open_source():
    agent = EventCalendarAgent()
    report = agent.analyze({"calendar_events": {}})
    assert report["open_source_signal"] == "無明顯訊號"
    agent.close()
    print("ok event agent empty")


def test_probe_does_not_crash():
    status = probe_collectors()
    assert "grok" in status and "gemini" in status
    print("ok probe", status["grok"]["available"], status["gemini"]["available"])


if __name__ == "__main__":
    test_extract_json_from_fence_and_wrapper()
    test_merge_dedup_by_url_and_title()
    test_event_agent_reads_open_source()
    test_event_agent_without_open_source()
    test_probe_does_not_crash()
    print("all cli collector tests passed")
