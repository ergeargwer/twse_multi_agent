from typing import Any, Dict, List

from src.core.rule_config import get_agent_rules


class EventCalendarAgent:
    def __init__(self):
        self.is_active = True
        self.rules = get_agent_rules("event_agent")
        
    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("ETF & Event Agent 已關閉，無法執行分析。")
            
        events_data = ingested_data.get("calendar_events", {})
        open_source = ingested_data.get("open_source_events") or {}
        days_to_ex_div = events_data.get("days_to_ex_dividend") or -1
        days_to_recall = events_data.get("days_to_margin_recall") or -1
        etf_rebalance = events_data.get("in_etf_rebalance_watchlist") or False
        
        margin_maintenance_ratio = events_data.get("margin_maintenance_ratio")
        has_large_buyback = events_data.get("has_large_buyback")
        
        call_pct = self.rules["margin_call_warning_pct"]
        bottom_pct = self.rules["margin_ratio_bottom_signal_pct"]
        band_pct = self.rules["margin_ratio_bottom_signal_band_pct"]
        recall_days = self.rules["days_to_recall_alert"]
        ex_div_days = self.rules["days_to_ex_div_alert"]
        margin_ratio_signal = "無明顯訊號"
        if margin_maintenance_ratio is not None:
            if margin_maintenance_ratio <= call_pct:
                margin_ratio_signal = "追繳警戒"
            elif abs(margin_maintenance_ratio - bottom_pct) <= band_pct:
                margin_ratio_signal = "恐慌指標鈍化"
        else:
            margin_ratio_signal = "資料源待補"

        usd_index_signal = "無明顯訊號"
        if ingested_data.get("usd_index_20d_high") is True:
            usd_index_signal = "外資撤離資金抽離警訊"
        elif ingested_data.get("usd_index_20d_high") is None and ingested_data.get("usd_index_error"):
            usd_index_signal = "資料源待補"
            
        buyback_signal = "無明顯訊號"
        if has_large_buyback is not None:
            if has_large_buyback:
                buyback_signal = "信心指標浮現"
        else:
            buyback_signal = "資料源待補"

        objective_findings = []
        if days_to_recall > 0 and days_to_recall <= recall_days:
            objective_findings.append(f"距離融券最後強制回補日僅剩 {days_to_recall} 日，需留意空單強迫買進之制度性軋空/買盤現象。")
        
        if days_to_ex_div > 0 and days_to_ex_div <= ex_div_days:
            objective_findings.append(f"距離除權息交易日約 {days_to_ex_div} 日，可能面臨高殖利率參與買盤或持股避稅棄息賣壓之換手。")
            
        if etf_rebalance:
            objective_findings.append("該標的目前名列「巨型高股息 ETF」之潛在成分股增刪觀察名單中，極易受到與基本面無關之被動式資金拋售或灌入干擾。")
        else:
            objective_findings.append("短期內未見重大 ETF 季配/半年配換股審核重疊風險。")
            
        if margin_ratio_signal == "追繳警戒":
            objective_findings.append(
                f"融資維持率跌破{call_pct:.0f}%追繳線，需留意斷頭賣壓。"
            )
        elif margin_ratio_signal == "恐慌指標鈍化":
            objective_findings.append(
                f"融資維持率落於{bottom_pct:.0f}%附近止穩，市場多殺多踐踏可能已近尾聲。"
            )
        if usd_index_signal == "外資撤離資金抽離警訊":
            source = ingested_data.get("usd_index_data_source") or "美元指數"
            latest = ingested_data.get("usd_index_latest")
            extra = f"（最新 {latest:.2f}，來源 {source}）" if latest is not None else f"（來源 {source}）"
            objective_findings.append(f"美元指數創20日新高{extra}，需留意外資資金撤離風險。")
        elif usd_index_signal == "資料源待補":
            objective_findings.append(
                f"美元指數未能取得（{ingested_data.get('usd_index_error')}），不使用替代匯率冒充。"
            )
        if buyback_signal == "信心指標浮現":
            objective_findings.append("大型公司宣布庫藏股，信心指標浮現。")

        open_items: List[Dict[str, Any]] = open_source.get("items") or []
        both_count = int(open_source.get("both_count") or 0)
        cli_status = open_source.get("status") or "missing"
        open_source_signal = "無明顯訊號"
        if both_count > 0:
            open_source_signal = "雙源交叉印證"
        elif open_items:
            open_source_signal = "單源待查"
        elif cli_status in ("failed", "unavailable"):
            open_source_signal = "開放來源未產出"

        if open_items:
            objective_findings.append(
                f"開放來源（Grok CLI + Gemini CLI）整理 {len(open_items)} 筆未驗證事件，"
                f"其中雙源交叉 {both_count} 筆；僅供對照，不得視為既定事實。"
            )
            notable = [item for item in open_items if item.get("kind") in {"buyback", "etf", "dividend", "announcement"}]
            for item in (notable or open_items)[:5]:
                sources = "/".join(item.get("sources") or [])
                mark = "雙源" if item.get("agreement") == "both" else "單源"
                objective_findings.append(
                    f"[{mark}/{item.get('kind')}/{sources}] {item.get('date') or '日期不明'} "
                    f"{item.get('title')} — {item.get('summary')}"
                )
        elif cli_status == "disabled":
            objective_findings.append("開放來源 CLI 蒐集已關閉（CLI_COLLECT_ENABLED=0）。")
        elif cli_status in ("failed", "unavailable", "empty"):
            objective_findings.append("開放來源 CLI 本次未取得可用新聞／公告，制度判斷仍以行事曆欄位為準。")
            
        report = {
            "agent_name": "ETF & Event Agent",
            "metrics_extracted": [
                "days_to_margin_recall",
                "days_to_ex_dividend",
                "in_etf_rebalance_watchlist",
                "open_source_events",
                "usd_index_20d_high",
            ],
            "objective_findings": objective_findings,
            "summary": (
                "特有行事曆與事件風險梳理完畢。"
                "開放來源條目為網路搜尋彙整、品質標為未驗證，"
                "本報告僅指出『潛在被動資金或制度性行為發生之可能性』，"
                "嚴格禁止對事件發生後之價格方向、漲跌幅度做任何推測。"
            ),
            "margin_ratio_signal": margin_ratio_signal,
            "usd_index_signal": usd_index_signal,
            "buyback_signal": buyback_signal,
            "open_source_signal": open_source_signal,
            "open_source_status": cli_status,
            "open_source_both_count": both_count,
            "open_source_items": open_items[:12],
        }
        return report

    def close(self):
        self.is_active = False
