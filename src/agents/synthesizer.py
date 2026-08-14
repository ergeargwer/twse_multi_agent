import os
import json
import requests
from typing import Dict, Any
from src.core import risk
from src.core.prompt_config import build_system_prompt, get_persona_version
from src.core.rule_config import get_agent_rules, get_rules_version

class DecisionSynthesizerAgent:
    def __init__(self):
        self.is_active = True
        
    def synthesize(self, context_store: Dict[str, Any], collector=None, cooldown_tracker=None, symbol: str = "未知標的", expected_gain_pct: float = 30.0, max_loss_pct: float = 10.0) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Decision Synthesizer Agent 已關閉，無法執行彙整。")
            
        fund_report = context_store.get("fundamental_report") or {}
        tech_report = context_store.get("technical_report") or {}
        flow_report = context_store.get("institutional_flow_report") or {}
        event_report = context_store.get("event_calendar_report") or {}
        asset_allocation_report = context_store.get("asset_allocation_report") or {}
        pricing_gatekeeper_report = context_store.get("pricing_gatekeeper_report") or {}
        veto_report = context_store.get("risk_veto_report") or {}
        discipline_report = context_store.get("discipline_report") or {}
        behavior_risk_report = context_store.get("behavior_risk_report") or {}
        
        # 1. 計算風暴比
        risk_profile = risk.calculate_risk_reward(expected_gain_pct, max_loss_pct)
        pos_step = risk.suggest_position_step(0.0)
        
        # 2. 檢查交易冷卻期
        cooldown_passed = True
        cooldown_warning = ""
        if cooldown_tracker:
            cooldown_passed = cooldown_tracker.is_cooldown_passed(symbol)
            if not cooldown_passed:
                cooldown_warning = "距離您上次對此標的產生交易衝動尚未滿一天，建議先離線散步 10 分鐘"
            # 記錄本次交易意圖
            cooldown_tracker.request_trade_intent(symbol)
            
        # 3. 檢查風控煞車 veto 狀態
        veto_active = veto_report.get("veto", False)
        veto_reason = veto_report.get("veto_reason", "")
        
        system_prompt = build_system_prompt(veto_active, veto_reason)
        
        user_prompt = json.dumps({
            "fundamental": fund_report,
            "technical": tech_report,
            "institutional": flow_report,
            "event": event_report,
            "asset_allocation": asset_allocation_report,
            "pricing_gatekeeper": pricing_gatekeeper_report,
            "risk_veto": veto_report,
            "discipline": discipline_report,
            "behavior_risk": behavior_risk_report,
        }, ensure_ascii=False, indent=2)
        
        llm_result = self._complete_with_fallback(system_prompt, user_prompt)
        scenario_conclusion = llm_result["content"]
        used_model = llm_result["model"]
        used_provider = llm_result["provider"]
            
        # 程式化置頂風控煞車段落 (硬性規則以防 LLM 遺漏)
        if veto_active and veto_reason:
            veto_prefix = f"【風控煞車警訊】系統已啟動風控攔截，原因如下：{veto_reason}。本次分析對象不符合安全交易標準，強烈建議暫停交易意圖，退場觀望。\n\n"
            if not scenario_conclusion.strip().startswith("【風控煞車警訊】"):
                scenario_conclusion = veto_prefix + scenario_conclusion
                
        # 結尾加註提醒
        min_ratio = get_agent_rules("risk_veto_agent")["min_risk_reward_ratio"]
        risk_reminder_text = (
            f"\n\n【導師的風險與資金管理提醒】\n"
            f"- 當前預估風暴比為 {risk_profile.ratio:.2f}:1 (預估漲幅: {risk_profile.expected_gain_pct}%, 可容忍停損: {risk_profile.max_loss_pct}%)。\n"
            f"- 符合 {min_ratio:.2f}:1 風暴比門檻: {'是' if risk_profile.is_qualified else '否'}。\n"
            f"- 建議單次調節幅度: {pos_step * 100:.0f}% (每次分批 10% 或 20% 操作原則，保留資金彈性，切勿滿倉或使用槓桿)。"
        )
        scenario_conclusion += risk_reminder_text
        
        if not cooldown_passed and cooldown_warning:
            scenario_conclusion += f"\n- 冷卻警訊：{cooldown_warning}"
            
        # 從各報告匯總客觀數據點
        all_findings = []
        for rpt in [
            fund_report,
            tech_report,
            flow_report,
            event_report,
            asset_allocation_report,
            pricing_gatekeeper_report,
            veto_report,
            discipline_report,
            behavior_risk_report,
        ]:
            all_findings.extend(rpt.get("objective_findings", []))
 
        report = {
            "agent_name": "Decision Synthesizer Agent",
            "process": "conflict_resolution_and_alignment",
            "inputs_parsed": [
                "fundamental",
                "technical",
                "institutional",
                "event",
                "asset_allocation",
                "pricing_gatekeeper",
                "risk_veto",
                "discipline",
                "behavior_risk",
            ],
            "aligned_evidence": all_findings,
            "conflicting_evidence": [],
            "scenario_synthesis": scenario_conclusion,
            "strict_disclaimer": "【系統警告】本綜合推演報告僅基於客觀數據聚集，不得作為交易投資建議、股價點位判斷或實盤操作依據。",
            "risk_profile": risk_profile.to_dict(),
            "cooldown_passed": cooldown_passed,
            "cooldown_warning": cooldown_warning,
            "rule_config_version": get_rules_version(),
            "prompt_persona_version": get_persona_version(),
        }
        
        if collector:
            collector.record_llm_trace(
                model=used_model,
                provider=used_provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_output=scenario_conclusion,
                final_report=report
            )
            
        return report

    def _complete_with_fallback(self, system_prompt: str, user_prompt: str) -> Dict[str, str]:
        """依可用金鑰依序嘗試 SpaceXAI / OpenRouter / Gemini。"""
        errors = []
        last_model = os.environ.get("LLM_MODEL", "google/gemma-4-31b-it")
        last_provider = "none"

        for attempt in self._llm_attempts():
            last_model = attempt["model"]
            last_provider = attempt["provider"]
            try:
                response = self._dispatch_llm(attempt, system_prompt, user_prompt)
                if response.status_code == 200:
                    content = self._extract_content(attempt["kind"], response)
                    if content:
                        return {
                            "content": content,
                            "model": attempt["model"],
                            "provider": attempt["provider"],
                        }
                    errors.append(f"{attempt['provider']} 回傳空白內容")
                else:
                    errors.append(
                        f"{attempt['provider']} HTTP {response.status_code}: {self._extract_error(response)}"
                    )
            except Exception as exc:
                errors.append(f"{attempt['provider']} 例外: {exc}")

        if not errors:
            detail = "未設定 XAI_API_KEY / OPENROUTER_API_KEY / GEMINI_API_KEY"
        else:
            detail = "；".join(errors)

        return {
            "content": f"LLM API 請求失敗。{detail}",
            "model": last_model,
            "provider": last_provider,
        }

    def _llm_attempts(self) -> list:
        preferred = os.environ.get("LLM_PROVIDER", "").strip().lower()
        xai_key = os.environ.get("XAI_API_KEY", "").strip()
        or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        gemini_key = (
            os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        )

        candidates = []
        if xai_key:
            candidates.append({
                "kind": "openai",
                "provider": "SpaceXAI",
                "model": os.environ.get("XAI_MODEL", "grok-4.5"),
                "url": "https://api.x.ai/v1/chat/completions",
                "api_key": xai_key,
            })
        if or_key:
            candidates.append({
                "kind": "openai",
                "provider": "OpenRouter",
                "model": os.environ.get("OPENROUTER_MODEL") or os.environ.get("LLM_MODEL") or "google/gemma-4-31b-it",
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "api_key": or_key,
            })
        if gemini_key:
            candidates.append({
                "kind": "gemini",
                "provider": "Gemini",
                "model": os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash",
                "url": "",
                "api_key": gemini_key,
            })

        if preferred:
            preferred_map = {"xai": "SpaceXAI", "spacexai": "SpaceXAI", "openrouter": "OpenRouter", "gemini": "Gemini"}
            target = preferred_map.get(preferred, preferred)
            candidates.sort(key=lambda item: 0 if item["provider"].lower() == target.lower() else 1)
        return candidates

    def _dispatch_llm(self, attempt: Dict[str, str], system_prompt: str, user_prompt: str):
        if attempt["kind"] == "gemini":
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{attempt['model']}:generateContent?key={attempt['api_key']}"
            )
            payload = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.4},
            }
            return requests.post(url, json=payload, timeout=60)

        headers = {
            "Authorization": f"Bearer {attempt['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": attempt["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        return requests.post(attempt["url"], headers=headers, json=payload, timeout=60)

    def _extract_content(self, kind: str, response) -> str:
        data = response.json()
        if kind == "gemini":
            parts = (
                data.get("candidates") or [{}]
            )[0].get("content", {}).get("parts") or []
            return "".join(part.get("text", "") for part in parts).strip()
        choices = data.get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message") or {}).get("content", "").strip()

    def _extract_error(self, response) -> str:
        try:
            data = response.json()
        except Exception:
            return (response.text or "")[:300]
        err = data.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err)[:300]
        if err:
            return str(err)[:300]
        return (response.text or "")[:300]

    def close(self):
        self.is_active = False
