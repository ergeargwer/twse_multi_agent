import threading
from typing import Dict, Any

from src.core.context import SharedContext
from src.agents.ingestion import DataIngestionAgent
from src.agents.fundamental import FundamentalAgent
from src.agents.technical import TechnicalAgent
from src.agents.institutional import InstitutionalFlowAgent
from src.agents.event import EventCalendarAgent
from src.agents.synthesizer import DecisionSynthesizerAgent

def run_agent_in_thread(agent_class, context: SharedContext, report_key: str):
    agent = agent_class()
    ingested_state = context.read("ingested_data")
    if ingested_state:
        report = agent.analyze(ingested_state)
        context.write(report_key, report)
    agent.close()

class OrchestratorPipeline:
    def __init__(self, symbol: str, task_id: str):
        self.symbol = symbol
        self.context = SharedContext(task_id=task_id, symbol=symbol)

    def run_phase_one(self):
        ingestion_agent = DataIngestionAgent(symbol=self.symbol)
        unified_data = {
            "price_action": ingestion_agent.fetch_price_volume_data(),
            "institutional_flow": ingestion_agent.fetch_institutional_margin_data(),
            "fundamentals": ingestion_agent.fetch_fundamental_data(),
            "calendar_events": ingestion_agent.fetch_calendar_events()
        }
        self.context.write("ingested_data", unified_data)
        ingestion_agent.close()

    def run_phase_two_parallel(self):
        threads = []
        # 定義要平行啟動的 Agent 與寫入的 Key
        agent_configs = [
            (FundamentalAgent, "fundamental_report"),
            (TechnicalAgent, "technical_report"),
            (InstitutionalFlowAgent, "institutional_flow_report"),
            (EventCalendarAgent, "event_calendar_report")
        ]

        for agent_class, report_key in agent_configs:
            t = threading.Thread(target=run_agent_in_thread, args=(agent_class, self.context, report_key))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    def run_phase_three(self):
        agent = DecisionSynthesizerAgent()
        synthesis_report = agent.synthesize(self.context.data)
        self.context.write("synthesis_report", synthesis_report)
        agent.close()

    def execute_all(self):
        self.run_phase_one()
        self.run_phase_two_parallel()
        self.run_phase_three()
        return self.context
