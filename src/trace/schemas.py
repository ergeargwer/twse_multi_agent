from typing import TypedDict, Any, List, Dict, Optional

class AgentTrace(TypedDict):
    stage_name: str
    input_trace: Dict[str, Any]
    processing_trace: List[str]
    output_trace: Dict[str, Any]

class LLMTrace(TypedDict):
    model: str
    provider: str
    system_prompt: str
    user_prompt: str
    raw_output: str
    final_report: Dict[str, Any]
