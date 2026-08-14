import json
import os
from typing import Dict, Any, List
from .schemas import AgentTrace, LLMTrace

class TraceCollector:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.trace_dir = os.path.join("trace", f"task_id={self.task_id}")
        os.makedirs(self.trace_dir, exist_ok=True)
        
    def _write_json(self, filename: str, data: Any):
        filepath = os.path.join(self.trace_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def record_agent_trace(self, stage_name: str, input_data: Dict[str, Any], processing_summary: List[str], output_data: Dict[str, Any]):
        trace: AgentTrace = {
            "stage_name": stage_name,
            "input_trace": input_data,
            "processing_trace": processing_summary,
            "output_trace": output_data
        }
        self._write_json(f"{stage_name}.trace.json", trace)

    def record_llm_trace(self, model: str, provider: str, system_prompt: str, user_prompt: str, raw_output: str, final_report: Dict[str, Any]):
        trace: LLMTrace = {
            "model": model,
            "provider": provider,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "raw_output": raw_output,
            "final_report": final_report
        }
        self._write_json("03_llm_prompt.trace.json", {
            "model": model,
            "provider": provider,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        })
        self._write_json("03_llm_output.trace.json", {
            "raw_output": raw_output,
            "final_report": final_report
        })
