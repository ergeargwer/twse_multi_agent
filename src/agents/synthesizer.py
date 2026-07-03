import os
import json
import requests
from typing import Dict, Any
from src.core import risk

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
        
        # 1. 計算風暴比
        risk_profile = risk.calculate_risk_reward(expected_gain_pct, max_loss_pct)
        pos_step = risk.suggest_position_step(0.0)
        
        # 2. 檢查交易冷卻期
        cooldown_passed = True
        cooldown_warning = ""
        if cooldown_tracker:
            cooldown_passed = cooldown_tracker.is_cooldown_passed(symbol)
            if not cooldown_passed:
                cooldown_warning = "距離您上次對此標的產生交易衝動尚未滿一天，建議先散步或離開螢幕 5-10 分鐘"
            # 記錄本次交易意圖
            cooldown_tracker.request_trade_intent(symbol)
            
        # 3. 檢查風控煞車 veto 狀態
        veto_active = veto_report.get("veto", False)
        veto_reason = veto_report.get("veto_reason", "")
        
        veto_system_instruction = ""
        if veto_active and veto_reason:
            veto_system_instruction = (
                f"【特別指令】\n"
                f"風控煞車機制已被觸發 (veto 為 True)！原因為：{veto_reason}。\n"
                f"你必須在報告最前面的第一個段落「逐字保留」以下風控警告，絕對不可做任何簡化、修飾或用溫和語氣淡化：\n"
                f"「【風控煞車警訊】系統已啟動風控攔截，原因如下：{veto_reason}。本次分析對象不符合安全交易標準，強烈建議暫停交易意圖，退場觀望。」\n\n"
            )
            
        system_prompt = (
            "你是一位溫暖的理性隱者，人稱「樹之修行者」的投資導師。\n"
            "你的核心人格：溫暖的理性隱者，相信利潤來自耐心而非操作技術，重視「扎根大於開花」，視獨立思考為修煉，不隨群眾情緒起舞。\n"
            "你的思維模組：應變重於預判。不對未來做單一預測，而是針對上漲、下跌、盤整分別擬定對策；主張減法與留白，反對過度分析與過度交易。\n"
            "你的行動原則：保留資金彈性，絕不建議滿倉或槓桿；不為證明自己而交易，認同「成功的停損」也是完美交易。\n"
            "你的語氣：溫柔堅定、像歷經市場風浪的學長，避免冰冷的機率式斷言。請一律使用繁體中文，且絕對禁止使用任何 emoji。\n\n"
            
            f"{veto_system_instruction}"
            
            "輸出限制（非常重要）：\n"
            "1. 嚴禁給出任何具體買賣點位或「應該買/應該賣」的直接建議。最終決策權必須交還給使用者。\n"
            "2. 先列出多空雙方的訊號與矛盾點（呼應「多空矛盾比對」邏輯）。\n"
            "3. 用「情境推演」語言取代「預測」語言（例如避免使用「將會上漲」，改用「若技術面訊號延續，可能面臨的情境是...」）。\n"
            "4. 結尾必須附上風暴比與分批操作的提醒，而非明確目標價。\n\n"
            "請基於以下傳入的各分析 Agent JSON 報告進行客觀之情境推演與彙總。"
        )
        
        user_prompt = json.dumps({
            "fundamental": fund_report,
            "technical": tech_report,
            "institutional": flow_report,
            "event": event_report,
            "asset_allocation": asset_allocation_report,
            "pricing_gatekeeper": pricing_gatekeeper_report,
            "risk_veto": veto_report,
            "discipline": discipline_report
        }, ensure_ascii=False, indent=2)
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "google/gemma-4-31b-it",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        
        scenario_conclusion = ""
        
        try:
            r = requests.post(url, headers=headers, json=data, timeout=30)
            if r.status_code == 200:
                resp_json = r.json()
                scenario_conclusion = resp_json["choices"][0]["message"]["content"]
            else:
                scenario_conclusion = f"LLM API 請求失敗 (HTTP {r.status_code})。可能為缺少金鑰或模型不支援。"
        except Exception as e:
            scenario_conclusion = f"LLM API 請求發生例外錯誤: {str(e)}"
            
        # 程式化置頂風控煞車段落 (硬性規則以防 LLM 遺漏)
        if veto_active and veto_reason:
            veto_prefix = f"【風控煞車警訊】系統已啟動風控攔截，原因如下：{veto_reason}。本次分析對象不符合安全交易標準，強烈建議暫停交易意圖，退場觀望。\n\n"
            if not scenario_conclusion.strip().startswith("【風控煞車警訊】"):
                scenario_conclusion = veto_prefix + scenario_conclusion
                
        # 結尾加註提醒
        risk_reminder_text = (
            f"\n\n【導師的風險與資金管理提醒】\n"
            f"- 當前預估風暴比為 {risk_profile.ratio:.2f}:1 (預估漲幅: {risk_profile.expected_gain_pct}%, 可容忍停損: {risk_profile.max_loss_pct}%)。\n"
            f"- 符合 3:1 風暴比門檻: {'是' if risk_profile.is_qualified else '否'}。\n"
            f"- 建議單次調節幅度: {pos_step * 100:.0f}% (每次分批 10% 或 20% 操作原則，保留資金彈性，切勿滿倉或使用槓桿)。"
        )
        scenario_conclusion += risk_reminder_text
        
        if not cooldown_passed and cooldown_warning:
            scenario_conclusion += f"\n- 冷卻警訊：{cooldown_warning}"
            
        # 從各報告匯總客觀數據點
        all_findings = []
        for rpt in [fund_report, tech_report, flow_report, event_report, asset_allocation_report, pricing_gatekeeper_report, veto_report, discipline_report]:
            all_findings.extend(rpt.get("objective_findings", []))
 
        report = {
            "agent_name": "Decision Synthesizer Agent",
            "process": "conflict_resolution_and_alignment",
            "inputs_parsed": ["fundamental", "technical", "institutional", "event", "asset_allocation", "pricing_gatekeeper", "risk_veto", "discipline"],
            "aligned_evidence": all_findings,
            "conflicting_evidence": [],
            "scenario_synthesis": scenario_conclusion,
            "strict_disclaimer": "【系統警告】本綜合推演報告僅基於客觀數據聚集，不得作為交易投資建議、股價點位判斷或實盤操作依據。",
            "risk_profile": risk_profile.to_dict(),
            "cooldown_passed": cooldown_passed,
            "cooldown_warning": cooldown_warning
        }
        
        if collector:
            collector.record_llm_trace(
                model="google/gemma-4-31b-it",
                provider="OpenRouter",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_output=scenario_conclusion,
                final_report=report
            )
            
        return report
 
    def close(self):
        self.is_active = False
