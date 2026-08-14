# -*- coding: utf-8 -*-
"""用 Grok Build CLI 與 Gemini CLI 平行蒐集未驗證的開放來源事件。

僅允許搜尋／抓頁，禁止寫檔與 shell。任一邊失敗就跳過，不擋 FinMind／Shioaji。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

KIND_VALUES = ("news", "announcement", "etf", "buyback", "dividend", "rumor", "other")

GROK_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "date": {"type": "string"},
                    "summary": {"type": "string"},
                    "kind": {"type": "string", "enum": list(KIND_VALUES)},
                },
                "required": ["title", "summary"],
            },
        }
    },
    "required": ["items"],
}

_DEFAULT_NODE22 = Path.home() / ".nvm/versions/node/v22.22.0/bin/node"
_DEFAULT_GEMINI_JS = (
    Path.home() / ".nvm/versions/node/v22.22.0/lib/node_modules/@google/gemini-cli/bundle/gemini.js"
)
_DEFAULT_GROK = Path.home() / ".local/bin/grok"


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def is_collect_enabled() -> bool:
    return _env_flag("CLI_COLLECT_ENABLED", True)


def collect_timeout_sec() -> int:
    return max(30, _env_int("CLI_COLLECT_TIMEOUT", 180))


def collect_max_turns() -> int:
    return max(2, _env_int("CLI_COLLECT_MAX_TURNS", 8))


def resolve_grok_cmd() -> Optional[List[str]]:
    override = os.environ.get("GROK_CLI_BIN", "").strip()
    if override:
        return [override]
    found = shutil.which("grok")
    if found:
        return [found]
    if _DEFAULT_GROK.is_file():
        return [str(_DEFAULT_GROK)]
    return None


def resolve_gemini_cmd() -> Optional[List[str]]:
    override = os.environ.get("GEMINI_CLI_BIN", "").strip()
    if override:
        return [override]
    node_override = os.environ.get("GEMINI_CLI_NODE", "").strip()
    node = Path(node_override) if node_override else _DEFAULT_NODE22
    js = _DEFAULT_GEMINI_JS
    if node.is_file() and js.is_file():
        return [str(node), str(js)]
    found = shutil.which("gemini")
    if found:
        # 系統 PATH 的 node 若 < 20，gemini 會直接 SyntaxError
        if node.is_file():
            return [str(node), found]
        return [found]
    return None


def probe_collectors() -> Dict[str, Any]:
    grok = resolve_grok_cmd()
    gemini = resolve_gemini_cmd()
    return {
        "enabled": is_collect_enabled(),
        "grok": {"available": bool(grok), "cmd": grok},
        "gemini": {"available": bool(gemini), "cmd": gemini},
        "timeout_sec": collect_timeout_sec(),
        "max_turns": collect_max_turns(),
    }


def extract_json_value(text: Any) -> Any:
    if text is None:
        return None
    if isinstance(text, (dict, list)):
        return text
    blob = str(text).strip()
    if not blob:
        return None
    candidates = [blob]
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", blob)
    if fence:
        candidates.insert(0, fence.group(1).strip())
    for opener in ("{", "["):
        idx = blob.find(opener)
        if idx >= 0:
            candidates.append(blob[idx:])
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    return None


def items_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    structured = payload.get("structuredOutput")
    if isinstance(structured, (dict, list)):
        return items_from_payload(structured)
    for key in ("items", "events", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    for key in ("text", "response", "output", "result", "message"):
        if key not in payload:
            continue
        inner = payload[key]
        if isinstance(inner, str):
            inner = extract_json_value(inner)
        found = items_from_payload(inner)
        if found:
            return found
    return []


def canonicalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    path = parsed.path.rstrip("/")
    return urlunparse((
        (parsed.scheme or "https").lower(),
        parsed.netloc.lower(),
        path,
        "",
        urlencode(query),
        "",
    ))


def canonicalize_title(title: str) -> str:
    folded = re.sub(r"\s+", "", (title or "").lower())
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", folded, flags=re.UNICODE)


def normalize_item(raw: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    kind = str(raw.get("kind") or "other").strip().lower()
    if kind not in KIND_VALUES:
        kind = "other"
    return {
        "title": title[:220],
        "url": str(raw.get("url") or "").strip()[:500],
        "date": str(raw.get("date") or "").strip()[:32],
        "summary": str(raw.get("summary") or "").strip()[:400],
        "kind": kind,
        "sources": [source],
        "agreement": source,
        "quality": "unverified",
    }


def merge_items(side_items: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    by_url: Dict[str, int] = {}
    by_title: Dict[str, int] = {}

    for source, rows in side_items.items():
        for raw in rows:
            item = normalize_item(raw, source)
            if not item:
                continue
            url_key = canonicalize_url(item["url"])
            title_key = canonicalize_title(item["title"])
            hit = None
            if url_key and url_key in by_url:
                hit = by_url[url_key]
            elif title_key and title_key in by_title:
                hit = by_title[title_key]
            if hit is None:
                idx = len(merged)
                merged.append(item)
                if url_key:
                    by_url[url_key] = idx
                if title_key:
                    by_title[title_key] = idx
                continue
            existing = merged[hit]
            if source not in existing["sources"]:
                existing["sources"].append(source)
            if item["url"] and not existing["url"]:
                existing["url"] = item["url"]
            if item["date"] and not existing["date"]:
                existing["date"] = item["date"]
            if item["summary"] and len(item["summary"]) > len(existing["summary"]):
                existing["summary"] = item["summary"]
            if existing["kind"] == "other" and item["kind"] != "other":
                existing["kind"] = item["kind"]

    for item in merged:
        sources = item["sources"]
        item["agreement"] = "both" if len(sources) > 1 else sources[0]
    return merged


def _build_prompt(symbol: str) -> str:
    code = symbol.split(".")[0]
    start = (date.today() - timedelta(days=14)).isoformat()
    end = date.today().isoformat()
    return (
        f"你是台股開放來源蒐集器，不是分析師。\n"
        f"目標標的：{symbol}（代號 {code}）。\n"
        f"請用搜尋與網頁抓取，整理 {start} 至 {end} 期間與此標的相關的新聞、公司公告、"
        f"除權息、庫藏股、ETF 成分異動或制度事件。\n"
        "規則：\n"
        "1. 只蒐集，不要預測漲跌，不要給買賣建議。\n"
        "2. 每筆盡量附可核對的 URL 與日期（YYYY-MM-DD）。\n"
        "3. 不確定就 kind=rumor 或 other，不要捏造來源。\n"
        "4. 最多 12 筆，摘要各一句繁體中文。\n"
        "5. 只輸出 JSON，格式："
        '{"items":[{"title":"","url":"","date":"","summary":"","kind":"news|announcement|etf|buyback|dividend|rumor|other"}]}'
    )


def _scrub_env() -> Dict[str, str]:
    env = os.environ.copy()
    for key in (
        "GROK_AGENT",
        "GROK_SESSION_ID",
        "GROK_LEADER_SOCKET",
        "TERM_PROGRAM",
    ):
        env.pop(key, None)
    env["TERM"] = "dumb"
    env["NO_COLOR"] = "1"
    node_dir = _DEFAULT_NODE22.parent
    if node_dir.is_dir():
        env["PATH"] = f"{node_dir}{os.pathsep}{env.get('PATH', '')}"
    return env


def _run_cli(cmd: List[str], cwd: str, timeout: int) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=_scrub_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            text=True,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return 124, out, (err + "\n[timeout]").strip()
    except Exception as exc:
        return 1, "", str(exc)


def _side_result(name: str, status: str, items: List[Dict[str, Any]], error: str = "") -> Dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "item_count": len(items),
        "items": items,
        "error": error[:500],
    }


def run_grok_collector(symbol: str, timeout: int, max_turns: int) -> Dict[str, Any]:
    cmd_prefix = resolve_grok_cmd()
    if not cmd_prefix:
        return _side_result("grok", "unavailable", [], "找不到 grok CLI")

    prompt = _build_prompt(symbol)
    with tempfile.TemporaryDirectory(prefix="twse-grok-collect-") as cwd:
        cmd = cmd_prefix + [
            "-p", prompt,
            "--cwd", cwd,
            "--output-format", "json",
            "--json-schema", json.dumps(GROK_JSON_SCHEMA, ensure_ascii=False),
            "--tools", "web_search,web_fetch",
            "--disallowed-tools", "run_terminal_cmd,search_replace,write,Agent",
            "--no-subagents",
            "--max-turns", str(max_turns),
            "--permission-mode", "bypassPermissions",
            "--verbatim",
        ]
        code, stdout, stderr = _run_cli(cmd, cwd, timeout)
    payload = extract_json_value(stdout)
    items = items_from_payload(payload)
    if code != 0 and not items:
        detail = stderr.strip() or stdout.strip() or f"exit {code}"
        return _side_result("grok", "failed", [], detail)
    if not items:
        return _side_result("grok", "empty", [], stderr.strip())
    return _side_result("grok", "ok", items)


def run_gemini_collector(symbol: str, timeout: int, max_turns: int) -> Dict[str, Any]:
    cmd_prefix = resolve_gemini_cmd()
    if not cmd_prefix:
        return _side_result("gemini", "unavailable", [], "找不到 Gemini CLI 或 Node 22")

    prompt = _build_prompt(symbol)
    # max_turns 保留介面對稱；Gemini CLI 無對應旗標，深度靠 prompt。
    del max_turns
    with tempfile.TemporaryDirectory(prefix="twse-gemini-collect-") as cwd:
        cmd = cmd_prefix + [
            "-p", prompt,
            "-o", "json",
            "--approval-mode", "plan",
            "--skip-trust",
        ]
        code, stdout, stderr = _run_cli(cmd, cwd, timeout)
    payload = extract_json_value(stdout)
    items = items_from_payload(payload)
    if code != 0 and not items:
        detail = stderr.strip() or stdout.strip() or f"exit {code}"
        return _side_result("gemini", "failed", [], detail)
    if not items:
        return _side_result("gemini", "empty", [], stderr.strip())
    return _side_result("gemini", "ok", items)


def collect_open_source_events(symbol: str) -> Dict[str, Any]:
    """平行跑 Grok + Gemini，合併去重後回傳固定 schema。"""
    if not is_collect_enabled():
        return {
            "status": "disabled",
            "symbol": symbol,
            "items": [],
            "sides": {},
            "both_count": 0,
            "quality": "unverified",
        }

    timeout = collect_timeout_sec()
    max_turns = collect_max_turns()
    runners = {
        "grok": run_grok_collector,
        "gemini": run_gemini_collector,
    }
    sides: Dict[str, Dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(fn, symbol, timeout, max_turns): name
            for name, fn in runners.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                sides[name] = future.result()
            except Exception as exc:
                sides[name] = _side_result(name, "failed", [], str(exc))

    items = merge_items({
        name: (side.get("items") or [])
        for name, side in sides.items()
    })
    both_count = sum(1 for item in items if item.get("agreement") == "both")
    ok_sides = [name for name, side in sides.items() if side.get("status") == "ok"]
    if not items:
        if all(side.get("status") == "unavailable" for side in sides.values()):
            status = "unavailable"
        elif any(side.get("status") == "failed" for side in sides.values()):
            status = "failed"
        else:
            status = "empty"
    elif len(ok_sides) == 2 or both_count > 0:
        status = "ok"
    else:
        status = "partial"

    compact_sides = {
        name: {
            "status": side.get("status"),
            "item_count": side.get("item_count", 0),
            "error": side.get("error", ""),
        }
        for name, side in sides.items()
    }
    return {
        "status": status,
        "symbol": symbol,
        "items": items[:16],
        "sides": compact_sides,
        "both_count": both_count,
        "quality": "unverified",
    }


def collect_open_source_events_async(symbol: str):
    """在背景執行緒啟動蒐集，回傳可 .result() 的 Future。"""
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cli-collect")
    future = pool.submit(collect_open_source_events, symbol)

    def _shutdown(done_future):
        pool.shutdown(wait=False)

    future.add_done_callback(_shutdown)
    return future
