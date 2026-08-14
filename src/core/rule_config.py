# -*- coding: utf-8 -*-
"""集中載入 config/rules.yaml，供所有 Agent 讀取判斷門檻。"""
from pathlib import Path
from typing import Any, Dict

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "rules.yaml"
_cache: Dict[str, Any] = {}


def load_rules(force_reload: bool = False) -> Dict[str, Any]:
    global _cache
    if _cache and not force_reload:
        return _cache
    if not _CONFIG_PATH.is_file():
        raise FileNotFoundError(f"找不到規則設定檔：{_CONFIG_PATH}")
    with open(_CONFIG_PATH, "r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"規則設定檔格式無效（應為對應表）：{_CONFIG_PATH}")
    _cache = loaded
    return _cache


def get_agent_rules(agent_key: str) -> Dict[str, Any]:
    rules = load_rules()
    if agent_key not in rules:
        raise KeyError(f"規則設定檔缺少 {agent_key} 區塊，請檢查 config/rules.yaml")
    block = rules[agent_key]
    if not isinstance(block, dict):
        raise ValueError(f"規則設定檔 {agent_key} 區塊格式無效，請檢查 config/rules.yaml")
    return block


def get_rules_version() -> str:
    return str(load_rules().get("version", "unknown"))


def get_rules_updated_at() -> str:
    return str(load_rules().get("updated_at", ""))


def get_rules_path() -> Path:
    return _CONFIG_PATH
