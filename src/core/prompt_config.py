# -*- coding: utf-8 -*-
"""載入 Synthesizer persona prompt 模板。"""
from pathlib import Path
from typing import Any, Dict

import yaml

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "prompts"
    / "synthesizer_persona_v1.yaml"
)
_cache: Dict[str, Any] = {}


def load_persona(force_reload: bool = False) -> Dict[str, Any]:
    global _cache
    if _cache and not force_reload:
        return _cache
    if not _PROMPT_PATH.is_file():
        raise FileNotFoundError(f"找不到 Prompt 人設檔：{_PROMPT_PATH}")
    with open(_PROMPT_PATH, "r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"Prompt 人設檔格式無效：{_PROMPT_PATH}")
    for required in ("persona_intro", "output_constraints", "veto_instruction_template"):
        if required not in loaded:
            raise KeyError(f"Prompt 人設檔缺少 {required}，請檢查 {_PROMPT_PATH}")
    _cache = loaded
    return _cache


def build_system_prompt(veto_active: bool, veto_reason: str = "") -> str:
    persona = load_persona()
    veto_block = ""
    if veto_active and veto_reason:
        veto_block = persona["veto_instruction_template"].format(veto_reason=veto_reason)
        if not veto_block.endswith("\n"):
            veto_block += "\n"
        veto_block += "\n"
    constraints_text = "\n".join(
        f"{index + 1}. {item}" for index, item in enumerate(persona["output_constraints"])
    )
    intro = str(persona["persona_intro"]).rstrip()
    return (
        f"{intro}\n\n"
        f"{veto_block}"
        f"輸出限制（非常重要）：\n{constraints_text}\n\n"
        f"請基於以下傳入的各分析 Agent JSON 報告進行客觀之情境推演與彙總。"
    )


def get_persona_version() -> str:
    return str(load_persona().get("version", "unknown"))


def get_persona_path() -> Path:
    return _PROMPT_PATH
