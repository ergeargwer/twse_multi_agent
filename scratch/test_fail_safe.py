# -*- coding: utf-8 -*-
import os
import sys
from dotenv import load_dotenv

# Ensure we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from src.orchestrator.pipeline import OrchestratorPipeline

def test_pipeline(scenario_name, api_key_val, secret_key_val):
    print(f"\n=== 測試情境: {scenario_name} ===")
    
    # 備份原有環境變數
    orig_api = os.environ.get("SHIOAJI_API_KEY")
    orig_sj_api = os.environ.get("SJ_API_KEY")
    orig_sec = os.environ.get("SHIOAJI_SECRET_KEY")
    orig_sj_sec = os.environ.get("SJ_SECRET_KEY")
    
    # 設定測試環境變數
    if api_key_val is None:
        if "SHIOAJI_API_KEY" in os.environ: del os.environ["SHIOAJI_API_KEY"]
        if "SJ_API_KEY" in os.environ: del os.environ["SJ_API_KEY"]
    else:
        os.environ["SHIOAJI_API_KEY"] = api_key_val
        os.environ["SJ_API_KEY"] = api_key_val
        
    if secret_key_val is None:
        if "SHIOAJI_SECRET_KEY" in os.environ: del os.environ["SHIOAJI_SECRET_KEY"]
        if "SJ_SECRET_KEY" in os.environ: del os.environ["SJ_SECRET_KEY"]
    else:
        os.environ["SHIOAJI_SECRET_KEY"] = secret_key_val
        os.environ["SJ_SECRET_KEY"] = secret_key_val

    try:
        pipeline = OrchestratorPipeline(symbol="2379.TW", task_id="test_task_id")
        pipeline.run_phase_one()
        pipeline.run_phase_two_parallel()
        
        # 讀取分析結果
        ingested = pipeline.context.read("ingested_data")
        veto_report = pipeline.context.read("risk_veto_report")
        asset_report = pipeline.context.read("asset_allocation_report")
        
        print(f"Ingested Status: {ingested.get('account_data_status')}")
        print(f"Veto Triggered: {veto_report.get('veto')}")
        print(f"Veto Reason: {veto_report.get('veto_reason')}")
        print(f"Asset Cash Ratio: {asset_report.get('cash_ratio')}")
        print(f"Asset Objective Findings: {asset_report.get('objective_findings')}")
        
    except Exception as e:
        print(f"發生非預期錯誤: {e}")
    finally:
        # 還原環境變數
        if orig_api is not None: os.environ["SHIOAJI_API_KEY"] = orig_api
        if orig_sj_api is not None: os.environ["SJ_API_KEY"] = orig_sj_api
        if orig_sec is not None: os.environ["SHIOAJI_SECRET_KEY"] = orig_sec
        if orig_sj_sec is not None: os.environ["SJ_SECRET_KEY"] = orig_sj_sec

def main():
    real_api = os.environ.get("SHIOAJI_API_KEY") or os.environ.get("SJ_API_KEY", "")
    real_sec = os.environ.get("SHIOAJI_SECRET_KEY") or os.environ.get("SJ_SECRET_KEY", "")
    
    # 1. 測試未設定金鑰 (not_configured)
    test_pipeline("A. 未設定金鑰", None, None)
    
    # 2. 測試錯誤金鑰 (error)
    test_pipeline("B. 錯誤金鑰", "invalid_key", "invalid_secret")
    
    # 3. 測試真實金鑰 (ok)
    if real_api and real_sec:
        test_pipeline("C. 正確金鑰", real_api, real_sec)
    else:
        print("\n跳過正確金鑰測試：.env 中無有效金鑰")

if __name__ == "__main__":
    main()
