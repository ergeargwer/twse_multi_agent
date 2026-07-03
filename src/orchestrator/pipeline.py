import os
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

# 新增輔助人格 Agent
from src.agents.asset_allocation import AssetAllocationAgent
from src.agents.pricing_gatekeeper import PricingGatekeeperAgent
from src.agents.risk_veto import RiskVetoAgent
from src.agents.discipline import DisciplineAgent

from src.integrations import shioaji_client

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
    def __init__(self, symbol: str, task_id: str, journal_store=None, cooldown_tracker=None):
        self.symbol = symbol
        self.task_id = task_id
        self.context = SharedContext(task_id=task_id, symbol=symbol)
        self.trace_collector = TraceCollector(task_id)
        
        from src.core.journal import JournalStore
        from src.core.cooldown import CooldownTracker
        self.journal_store = journal_store or JournalStore()
        self.cooldown_tracker = cooldown_tracker or CooldownTracker()

    def run_phase_one(self, expected_gain_pct: float = 30.0, max_loss_pct: float = 10.0):
        ingestion_agent = DataIngestionAgent(symbol=self.symbol)
        
        # 串接 Shioaji 取得帳戶與部位資訊
        api_key = os.environ.get("SHIOAJI_API_KEY") or os.environ.get("SJ_API_KEY", "")
        secret_key = os.environ.get("SHIOAJI_SECRET_KEY") or os.environ.get("SJ_SECRET_KEY", "")
        
        api = None
        account_balance = None
        position_list = None
        account_data_status = "ok"
        account_data_error = ""

        if not api_key or not secret_key:
            account_data_status = "not_configured"
            print("未設定 SHIOAJI_API_KEY/SHIOAJI_SECRET_KEY，本次分析將不包含真實帳戶資料")
        else:
            try:
                api = shioaji_client.login(api_key, secret_key)
                account_balance = shioaji_client.get_account_balance(api)
                position_list = shioaji_client.get_position_list(api)
                account_data_status = "ok"
            except shioaji_client.ShioajiQueryError as e:
                account_data_status = "error"
                account_data_error = str(e)
                account_balance = None
                position_list = None
                print(f"[Shioaji Ingestion Error] 帳戶資料查詢失敗: {e}")
                import traceback
                traceback.print_exc()
            except Exception as e:
                account_data_status = "error"
                account_data_error = f"連線或認證失敗: {str(e)}"
                account_balance = None
                position_list = None
                print(f"[Shioaji Ingestion Error] 認證或未知錯誤: {e}")
                import traceback
                traceback.print_exc()
            finally:
                if api:
                    shioaji_client.logout(api)
                    
        unified_data = {
            "symbol": self.symbol,
            "expected_gain_pct": expected_gain_pct,
            "max_loss_pct": max_loss_pct,
            "account_data_status": account_data_status,
            "account_data_error": account_data_error,
            "account_balance": account_balance,
            "position_list": position_list,
            "price_action": ingestion_agent.fetch_price_volume_data(),
            "institutional_flow": ingestion_agent.fetch_institutional_margin_data(),
            "fundamentals": ingestion_agent.fetch_fundamental_data(),
            "calendar_events": ingestion_agent.fetch_calendar_events(),
            "account_balance": account_balance,
            "position_list": position_list,
            "journal_history": [e.to_dict() for e in self.journal_store.get_history(self.symbol)],
            "cooldown_passed": self.cooldown_tracker.is_cooldown_passed(self.symbol)
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
        # 定義要平行啟動的 Agent 與寫入的 Key (包含四個新增的輔助人格 Agent)
        agent_configs = [
            (FundamentalAgent, "fundamental_report", "02_fundamental"),
            (TechnicalAgent, "technical_report", "02_technical"),
            (InstitutionalFlowAgent, "institutional_flow_report", "02_institutional"),
            (EventCalendarAgent, "event_calendar_report", "02_event"),
            (AssetAllocationAgent, "asset_allocation_report", "02_asset_allocation"),
            (PricingGatekeeperAgent, "pricing_gatekeeper_report", "02_pricing_gatekeeper"),
            (RiskVetoAgent, "risk_veto_report", "02_risk_veto"),
            (DisciplineAgent, "discipline_report", "02_discipline")
        ]

        for agent_class, report_key, stage_name in agent_configs:
            t = threading.Thread(target=run_agent_in_thread, args=(agent_class, self.context, report_key, self.trace_collector, stage_name))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    def run_phase_three(self, expected_gain_pct: float = 30.0, max_loss_pct: float = 10.0):
        agent = DecisionSynthesizerAgent()
        synthesis_report = agent.synthesize(
            self.context.data,
            collector=self.trace_collector,
            cooldown_tracker=self.cooldown_tracker,
            symbol=self.symbol,
            expected_gain_pct=expected_gain_pct,
            max_loss_pct=max_loss_pct
        )
        self.context.write("synthesis_report", synthesis_report)
        agent.close()

    def execute_all(self, expected_gain_pct: float = 30.0, max_loss_pct: float = 10.0):
        self.run_phase_one(expected_gain_pct=expected_gain_pct, max_loss_pct=max_loss_pct)
        self.run_phase_two_parallel()
        self.run_phase_three(expected_gain_pct=expected_gain_pct, max_loss_pct=max_loss_pct)
        return self.context
