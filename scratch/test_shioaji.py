# -*- coding: utf-8 -*-
import os
import sys
from dotenv import load_dotenv

# Ensure we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from src.integrations import shioaji_client

def main():
    api_key = os.environ.get("SHIOAJI_API_KEY") or os.environ.get("SJ_API_KEY", "")
    secret_key = os.environ.get("SHIOAJI_SECRET_KEY") or os.environ.get("SJ_SECRET_KEY", "")
    
    print(f"API Key: {api_key}")
    print(f"Secret Key length: {len(secret_key) if secret_key else 0}")
    
    if not api_key or not secret_key:
        print("未在 .env 中偵測到金鑰。")
        return
        
    try:
        print("正在嘗試登入 Shioaji...")
        api = shioaji_client.login(api_key, secret_key)
        print("登入成功！")
        
        print("正在查詢帳戶餘額...")
        balance = api.account_balance()
        print(f"原始帳戶餘額回傳: {balance}")
        
        print("正在查詢庫存部位...")
        positions = api.list_positions(api.stock_account)
        print(f"原始庫存回傳: {positions}")
        
        shioaji_client.logout(api)
        print("已成功登出。")
    except Exception as e:
        print(f"執行時發生錯誤，詳細原因: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
