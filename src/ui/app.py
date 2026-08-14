# -*- coding: utf-8 -*-
import os
import json
import uuid
import datetime
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Any

# 固定讀專案根目錄 .env（streamlit run src/ui/app.py 時不可依賴 cwd）
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

import importlib
from src.orchestrator.pipeline import OrchestratorPipeline
from src.core.journal import JournalStore, JournalEntry, JournalAction
from src.core.cooldown import CooldownTracker
from src.trace import visualizer as visualizer_mod
from src.analysis.behavior_risk import run_behavior_risk
from src.ui.risk_chart import create_risk_chart
from src.core.rule_config import (
    get_agent_rules,
    get_rules_path,
    get_rules_updated_at,
    get_rules_version,
    load_rules,
)
from src.core.prompt_config import get_persona_path, get_persona_version, load_persona

importlib.reload(visualizer_mod)
TraceVisualizer = visualizer_mod.TraceVisualizer


def render_mermaid(diagram: str, height: int = 720) -> None:
    payload = json.dumps(diagram)
    components.html(
        f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    html, body {{ margin: 0; background: transparent; }}
    #graph {{ padding: 4px 0 8px 0; }}
  </style>
</head>
<body>
  <div id="graph">流程圖載入中...</div>
  <script>
    const src = {payload};
    mermaid.initialize({{
      startOnLoad: false,
      theme: "base",
      securityLevel: "loose",
      themeVariables: {{
        fontFamily: "Inter, Noto Sans TC, sans-serif",
        primaryColor: "#eef2ff",
        primaryTextColor: "#1e3c72",
        primaryBorderColor: "#2a5298",
        lineColor: "#64748b"
      }}
    }});
    mermaid.render("twseFlow", src).then((out) => {{
      document.getElementById("graph").innerHTML = out.svg;
    }}).catch((err) => {{
      document.getElementById("graph").innerHTML =
        "<pre style='color:#991b1b;white-space:pre-wrap'>" + String(err) + "</pre>";
    }});
  </script>
</body>
</html>""",
        height=height,
        scrolling=True,
    )


def render_agent_reports(task_id: str, key_prefix: str) -> None:
    """逐一展開各 Agent 的發現、訊號與 JSON，供修改 agent 時對照。"""
    viz = TraceVisualizer(task_id)
    reports = viz.iter_agent_reports()
    if not any(item["present"] for item in reports):
        st.info("此任務尚無 Agent trace 可供檢視。")
        return

    rows = []
    for item in reports:
        signal_text = "、".join(
            f"{k}={v}" for k, v in item["signals"].items() if v not in ("", None)
        )
        rows.append({
            "階段": item["stage"],
            "Agent": item["title"],
            "原始碼": item["source"],
            "狀態": "已產出" if item["present"] else "未產出",
            "摘要 / 訊號": item["summary"] or signal_text or ("—" if item["present"] else "無 trace"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(f"Trace 目錄：`trace/task_id={task_id}/`。展開下方卡片可看輸入、判斷與完整輸出 JSON。")

    for item in reports:
        badge = "已產出" if item["present"] else "未產出"
        with st.expander(f"{item['title']}　{item['stage']}　[{badge}]　{item['source']}", expanded=False):
            if not item["present"]:
                st.caption("這次 pipeline 沒有寫入此 Agent 的 trace，通常是較舊的任務或缺資料。")
                continue
            st.write(f"**對應程式**：`{item['source']}`")
            if item["signals"]:
                st.write("**關鍵訊號**")
                st.json(item["signals"])
            if item["findings"]:
                st.write("**客觀發現 / 判斷過程**")
                for finding in item["findings"]:
                    st.write(f"- {finding}")
            if item["summary"]:
                st.write("**摘要**")
                st.write(item["summary"])
            if item["input"]:
                st.write("**輸入（input_trace，長列表已裁切）**")
                st.json(item["input"])
            if item["output"]:
                st.write("**輸出（output / prompt，長列表已裁切）**")
                st.json(item["output"])
            raw_json = json.dumps(item["raw"], ensure_ascii=False, indent=2)
            st.download_button(
                label=f"下載 {item['stage']} 完整 JSON",
                data=raw_json,
                file_name=f"{item['stage']}.trace.json",
                mime="application/json",
                key=f"{key_prefix}_{item['stage']}_dl",
            )


def load_open_source_from_task(task_id: str) -> Dict[str, Any]:
    ingestion_path = os.path.join("trace", f"task_id={task_id}", "01_ingestion.trace.json")
    if not os.path.exists(ingestion_path):
        return {}
    try:
        with open(ingestion_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        output = data.get("output_trace") or {}
        return output.get("open_source_events") or {}
    except Exception:
        return {}


def render_open_source_panel(bundle: Dict[str, Any], key_prefix: str) -> None:
    """顯示 Grok / Gemini 合作蒐集結果。"""
    st.write("### 開放來源事件（Grok CLI + Gemini CLI）")
    if not bundle:
        st.caption("此次沒有開放來源蒐集結果。")
        return
    status = bundle.get("status") or "missing"
    both_count = bundle.get("both_count") or 0
    sides = bundle.get("sides") or {}
    st.caption(
        f"狀態 `{status}`；雙源交叉 {both_count} 筆。全部標為未驗證，不得視為事實或買賣依據。"
    )
    if sides:
        cols = st.columns(2)
        for idx, name in enumerate(("grok", "gemini")):
            side = sides.get(name) or {}
            cols[idx].write(
                f"**{name}**：`{side.get('status', 'n/a')}`　"
                f"{side.get('item_count', 0)} 筆"
                + (f"　{side.get('error')}" if side.get("error") else "")
            )
    items = bundle.get("items") or []
    if not items:
        st.info("沒有可顯示的開放來源條目。")
        return
    rows = []
    for item in items:
        rows.append({
            "日期": item.get("date") or "",
            "類型": item.get("kind") or "",
            "交叉": item.get("agreement") or "",
            "來源": "/".join(item.get("sources") or []),
            "標題": item.get("title") or "",
            "摘要": item.get("summary") or "",
            "URL": item.get("url") or "",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, key=f"{key_prefix}_os_table")


RULE_FIELD_LABELS = {
    "pe_percentile_attractive_stdev": "本益比位階低於此標準差視為便宜具吸引力",
    "pe_percentile_extreme_stdev": "本益比位階高於此標準差觸發極端溢價警示",
    "peg_min_growth_pct": "PEG 估值法適用的最低年增率門檻",
    "revenue_achievement_min_ratio": "月營收達成率低於此比例視為「疑似價值陷阱」",
    "pe_high_threshold": "本益比高於此值視為「相對較高區間」",
    "pe_low_threshold": "本益比低於此值視為「相對較低區間」",
    "revenue_growth_strong_pct": "月營收年增率達此值視為「雙位數成長」",
    "overbought_price_vs_ma20_pct": "價格高於20MA幾倍視為偏離",
    "overbought_pe_vs_5y_avg_pct": "本益比高於5年均值幾倍視為偏高",
    "oversold_pe_vs_5y_avg_pct": "本益比低於5年均值幾倍視為偏低",
    "oversold_price_vs_ma60_pct": "價格低於60MA幾倍視為「利空未反映」",
    "min_risk_reward_ratio": "風暴比安全底線（預期漲幅 / 可容忍停損）",
    "max_position_concentration_pct": "單一標的占總資產上限",
    "concentration_alert_pct": "觸發集中度警訊的門檻",
    "position_step_small": "部位小於等於分界時建議調節幅度",
    "position_step_large": "部位大於分界時建議調節幅度",
    "position_step_switch_pct": "切換兩種調節幅度的部位分界",
    "reversal_min_sell_amount": "資金轉向警訊：連兩日賣超絕對值門檻",
    "reversal_sell_vs_buy_ratio": "或賣超金額達前期買超此比例",
    "kd_period": "KD 指標週期參數",
    "bottom_signal_prior_drop_pct": "判定「大跌後」的收盤價比較基準",
    "bottom_signal_volume_multiplier": "單日爆量倍數門檻",
    "bottom_signal_shadow_ratio": "長下影線相對實體倍數",
    "top_signal_volume_multiplier": "創高爆量倍數門檻",
    "top_signal_body_pct": "長黑K實體占收盤價比例門檻",
    "ma20_oversold_dev_pct": "月線負乖離達此幅度視為超跌型態",
    "ma20_extreme_oversold_dev_pct": "月線極端負乖離型態門檻",
    "ma20_overbought_dev_pct": "月線正乖離達此幅度視為高追價（可被使用者輸入覆蓋）",
    "emotional_lookback_entries": "檢視近期日記筆數",
    "emotional_trigger_count": "情緒關鍵字出現筆數達此值視為「傾向偏高」",
    "margin_ratio_low": "融資維持率下限",
    "margin_ratio_high": "融資維持率上限",
    "days_to_recall_alert": "距融券強制回補日少於此天數才提示",
    "days_to_ex_div_alert": "距除權息日少於此天數才提示",
}

AGENT_SECTION_TITLES = {
    "fundamental_agent": "基本面 Agent",
    "pricing_gatekeeper_agent": "定價把關 Agent",
    "risk_veto_agent": "風控煞車 Agent",
    "asset_allocation_agent": "資產配置 Agent",
    "institutional_flow_agent": "法人籌碼 Agent",
    "technical_agent": "技術面 Agent",
    "behavior_risk_agent": "行為風險 Agent",
    "discipline_agent": "執行紀律 Agent",
    "event_agent": "制度事件 Agent",
}


def render_system_settings_panel() -> None:
    st.write("### 系統設定（唯讀）")
    st.info(
        "如需調整數值，請編輯 `config/rules.yaml` 或 `config/prompts/synthesizer_persona_v1.yaml` 後重新啟動系統。"
        "可編輯介面規劃於下一階段。"
    )
    try:
        rules = load_rules()
        rules_path = get_rules_path()
        st.write(
            f"**規則版本**：`{get_rules_version()}`　"
            f"**更新日期**：`{get_rules_updated_at()}`　"
            f"**檔案**：`{rules_path}`"
        )
        rows = []
        for agent_key, title in AGENT_SECTION_TITLES.items():
            block = rules.get(agent_key)
            if not isinstance(block, dict):
                continue
            for field, value in block.items():
                rows.append({
                    "Agent": title,
                    "欄位": field,
                    "數值": value,
                    "說明": RULE_FIELD_LABELS.get(field, ""),
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.download_button(
            label="下載規則原始檔 rules.yaml",
            data=rules_path.read_text(encoding="utf-8"),
            file_name="rules.yaml",
            mime="text/yaml",
            key="dl_rules_yaml",
        )
    except Exception as exc:
        st.error(f"無法載入規則設定檔：{exc}")

    st.write("---")
    try:
        persona = load_persona()
        prompt_path = get_persona_path()
        st.write(
            f"**Prompt 人設版本**：`{get_persona_version()}`　"
            f"**名稱**：`{persona.get('name', '')}`　"
            f"**更新日期**：`{persona.get('updated_at', '')}`"
        )
        st.write("**人設全文**")
        st.text_area(
            "persona_intro",
            value=str(persona.get("persona_intro") or ""),
            height=220,
            disabled=True,
            label_visibility="collapsed",
            key="persona_intro_view",
        )
        st.write("**輸出限制**")
        for index, item in enumerate(persona.get("output_constraints") or [], start=1):
            st.write(f"{index}. {item}")
        st.download_button(
            label="下載 Prompt 原始檔 synthesizer_persona_v1.yaml",
            data=prompt_path.read_text(encoding="utf-8"),
            file_name="synthesizer_persona_v1.yaml",
            mime="text/yaml",
            key="dl_persona_yaml",
        )
    except Exception as exc:
        st.error(f"無法載入 Prompt 人設檔：{exc}")


def load_price_history_from_task(task_id: str) -> List[Dict[str, Any]]:
    """從 Phase 1 ingestion trace 取出日線 raw_history。"""
    ingestion_path = os.path.join("trace", f"task_id={task_id}", "01_ingestion.trace.json")
    if not os.path.exists(ingestion_path):
        return []
    try:
        with open(ingestion_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        output = data.get("output_trace") or {}
        price = output.get("price_action") or {}
        return price.get("raw_history") or []
    except Exception:
        return []


def render_behavior_risk_panel(
    raw_history: List[Dict[str, Any]],
    symbol: str,
    key_prefix: str,
    default_ma20_dev: float = 5.0,
) -> None:
    """可調月線乖離門檻重算行為風險圖與近期事件表。"""
    st.warning("所有分析僅為市場行為風險提示，非投資建議，非主力判斷。")
    if not raw_history:
        st.info("尚無日線價量。請先執行 Pipeline，或在本頁以「只抓價量」取得資料。")
        return

    ma20_dev = st.slider(
        "高追價：月線乖離門檻 (%)",
        min_value=1.0,
        max_value=15.0,
        value=float(default_ma20_dev),
        step=0.5,
        key=f"{key_prefix}_ma20",
    )
    result = run_behavior_risk(raw_history, ma20_dev_threshold_pct=ma20_dev)
    signal = result["signal"]
    if signal == "高追價風險":
        st.error(f"最新行為標記：{signal}。{result['latest_risk_reason']}")
    elif signal in ("月線極端負乖離型態", "月線負乖離型態"):
        st.warning(f"最新行為標記：{signal}。{result['latest_risk_reason']}")
    elif signal == "低殺出風險":
        st.warning(f"最新行為標記：{signal}。{result['latest_risk_reason']}")
    else:
        st.success(f"最新行為標記：{signal}")

    cols = st.columns(4)
    cols[0].metric("分析根數", result["bars_analyzed"])
    cols[1].metric("高追價筆數", result["high_chase_count"])
    cols[2].metric("低殺出筆數", result["low_sell_count"])
    cols[3].metric("極端負乖離", result.get("extreme_oversold_count", 0))

    if result["frame"] is not None and not result["frame"].empty:
        st.plotly_chart(
            create_risk_chart(result["frame"], symbol),
            use_container_width=True,
            key=f"{key_prefix}_chart",
        )
        st.caption("將游標移到三角形標記可查看風險原因。本圖使用 Pipeline 已收集的日線，不另打分鐘線 API。")

    if result["recent_events"]:
        st.write("### 近期行為風險事件")
        st.dataframe(pd.DataFrame(result["recent_events"]), use_container_width=True, hide_index=True)
    else:
        st.info("近期內未偵測出顯著的行為乖離或背離風險。")


def get_report_history(require_llm: bool = True) -> List[Dict[str, Any]]:
    import glob

    trace_dir = "trace"
    if not os.path.exists(trace_dir):
        return []

    reports = []
    task_dirs = glob.glob(os.path.join(trace_dir, "task_id=*"))
    for task_dir in task_dirs:
        try:
            task_id = os.path.basename(task_dir).replace("task_id=", "")
            llm_path = os.path.join(task_dir, "03_llm_output.trace.json")
            ingestion_path = os.path.join(task_dir, "01_ingestion.trace.json")
            if require_llm and not os.path.exists(llm_path):
                continue
            scenario_synthesis = ""
            if os.path.exists(llm_path):
                with open(llm_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                scenario_synthesis = (data.get("final_report") or {}).get("scenario_synthesis", "") or data.get("raw_output", "")
            symbol = "未知"
            if os.path.exists(ingestion_path):
                with open(ingestion_path, "r", encoding="utf-8") as inf:
                    ing_data = json.load(inf)
                symbol = (
                    (ing_data.get("input_data") or {}).get("symbol")
                    or (ing_data.get("output_trace") or {}).get("symbol")
                    or "未知"
                )
            stamp_file = llm_path if os.path.exists(llm_path) else ingestion_path
            if not os.path.exists(stamp_file):
                stamp_file = task_dir
            mtime = os.path.getmtime(stamp_file)
            reports.append({
                "time": datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": symbol,
                "report": scenario_synthesis,
                "mtime": mtime,
                "task_id": task_id,
            })
        except Exception:
            pass
    reports.sort(key=lambda x: x["mtime"], reverse=True)
    return reports

st.set_page_config(
    page_title="TWSE Multi-Agent AI 投資管家",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入美化樣式 (極致美學無 emoji 規範)
st.markdown("""
<style>
/* 載入 Inter 與 Outfit 字體 */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Outfit:wght@400;600;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', 'Outfit', -apple-system, sans-serif;
}

/* 頂級漸層卡片樣式 */
.premium-card {
    background: linear-gradient(135deg, rgba(30, 60, 114, 0.04) 0%, rgba(42, 82, 152, 0.04) 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.03);
    backdrop-filter: blur(4px);
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.premium-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px 0 rgba(31, 38, 135, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
}

/* 否決警示卡片 */
.veto-card {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(220, 38, 38, 0.08) 100%);
    border: 1px solid rgba(239, 68, 68, 0.25);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
    box-shadow: 0 8px 24px rgba(239, 68, 68, 0.03);
}

/* 漸層按鈕 */
.stButton>button {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%) !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
}

.stButton>button:hover {
    transform: scale(1.02) !important;
    box-shadow: 0 4px 15px rgba(42, 82, 152, 0.25) !important;
}
</style>
""", unsafe_allow_html=True)

# 密碼驗證機制 (已取消密碼解鎖功能，改為直接存取)
def check_password():
    return True

if check_password():
    # 初始化全域共用 Tracker / Store 至 session_state
    if "journal_store" not in st.session_state:
        st.session_state.journal_store = JournalStore()
    if "cooldown_tracker" not in st.session_state:
        st.session_state.cooldown_tracker = CooldownTracker()
        
    journal_store = st.session_state.journal_store
    cooldown_tracker = st.session_state.cooldown_tracker

    # 側邊欄導覽
    st.sidebar.title("導覽選單")
    page = st.sidebar.radio(
        "前往頁面",
        ["總覽儀表板", "個股分析報告", "投資日記", "執行紀律追蹤"]
    )
    
    st.sidebar.write("---")
    st.sidebar.caption("樹之修行者與理性的交會")
    
    # 1. 總覽儀表板
    if page == "總覽儀表板":
        st.title("總覽儀表板")
        st.subheader("資產與部位集中度概覽")
        
        # 讀取 Shioaji 帳戶資料 (僅真實資料，查詢失敗或未設定時顯示提示，不回傳假資料)
        from src.integrations import shioaji_client
        api_key, secret_key = shioaji_client.get_credentials()
        
        account_balance = None
        position_list = None
        query_success = False
        
        if not api_key or not secret_key:
            st.info("尚未設定 Shioaji 帳戶金鑰，請於專案根目錄 .env 設定 SHIOAJI_API_KEY / SHIOAJI_SECRET_KEY（或 SJ_API_KEY / SJ_SECRET_KEY）後重新啟動即可查看真實帳戶資料。")
        else:
            with st.spinner("正在安全連接券商取得最新帳務與部位資料..."):
                api = None
                try:
                    api = shioaji_client.login(api_key, secret_key)
                    account_balance = shioaji_client.get_account_balance(api)
                    position_list = shioaji_client.get_position_list(api)
                    query_success = True
                except shioaji_client.ShioajiQueryError as e:
                    st.error(f"帳戶資料查詢失敗：{str(e)}")
                except Exception as e:
                    st.error(f"帳戶資料連線或認證失敗：{str(e)}")
                finally:
                    if api:
                        shioaji_client.logout(api)
                        
        if query_success and account_balance is not None and position_list is not None:
            cash = float(account_balance.get("cash", 0.0))
            
            # 部位計算
            total_pos_val = 0.0
            position_rows = []
            for pos in position_list:
                symbol = pos.get("symbol", "")
                name = pos.get("name", "未知")
                shares = pos.get("shares", 0)
                cost = pos.get("cost", 0.0)
                unrealized_pnl = pos.get("unrealized_pnl", 0.0)
                m_val = cost + unrealized_pnl
                total_pos_val += m_val
                position_rows.append({
                    "股票代號": symbol,
                    "股票名稱": name,
                    "持股股數": f"{shares:,}",
                    "持有成本 (元)": f"{cost:,.0f}",
                    "未實現損益 (元)": f"{unrealized_pnl:,.0f}",
                    "目前估計市值 (元)": f"{m_val:,.0f}",
                    "raw_val": m_val,
                    "display_label": f"{symbol} {name}"
                })
                
            total_assets = cash + total_pos_val
            cash_ratio = (cash / total_assets) if total_assets > 0 else 0.0
            
            # 指標卡片 (自定義 HSL 漸層毛玻璃風格)
            card_html = f"""
            <div style="display: flex; gap: 20px; margin-bottom: 24px;">
                <div class="premium-card" style="flex: 1; border-left: 5px solid #1e3c72;">
                    <div style="font-size: 0.9rem; color: #888; font-weight: 600;">總資產價值 (元)</div>
                    <div style="font-size: 2rem; font-weight: 800; margin-top: 8px; color: #1e3c72;">{total_assets:,.0f}</div>
                </div>
                <div class="premium-card" style="flex: 1; border-left: 5px solid #2a5298;">
                    <div style="font-size: 0.9rem; color: #888; font-weight: 600;">現金餘額 (元)</div>
                    <div style="font-size: 2rem; font-weight: 800; margin-top: 8px; color: #2a5298;">{cash:,.0f} <span style="font-size: 0.9rem; font-weight: 400; color: #666;">({cash_ratio*100:.2f}%)</span></div>
                </div>
                <div class="premium-card" style="flex: 1; border-left: 5px solid #c33764;">
                    <div style="font-size: 0.9rem; color: #888; font-weight: 600;">證券總市值 (元)</div>
                    <div style="font-size: 2rem; font-weight: 800; margin-top: 8px; color: #c33764;">{total_pos_val:,.0f} <span style="font-size: 0.9rem; font-weight: 400; color: #666;">({(1.0-cash_ratio)*100:.2f}%)</span></div>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            
            # 部位明細
            st.write("---")
            st.write("### 目前庫存部位明細")
            if position_rows:
                df_pos = pd.DataFrame(position_rows)
                st.dataframe(df_pos.drop(columns=["raw_val", "display_label"]), use_container_width=True)
            else:
                st.info("目前庫存無持股。")
                
            # 集中度 analyses 圖表
            st.write("---")
            st.write("### 資產配置集中度比例圖")
            chart_data = {"現金": cash}
            for item in position_rows:
                chart_data[item["display_label"]] = item["raw_val"]
                
            df_chart = pd.DataFrame(list(chart_data.items()), columns=["資產", "金額"])
            df_chart["占比 (%)"] = df_chart["金額"] / total_assets * 100
            
            st.bar_chart(df_chart.set_index("資產")["占比 (%)"])
            
            # 檢查集中度警訊
            st.write("### 集中度風控檢查結果")
            has_alert = False
            for k, v in chart_data.items():
                if k != "現金":
                    ratio = v / total_assets
                    alert_pct = get_agent_rules("asset_allocation_agent")["concentration_alert_pct"]
                    if ratio > alert_pct:
                        st.error(
                            f"警訊：單一標的 {k} 占比達 {ratio*100:.2f}%，"
                            f"已超出 {alert_pct*100:.1f}% 的安全限制，請調整資產配置以防禦未知風險。"
                        )
                        has_alert = True
            if not has_alert:
                alert_pct = get_agent_rules("asset_allocation_agent")["concentration_alert_pct"]
                st.success(
                    f"所有標的部位比例皆符合單一持股低於 {alert_pct*100:.1f}% 的風控安全指標。"
                )

    # 2. 個股分析報告
    elif page == "個股分析報告":
        st.title("個股分析報告")
        st.write("藉由多 Agent 平行盲測與修行者決策機制，進行情境推演。")
        
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            ["新增分析推演", "歷史報告查詢", "分析流程", "Agent 報告", "行為風險", "系統設定"]
        )
        
        with tab1:
            col1, col2, col3, col4 = st.columns(4)
            symbol = col1.text_input("請輸入股票代號 (例: 2379.TW)", value="2379.TW", key="new_report_symbol")
            expected_gain = col2.number_input("預期漲幅 (%)", min_value=1.0, max_value=200.0, value=30.0, step=1.0, key="new_report_gain")
            max_loss = col3.number_input("可容忍停損 (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0, key="new_report_loss")
            vwap_threshold = col4.number_input("月線乖離門檻 (%)", min_value=1.0, max_value=15.0, value=5.0, step=0.5, key="new_report_ma20")
            
            if st.button("開始執行 Pipeline 分析", key="run_pipeline_btn"):
                task_id = str(uuid.uuid4())
                
                with st.spinner("正在收集資料並進行平行決策推演，請稍候..."):
                    try:
                        pipeline = OrchestratorPipeline(
                            symbol=symbol,
                            task_id=task_id,
                            journal_store=journal_store,
                            cooldown_tracker=cooldown_tracker
                        )
                        # 執行 Ingestion + Agents + Synthesizer
                        context = pipeline.execute_all(
                            expected_gain_pct=expected_gain,
                            max_loss_pct=max_loss,
                            ma20_dev_threshold_pct=vwap_threshold,
                        )
                        st.session_state["last_analysis_task_id"] = task_id
                        st.session_state["last_analysis_symbol"] = symbol
                        ingested = context.read("ingested_data") or {}
                        st.session_state["last_price_history"] = (
                            (ingested.get("price_action") or {}).get("raw_history") or []
                        )
                        st.session_state["last_ma20_threshold"] = vwap_threshold
                        st.session_state["last_open_source"] = ingested.get("open_source_events") or {}
                        synthesis_report = context.read("synthesis_report")
                        pricing_report = context.read("pricing_keeper_report") or context.read("pricing_gatekeeper_report") or {}
                        veto_report = context.read("risk_veto_report") or {}
                        behavior_report = context.read("behavior_risk_report") or {}
                        
                        st.success("分析推演完成！")
                        st.write("---")
                        
                        # 優先檢查風控否決 (Veto) 的結果
                        veto_active = veto_report.get("veto", False)
                        veto_reason = veto_report.get("veto_reason", "")
                        
                        if veto_active:
                            # 檢查是否為帳戶資料不可用引起的攔截
                            is_acc_veto = ("帳戶資料不可用" in veto_reason or 
                                           "未設定" in veto_reason or 
                                           "查詢失敗" in veto_reason or 
                                           "帳戶金鑰" in veto_reason)
                            
                            veto_html = f"""
                            <div class="veto-card">
                                <h3 style="margin: 0 0 8px 0; color: #dc2626; font-weight: 800;">[風控煞車已啟動]</h3>
                                <div style="font-size: 1.1rem; color: #991b1b; line-height: 1.6;">原因：{veto_reason}</div>
                            </div>
                            """
                            st.markdown(veto_html, unsafe_allow_html=True)
                            
                            if is_acc_veto:
                                st.warning("本次分析因帳戶資料不可用，風控煞車已預設攔截，非個股本身訊號問題。")
                            else:
                                st.warning("本次推演未通過安全門檻，強烈建議秉持紀律，暫停交易衝動。")
                        else:
                            st.success("### [風控檢測通過]\n未觸發任何否決條件。")
                            
                        # 顯示定價把關與行為風險標籤
                        gatekeeper_signal = pricing_report.get("price_reasonableness_signal", "無此訊號")
                        behavior_signal = behavior_report.get("behavior_risk_signal", "無明顯訊號")
                        st.write(f"**定價合理性把關標籤**：`{gatekeeper_signal}`")
                        st.write(f"**行為風險標記**：`{behavior_signal}`")
                        event_report = context.read("event_calendar_report") or {}
                        st.write(f"**開放來源標記**：`{event_report.get('open_source_signal', '無明顯訊號')}`")
                        render_open_source_panel(
                            st.session_state.get("last_open_source") or {},
                            key_prefix="new_run_os",
                        )

                        st.write("### 行為風險圖表")
                        render_behavior_risk_panel(
                            st.session_state.get("last_price_history") or [],
                            symbol,
                            key_prefix="new_run_risk",
                            default_ma20_dev=vwap_threshold,
                        )
                        
                        # 顯示 synthesizer 產出的報告
                        st.write("### 決策彙整報告 (Decision Synthesis Report)")
                        report_text = synthesis_report.get("scenario_synthesis", "無報告內容")
                        st.text_area("報告原文", report_text, height=450, key="new_report_output")

                        st.write("### 各 Agent 結果（修改功能時可對照）")
                        render_agent_reports(task_id, key_prefix="new_run")

                        st.write("### 本次分析流程")
                        render_mermaid(TraceVisualizer(task_id).generate_run_flowchart(), height=780)
                        
                        st.caption("免責聲明：本報告僅基於客觀數據推演，請投資人維持獨立思考，自行承擔損益風險。")
                    except Exception as e:
                        st.error(f"分析執行時發生錯誤: {e}")
                        import traceback
                        st.code(traceback.format_exc())
            elif st.session_state.get("last_analysis_task_id"):
                last_tid = st.session_state["last_analysis_task_id"]
                last_sym = st.session_state.get("last_analysis_symbol", "")
                st.info(f"上次分析仍可檢視：`{last_sym}` / `{last_tid}`")
                last_hist = st.session_state.get("last_price_history") or load_price_history_from_task(last_tid)
                st.session_state["last_price_history"] = last_hist
                last_os = st.session_state.get("last_open_source") or load_open_source_from_task(last_tid)
                st.session_state["last_open_source"] = last_os
                render_open_source_panel(last_os, key_prefix="last_run_os")
                st.write("### 行為風險圖表")
                render_behavior_risk_panel(
                    last_hist,
                    last_sym,
                    key_prefix="last_run_risk",
                    default_ma20_dev=float(st.session_state.get("last_ma20_threshold", 5.0)),
                )
                st.write("### 各 Agent 結果（修改功能時可對照）")
                render_agent_reports(last_tid, key_prefix="last_run")
                        
        with tab2:
            st.write("### 查詢過去產出的分析報告")
            history_reports = get_report_history()
            
            if history_reports:
                report_options = [f"[{r['time']}] {r['symbol']}" for r in history_reports]
                selected_option = st.selectbox("請選擇要檢視的歷史報告", report_options)
                
                if selected_option:
                    selected_idx = report_options.index(selected_option)
                    selected_report = history_reports[selected_idx]
                    
                    st.write(f"**報告時間**：{selected_report['time']}")
                    st.write(f"**股票標的**：`{selected_report['symbol']}`")
                    st.write("---")
                    
                    # 顯示報告內容
                    st.write("### 歷史決策彙整報告")
                    st.text_area("報告原文", selected_report["report"], height=450, key="history_report_output")
                    if selected_report.get("task_id"):
                        st.write("### 各 Agent 結果（修改功能時可對照）")
                        render_agent_reports(selected_report["task_id"], key_prefix="hist")
                        st.write("### 該次分析流程")
                        render_mermaid(
                            TraceVisualizer(selected_report["task_id"]).generate_run_flowchart(),
                            height=780,
                        )
                    st.caption("免責聲明：本報告僅基於歷史客觀數據推演，請投資人維持獨立思考，自行承擔損益風險。")
            else:
                st.info("目前尚無任何歷史報告紀錄。")

        with tab3:
            st.write("### 個股分析報告流程")
            st.write(
                "系統採三階段流水線：先統一收集資料，再由多個 Agent **平行盲測** "
                "（彼此看不到對方報告），最後才由合成器與 LLM 做矛盾比對與情境推演。"
            )
            render_mermaid(TraceVisualizer.generate_pipeline_flowchart(), height=820)
            st.write("---")
            st.write("**階段說明**")
            st.markdown(
                """
- **Phase 1 資料收集**：封裝價量、財報估值、三大法人、融資券、行事曆與 Shioaji 帳戶／庫存；並平行啟動 Grok Build CLI 與 Gemini CLI 蒐集未驗證新聞／公告，寫入 Shared Context。
- **Phase 2 平行盲測**：基本面、技術面、法人籌碼、制度事件、資產配置、定價把關、風控煞車、執行紀律，以及行為風險（VWAP 乖離／量價背離／假跌破），各自只讀自己需要的欄位。
- **Phase 3 決策合成**：匯整九份報告，交由 LLM 做多空矛盾與情境推演；程式再附上風暴比與分批操作提醒。風控煞車若否決，會置頂攔截說明。行為風險只當觀察標記，不會自動否決。
                """.strip()
            )

        with tab4:
            st.write("### 各 Agent 結果報告")
            st.write(
                "這裡可逐一檢視每次 pipeline 寫下的 trace：輸入欄位、客觀發現、訊號與完整 JSON。"
                "改 Agent 規則時，請對照右側原始碼路徑與輸出結構。"
            )
            history_for_agents = get_report_history(require_llm=False)
            if not history_for_agents:
                st.info("尚無歷史任務。請先在「新增分析推演」跑一次。")
            else:
                default_tid = st.session_state.get("last_analysis_task_id", history_for_agents[0]["task_id"])
                options = [f"[{r['time']}] {r['symbol']}  ({r['task_id'][:8]})" for r in history_for_agents]
                default_idx = 0
                for i, item in enumerate(history_for_agents):
                    if item["task_id"] == default_tid:
                        default_idx = i
                        break
                picked = st.selectbox("選擇任務", options, index=default_idx, key="agent_report_task")
                picked_idx = options.index(picked)
                picked_task = history_for_agents[picked_idx]
                st.write(
                    f"**標的**：`{picked_task['symbol']}`　"
                    f"**時間**：{picked_task['time']}　"
                    f"**task_id**：`{picked_task['task_id']}`"
                )
                render_agent_reports(picked_task["task_id"], key_prefix="browse")

        with tab5:
            st.write("### 股價行為風險提示")
            st.write(
                "沿用 stock_risk_alert 的規則：高追價（VWAP 乖離、高檔量縮、創新高波動急縮）"
                "與低殺出（跌破支撐無量、假跌破、低檔盤旋）。資料來自既有日線 raw_history，不另呼叫分鐘線。"
            )
            last_tid = st.session_state.get("last_analysis_task_id")
            last_sym = st.session_state.get("last_analysis_symbol", "2379.TW")
            last_hist = st.session_state.get("last_price_history") or []
            if not last_hist and last_tid:
                last_hist = load_price_history_from_task(last_tid)
                st.session_state["last_price_history"] = last_hist

            source = st.radio(
                "資料來源",
                ["使用最近一次 Pipeline 日線", "從歷史任務載入", "只抓價量（不跑 LLM）"],
                horizontal=True,
                key="behavior_risk_source",
            )

            selected_symbol = last_sym
            selected_history = last_hist
            selected_vwap = float(st.session_state.get("last_ma20_threshold", 5.0))

            if source == "從歷史任務載入":
                history_for_risk = get_report_history(require_llm=False)
                if not history_for_risk:
                    st.info("尚無歷史任務。請先在「新增分析推演」跑一次，或改用只抓價量。")
                    selected_history = []
                else:
                    options = [f"[{r['time']}] {r['symbol']}  ({r['task_id'][:8]})" for r in history_for_risk]
                    picked = st.selectbox("選擇任務", options, key="behavior_risk_task")
                    picked_idx = options.index(picked)
                    picked_task = history_for_risk[picked_idx]
                    selected_symbol = picked_task["symbol"]
                    selected_history = load_price_history_from_task(picked_task["task_id"])
            elif source == "只抓價量（不跑 LLM）":
                fetch_symbol = st.text_input("股票代號 (例: 2379.TW)", value=last_sym or "2379.TW", key="behavior_only_symbol")
                if st.button("抓取日線並標記風險", key="behavior_fetch_btn"):
                    with st.spinner("正在擷取日線價量..."):
                        from src.agents.ingestion import DataIngestionAgent
                        ingest = DataIngestionAgent(symbol=fetch_symbol)
                        try:
                            price = ingest.fetch_price_volume_data()
                            selected_history = price.get("raw_history") or []
                            selected_symbol = fetch_symbol
                            st.session_state["behavior_standalone_history"] = selected_history
                            st.session_state["behavior_standalone_symbol"] = selected_symbol
                        finally:
                            ingest.close()
                selected_history = st.session_state.get("behavior_standalone_history") or []
                selected_symbol = st.session_state.get("behavior_standalone_symbol") or fetch_symbol

            render_behavior_risk_panel(
                selected_history,
                selected_symbol,
                key_prefix="tab5_risk",
                default_ma20_dev=selected_vwap,
            )

        with tab6:
            render_system_settings_panel()

    # 3. 投資日記
    elif page == "投資日記":
        st.title("投資日記")
        st.subheader("交易紀錄與心態複盤")
        
        # 顯示歷史日記表格
        st.write("### 歷史日記清單")
        symbol_filter = st.text_input("以股票代號篩選 (例如: 2379.TW)", value="")
        
        history_entries = journal_store.get_history(symbol_filter) if symbol_filter else []
        # 如果為空，嘗試載入 2379.TW 的作為示範
        if not symbol_filter:
            history_entries = journal_store.get_history("2379.TW")
            
        if history_entries:
            rows = []
            for entry in history_entries:
                rows.append({
                    "股票代號": entry.symbol,
                    "時間戳記": entry.timestamp,
                    "操作類別": entry.action,
                    "理性理由": entry.reason,
                    "情緒記錄": entry.emotion,
                    "操作後部位比例": entry.position_ratio_after
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("查無此標的之歷史日記，請於下方新增。")
            
        # 表單新增日記 (人工記錄券商 App 完成的操作)
        st.write("---")
        st.write("### 新增今日投資日記 (手動記錄)")
        
        with st.form("add_journal_form"):
            new_symbol = st.text_input("股票代號 (例: 2379.TW)", value="2379.TW")
            new_action = st.selectbox(
                "操作類別",
                [JournalAction.OBSERVE.value, JournalAction.BATCH_IN.value, JournalAction.BATCH_OUT.value, JournalAction.STOP_LOSS.value, JournalAction.STOP_GAIN.value]
            )
            new_reason = st.text_area("理性理由 (例: 突破盤整均線 / 估值具吸引力)", value="")
            new_emotion = st.text_input("當前情緒記錄 (例: 平靜 / 焦慮 / 追高亢奮)", value="")
            new_ratio = st.slider("操作後部位比例 (0.0 ~ 1.0)", min_value=0.0, max_value=1.0, value=0.0, step=0.05)
            
            submit_button = st.form_submit_button("寫入投資日記")
            if submit_button:
                if not new_symbol:
                    st.error("請輸入股票代號。")
                else:
                    new_entry = JournalEntry(
                        symbol=new_symbol,
                        timestamp=datetime.datetime.now().isoformat(),
                        action=JournalAction(new_action),
                        reason=new_reason,
                        emotion=new_emotion,
                        position_ratio_after=new_ratio
                    )
                    temp_task_id = str(uuid.uuid4())
                    journal_store.append_entry(temp_task_id, new_entry)
                    st.success(f"已成功記錄！日記存檔路徑: trace/task_id={temp_task_id}/journal.json")
                    st.rerun()

    # 4. 執行紀律追蹤
    elif page == "執行紀律追蹤":
        st.title("執行紀律追蹤")
        st.subheader("心態紀律與交易冷卻狀態")
        
        target_symbol = st.text_input("要追蹤的股票代號 (例: 2379.TW)", value="2379.TW")
        st.write("---")
        
        # 1. 查詢冷卻狀態
        st.write("### 交易冷卻狀態")
        is_passed = cooldown_tracker.is_cooldown_passed(target_symbol)
        
        if is_passed:
            st.success("當前狀態: [已過交易冷卻期]，頭腦清醒。")
        else:
            st.error("當前狀態: [尚未過交易冷卻期]。")
            st.warning("距離您上次對此標的產生交易衝動尚未滿 24 小時，建議先散步或離開螢幕 5-10 分鐘，平復情緒後再行審視。")
            
        # 手動更新衝動時間戳記以測試
        if st.button("記錄一次交易意圖（開始 24 小時交易冷卻）"):
            cooldown_tracker.request_trade_intent(target_symbol)
            st.info("已記錄交易意圖，冷卻期開始重新計算。")
            st.rerun()
            
        # 2. 情緒化交易傾向
        st.write("---")
        st.write("### 心態紀律回顧 (近 5 筆交易)")
        history = journal_store.get_history(target_symbol)
        recent = history[-5:]
        
        keywords = ["焦慮", "恐慌", "亢奮", "衝動", "貪婪", "害怕", "生氣", "挫折", "後悔", "盲目", "興奮"]
        emotional_count = 0
        
        if recent:
            st.write(f"以下為您對 {target_symbol} 記錄的近期心態回顧：")
            for entry in recent:
                emotion = entry.emotion
                has_emotion = any(kw in emotion for kw in keywords)
                if has_emotion:
                    emotional_count += 1
                status_icon = "[情緒波動]" if has_emotion else "[狀態正常]"
                st.write(f"- **時間**: {entry.timestamp[:19].replace('T', ' ')} | **類別**: {entry.action} | 情緒評估: {status_icon} `{emotion if emotion else '無紀錄'}`")
                
            st.write("")
            if len(recent) >= 3 and emotional_count >= 3:
                st.error(f"警訊：近期有 {emotional_count}/5 筆交易涉及情緒波動 ({', '.join(keywords)})。目前情緒化交易傾向偏高，建議放慢操作腳步，給自己留白。")
            else:
                st.success(f"目前情緒控制良好，僅有 {emotional_count}/5 筆交易記錄情緒波動。請繼續保持理性的隱者狀態。")
        else:
            st.info("查無此標的之近期投資日記心態紀錄。")
