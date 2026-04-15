import uuid
import json
from src.orchestrator.pipeline import OrchestratorPipeline

def main():
    target_symbol = "2330.TW"
    task_id = str(uuid.uuid4())
    
    print(f"=== TWSE Multi-Agent 啟動 ===")
    print(f"目標標的: {target_symbol} | 任務 ID: {task_id}\n")

    pipeline = OrchestratorPipeline(symbol=target_symbol, task_id=task_id)

    print("--- [Phase 1] Data Ingestion ---")
    pipeline.run_phase_one()
    print("資料收集完畢，寫入 Shared Context。")

    print("\n--- [Phase 2] 平行盲測分析啟動 ---")
    pipeline.run_phase_two_parallel()
    print("四個 Base Agents (Fundamental, Technical, Institutional, Event) 分析完畢，各自報告已獨立寫入。")

    print("\n--- [Phase 3] Decision Synthesizer 衝突推演 ---")
    pipeline.run_phase_three()
    print("匯整決策產生完畢。")

    print("\n=== 最終合成報告 (Synthesis Report) ===")
    final_report = pipeline.context.read("synthesis_report")
    print(json.dumps(final_report, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    main()
