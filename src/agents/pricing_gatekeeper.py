# -*- coding: utf-8 -*-
from typing import Dict, Any, List

class PricingGatekeeperAgent:
    def __init__(self):
        self.is_active = True

    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Pricing Gatekeeper Agent 已關閉。")

        price_data = ingested_data.get("price_action") or {}
        fundamentals = ingested_data.get("fundamentals") or {}

        close = price_data.get("close")
        ma20 = price_data.get("ma20")
        ma60 = price_data.get("ma60")
        pe_ratio = fundamentals.get("pe_ratio")
        pe_ratio_5y_avg = fundamentals.get("pe_ratio_5y_avg")

        price_reasonableness_signal = "價位合理"
        objective_findings = []

        if close is not None:
            objective_findings.append(f"當前市價: {close:,.2f} 元。")
            if ma20 is not None:
                objective_findings.append(f"20日均線 (20MA): {ma20:,.2f} 元。")
            if ma60 is not None:
                objective_findings.append(f"60日均線 (60MA): {ma60:,.2f} 元。")
            if pe_ratio is not None:
                objective_findings.append(f"目前本益比 (PE): {pe_ratio:.2f} 倍。")
            if pe_ratio_5y_avg is not None:
                objective_findings.append(f"5年平均本益比 (5Y Avg PE): {pe_ratio_5y_avg:.2f} 倍。")

            # 價位合理性判斷邏輯
            if ma20 is not None and pe_ratio is not None and pe_ratio_5y_avg is not None and pe_ratio_5y_avg > 0:
                # 價位偏高：價格顯著高於 20MA (高於 5%) 且本益比高於 5年均值 20% 以上
                if close > 1.05 * ma20 and pe_ratio > 1.20 * pe_ratio_5y_avg:
                    price_reasonableness_signal = "價位偏高, 追高風險"
                # 價位偏低：價格低於 20MA 且本益比較 5年均值低 (低於 1.5 倍平均，即 pe_percentile 具吸引力)，
                # 若價格跌破 60MA 達 10% 以上，可能面臨未反映利空
                elif close < ma20 and pe_ratio < 1.0 * pe_ratio_5y_avg:
                    if ma60 is not None and close < 0.90 * ma60:
                        price_reasonableness_signal = "價位偏低, 可能存在利空未反映"
                    else:
                        price_reasonableness_signal = "價位合理"
                else:
                    price_reasonableness_signal = "價位合理"

        objective_findings.append(f"定價合理性評估結論: {price_reasonableness_signal}。")

        report = {
            "agent_name": "Pricing Gatekeeper Agent",
            "price_reasonableness_signal": price_reasonableness_signal,
            "objective_findings": objective_findings,
            "summary": f"個股定價合理性把關完成（評估結果: {price_reasonableness_signal}）。本分析僅作風險防範，不提供任何具體目標價或交易進出場建議。"
        }
        return report

    def close(self):
        self.is_active = False
