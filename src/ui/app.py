# -*- coding: utf-8 -*-
import os
import uuid
import datetime
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from typing import List, Dict, Any

# 讀取 .env
load_dotenv()

from src.orchestrator.pipeline import OrchestratorPipeline
from src.core.journal import JournalStore, JournalEntry, JournalAction
from src.core.cooldown import CooldownTracker

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
        
        # 讀取 Shioaji 帳戶資料 (使用 pipeline 的 mock 或從環境變數嘗試讀取)
        from src.integrations import shioaji_client
        api_key = os.environ.get("SHIOAJI_API_KEY") or os.environ.get("SJ_API_KEY", "")
        secret_key = os.environ.get("SHIOAJI_SECRET_KEY") or os.environ.get("SJ_SECRET_KEY", "")
        
        api = None
        account_balance = {"cash": 1500000.0, "total_limit": 3000000.0}
        position_list = []
        
        if api_key and secret_key:
            with st.spinner("正在安全連接券商取得最新帳務與部位資料..."):
                try:
                    api = shioaji_client.login(api_key, secret_key)
                    account_balance = shioaji_client.get_account_balance(api)
                    position_list = shioaji_client.get_position_list(api)
                except Exception as e:
                    st.warning(f"無法登入永豐金 API: {e}。使用預設展示資料。")
                finally:
                    if api:
                        shioaji_client.logout(api)
        else:
            position_list = [
                {"symbol": "2330", "name": "台積電", "shares": 1000, "cost": 600000.0, "unrealized_pnl": 211000.0},
                {"symbol": "2379", "name": "瑞昱", "shares": 500, "cost": 200000.0, "unrealized_pnl": -15000.0}
            ]
            
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
                if ratio > 0.30:
                    st.error(f"警訊：單一標的 {k} 占比達 {ratio*100:.2f}%，已超出 30.0% 的安全限制，請調整資產配置以防禦未知風險。")
                    has_alert = True
        if not has_alert:
            st.success("所有標的部位比例皆符合單一持股低於 30.0% 的風控安全指標。")

    # 2. 個股分析報告
    elif page == "個股分析報告":
        st.title("個股分析報告")
        st.write("藉由多 Agent 平行盲測與修行者決策機制，進行情境推演。")
        
        tab1, tab2 = st.tabs(["新增分析推演", "歷史報告查詢"])
        
        with tab1:
            col1, col2, col3 = st.columns(3)
            symbol = col1.text_input("請輸入股票代號 (例: 2379.TW)", value="2379.TW", key="new_report_symbol")
            expected_gain = col2.number_input("預期漲幅 (%)", min_value=1.0, max_value=200.0, value=30.0, step=1.0, key="new_report_gain")
            max_loss = col3.number_input("可容忍停損 (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0, key="new_report_loss")
            
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
                        context = pipeline.execute_all(expected_gain_pct=expected_gain, max_loss_pct=max_loss)
                        synthesis_report = context.read("synthesis_report")
                        pricing_report = context.read("pricing_keeper_report") or context.read("pricing_gatekeeper_report") or {}
                        veto_report = context.read("risk_veto_report") or {}
                        
                        st.success("分析推演完成！")
                        st.write("---")
                        
                        # 優先檢查風控否決 (Veto) 的結果
                        veto_active = veto_report.get("veto", False)
                        veto_reason = veto_report.get("veto_reason", "")
                        
                        if veto_active:
                            veto_html = f"""
                            <div class="veto-card">
                                <h3 style="margin: 0 0 8px 0; color: #dc2626; font-weight: 800;">[風控煞車已啟動]</h3>
                                <div style="font-size: 1.1rem; color: #991b1b; line-height: 1.6;">原因：{veto_reason}</div>
                            </div>
                            """
                            st.markdown(veto_html, unsafe_allow_html=True)
                            st.warning("本次推演未通過安全門檻，強烈建議秉持紀律，暫停交易衝動。")
                        else:
                            st.success("### [風控檢測通過]\n未觸發任何否決條件。")
                            
                        # 顯示定價把關標籤
                        gatekeeper_signal = pricing_report.get("price_reasonableness_signal", "無此訊號")
                        st.write(f"**定價合理性把關標籤**：`{gatekeeper_signal}`")
                        
                        # 顯示 synthesizer 產出的報告
                        st.write("### 決策彙整報告 (Decision Synthesis Report)")
                        report_text = synthesis_report.get("scenario_synthesis", "無報告內容")
                        st.text_area("報告原文", report_text, height=450, key="new_report_output")
                        
                        st.caption("免責聲明：本報告僅基於客觀數據推演，請投資人維持獨立思考，自行承擔損益風險。")
                    except Exception as e:
                        st.error(f"分析執行時發生錯誤: {e}")
                        import traceback
                        st.code(traceback.format_exc())
                        
        with tab2:
            st.write("### 查詢過去產出的分析報告")
            
            # 定義歷史報告讀取函數
            def get_report_history() -> List[Dict[str, Any]]:
                import glob
                import os
                import json
                import datetime
                
                trace_dir = "trace"
                if not os.path.exists(trace_dir):
                    return []
                    
                reports = []
                pattern = os.path.join(trace_dir, "task_id=*", "03_llm_output.trace.json")
                files = glob.glob(pattern)
                
                for fpath in files:
                    try:
                        mtime = os.path.getmtime(fpath)
                        dt = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                        
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            
                        final_report = data.get("final_report", {})
                        scenario_synthesis = final_report.get("scenario_synthesis", "")
                        
                        # 取得 symbol
                        ingestion_path = fpath.replace("03_llm_output.trace.json", "01_ingestion.trace.json")
                        symbol = "未知"
                        if os.path.exists(ingestion_path):
                            with open(ingestion_path, "r", encoding="utf-8") as inf:
                                ing_data = json.load(inf)
                            symbol = ing_data.get("input_data", {}).get("symbol", "未知")
                            
                        reports.append({
                            "time": dt,
                            "symbol": symbol,
                            "report": scenario_synthesis,
                            "mtime": mtime
                        })
                    except Exception:
                        pass
                        
                reports.sort(key=lambda x: x["mtime"], reverse=True)
                return reports
                
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
                    st.caption("免責聲明：本報告僅基於歷史客觀數據推演，請投資人維持獨立思考，自行承擔損益風險。")
            else:
                st.info("目前尚無任何歷史報告紀錄。")

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
