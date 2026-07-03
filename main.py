import uuid
import json
import sys
import datetime
from dotenv import load_dotenv

# 讀取 .env
load_dotenv()

from src.orchestrator.pipeline import OrchestratorPipeline
from src.core.journal import JournalStore, JournalEntry, JournalAction
from src.core.cooldown import CooldownTracker

def main():
    target_symbol = "2379.TW"
    task_id = str(uuid.uuid4())
    
    print("=== TWSE Multi-Agent 啟動 ===")
    print(f"目標標的: {target_symbol} | 任務 ID: {task_id}\n")

    # 初始化 JournalStore 與 CooldownTracker
    journal_store = JournalStore()
    cooldown_tracker = CooldownTracker()

    pipeline = OrchestratorPipeline(
        symbol=target_symbol,
        task_id=task_id,
        journal_store=journal_store,
        cooldown_tracker=cooldown_tracker
    )

    print("--- [Phase 1] Data Ingestion ---")
    pipeline.run_phase_one()
    print("資料收集完畢，寫入 Shared Context。")

    print("\n--- [Phase 2] 平行盲測分析啟動 ---")
    pipeline.run_phase_two_parallel()
    print("四個 Base Agents (Fundamental, Technical, Institutional, Event) 分析完畢，各自報告已獨立寫入。")

    print("\n--- [Phase 3] Decision Synthesizer 衝突推演 ---")
    # 可以依需求調整預估漲幅與可容忍停損，預設使用 30% / 10%
    pipeline.run_phase_three(expected_gain_pct=30.0, max_loss_pct=10.0)
    print("匯整決策產生完畢。")

    print("\n=== 最終合成報告 (Synthesis Report) ===")
    final_report = pipeline.context.read("synthesis_report")
    print(json.dumps(final_report, indent=4, ensure_ascii=False))
    
    print("\n=== [Observability] 生成 Trace 視覺化報告 ===")
    from src.trace import TraceVisualizer
    visualizer = TraceVisualizer(task_id)
    summary = visualizer.generate_human_summary()
    mermaid = visualizer.generate_mermaid_sequence()
    
    print(summary)
    print("\n--- Mermaid Sequence Diagram ---\n")
    print(f"```mermaid\n{mermaid}\n```")

    # 若為互動終端，詢問使用者是否要寫入投資日記
    if sys.stdin.isatty():
        try:
            user_input = input("\n是否要為本次分析寫入投資日記？(y/N): ").strip().lower()
            if user_input == "y":
                emotion = input("請輸入當前情緒記錄（可留空）：").strip()
                
                # 彙整 Phase 2 各 Agent 訊號摘要作為理性理由
                reason_parts = []
                fund = pipeline.context.read("fundamental_report") or {}
                tech = pipeline.context.read("technical_report") or {}
                flow = pipeline.context.read("institutional_flow_report") or {}
                evt = pipeline.context.read("event_calendar_report") or {}
                
                pe_sig = fund.get("pe_percentile_signal")
                rev_sig = fund.get("revenue_achievement_signal")
                bot_sig = tech.get("bottom_signal")
                top_sig = tech.get("top_reversal_signal")
                flow_sig = flow.get("foreign_flow_reversal_signal")
                margin_sig = evt.get("margin_ratio_signal")
                buyback_sig = evt.get("buyback_signal")
                
                for name, sig in [
                    ("估值", pe_sig), ("營收", rev_sig), 
                    ("底部", bot_sig), ("高點", top_sig), 
                    ("籌碼", flow_sig), ("融資", margin_sig), 
                    ("庫藏股", buyback_sig)
                ]:
                    if sig and sig != "資料源待補" and sig != "無明顯訊號":
                        reason_parts.append(f"{name}: {sig}")
                
                reason = " | ".join(reason_parts) if reason_parts else "無明顯異常訊號"
                
                while True:
                    try:
                        pos_input = input("請輸入操作後部位比例 (0.0~1.0，預設 0.0): ").strip()
                        position_ratio = float(pos_input) if pos_input else 0.0
                        if 0.0 <= position_ratio <= 1.0:
                            break
                        print("部位比例必須在 0.0 到 1.0 之間。")
                    except ValueError:
                        print("請輸入有效的數字。")
                        
                print("請選擇操作類別：")
                print("1. 觀察 (預設)")
                print("2. 分批進場")
                print("3. 分批減碼")
                print("4. 停損")
                print("5. 停利")
                action_choice = input("請輸入號碼 (1-5): ").strip()
                action_map = {
                    "1": JournalAction.OBSERVE,
                    "2": JournalAction.BATCH_IN,
                    "3": JournalAction.BATCH_OUT,
                    "4": JournalAction.STOP_LOSS,
                    "5": JournalAction.STOP_GAIN
                }
                action = action_map.get(action_choice, JournalAction.OBSERVE)
                
                entry = JournalEntry(
                    symbol=target_symbol,
                    timestamp=datetime.datetime.now().isoformat(),
                    action=action,
                    reason=reason,
                    emotion=emotion,
                    position_ratio_after=position_ratio
                )
                journal_store.append_entry(task_id, entry)
                print(f"已成功寫入投資日記至 trace/task_id={task_id}/journal.json")
        except Exception as e:
            print(f"寫入投資日記時發生錯誤: {e}")

if __name__ == "__main__":
    main()
