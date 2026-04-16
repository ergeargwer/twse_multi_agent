import threading
from typing import Dict, Any

from src.core.context import SharedContext
from src.agents.ingestion import DataIngestionAgent
from src.agents.fundamental import FundamentalAgent
from src.agents.technical import TechnicalAgent
from src.agents.institutional import InstitutionalFlowAgent
from src.agents.event import EventCalendarAgent
from src.agents.synthesizer import DecisionSynthesizerAgent
from src.trace import TraceCollector

def run_agent_in_thread(agent_class, context: SharedContext, report_key: str, collector: TraceCollector, stage_name: str):
    agent = agent_class()
    ingested_state = context.read("ingested_data")
    if ingested_state:
        try:
            report = agent.analyze(ingested_state)
            
            # Record trace
            processing_summary = report.get("objective_findings", [])
            collector.record_agent_trace(
                stage_name=stage_name,
                input_data=ingested_state,
                processing_summary=processing_summary,
                output_data=report
            )
            
            context.write(report_key, report)
        except Exception as e:
            # If the agent crashes, still print the traceback to console
            import traceback
            traceback.print_exc()
            
    agent.close()

class OrchestratorPipeline:
    def __init__(self, symbol: str, task_id: str):
        self.symbol = symbol
        self.task_id = task_id
        self.context = SharedContext(task_id=task_id, symbol=symbol)
        self.trace_collector = TraceCollector(task_id)

    def run_phase_one(self):
        ingestion_agent = DataIngestionAgent(symbol=self.symbol)
        unified_data = {
            "price_action": ingestion_agent.fetch_price_volume_data(),
            "institutional_flow": ingestion_agent.fetch_institutional_margin_data(),
            "fundamentals": ingestion_agent.fetch_fundamental_data(),
            "calendar_events": ingestion_agent.fetch_calendar_events()
        }
        
        self.trace_collector.record_agent_trace(
            stage_name="01_ingestion",
            input_data={"symbol": self.symbol},
            processing_summary=["Data fetched successfully from DataIngestionAgent"],
            output_data=unified_data
        )
        
        self.context.write("ingested_data", unified_data)
        ingestion_agent.close()

    def run_phase_two_parallel(self):
        threads = []
        # 定義要平行啟動的 Agent 與寫入的 Key
        agent_configs = [
            (FundamentalAgent, "fundamental_report", "02_fundamental"),
            (TechnicalAgent, "technical_report", "02_technical"),
            (InstitutionalFlowAgent, "institutional_flow_report", "02_institutional"),
            (EventCalendarAgent, "event_calendar_report", "02_event")
        ]

        for agent_class, report_key, stage_name in agent_configs:
            t = threading.Thread(target=run_agent_in_thread, args=(agent_class, self.context, report_key, self.trace_collector, stage_name))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    def run_phase_three(self):
        agent = DecisionSynthesizerAgent()
        synthesis_report = agent.synthesize(self.context.data, collector=self.trace_collector)
        self.context.write("synthesis_report", synthesis_report)
        agent.close()

    def execute_all(self):
        self.run_phase_one()
        self.run_phase_two_parallel()
        self.run_phase_three()
        return self.context
