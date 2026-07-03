# -*- coding: utf-8 -*-
"""
本模組僅提供查詢類功能，不封裝任何委託下單 (Order) 相關 API。
如需下單功能，須經過使用者另行且獨立的架構決策，不在本專案範圍內。
"""
import shioaji as sj
from typing import Dict, Any, List

class ShioajiQueryError(Exception):
    """Shioaji 查詢例外類別"""
    pass

def login(api_key: str, secret_key: str) -> sj.Shioaji:
    # 登入永豐金 Shioaji API
    api = sj.Shioaji()
    api.login(api_key=api_key, secret_key=secret_key)
    return api

def logout(api: sj.Shioaji) -> None:
    # 登出 API
    try:
        api.logout()
    except Exception:
        pass

def get_account_balance(api: sj.Shioaji) -> Dict[str, Any]:
    # 取得帳戶餘額 (現金餘額、交易額度)
    # 返回統一格式: {"cash": float, "total_limit": float}
    try:
        balance_data = api.account_balance()
        # Shioaji 的 AccountBalance 物件屬性為 acc_balance 或是 cash_balance
        cash = getattr(balance_data, "acc_balance", None)
        if cash is None:
            cash = getattr(balance_data, "cash_balance", None)
            
        if cash is None:
            raise ValueError("無效的餘額欄位回傳")
            
        total_limit = getattr(balance_data, "collateral", 0.0)
        return {
            "cash": float(cash),
            "total_limit": float(total_limit)
        }
    except Exception as e:
        raise ShioajiQueryError(f"查詢帳戶餘額失敗: {str(e)}") from e

def get_position_list(api: sj.Shioaji) -> List[Dict[str, Any]]:
    # 取得庫存部位列表
    # 返回格式: [{"symbol": str, "name": str, "shares": int, "cost": float, "unrealized_pnl": float}]
    try:
        from shioaji.constant import Unit
        positions = api.list_positions(api.stock_account, unit=Unit.Share)
        res = []
        for pos in positions:
            symbol = getattr(pos, "code", "")
            shares = int(getattr(pos, "quantity", 0))
            price = float(getattr(pos, "price", 0.0))
            cost = price * shares
            unrealized_pnl = float(getattr(pos, "pnl", 0.0))
            
            # 取得股票中文名稱
            name = "未知"
            try:
                contract = api.Contracts.Stocks[symbol]
                name = getattr(contract, "name", "未知")
            except Exception:
                pass
                
            res.append({
                "symbol": symbol,
                "name": name,
                "shares": shares,
                "cost": cost,
                "unrealized_pnl": unrealized_pnl
            })
        return res
    except Exception as e:
        raise ShioajiQueryError(f"查詢庫存部位失敗: {str(e)}") from e

def get_snapshot(api: sj.Shioaji, symbol: str) -> Dict[str, Any]:
    # 取得個股即時報價快照
    try:
        stock_id = symbol.split(".")[0]
        contract = api.Contracts.Stocks[stock_id]
        snapshots = api.snapshots([contract])
        if snapshots:
            snap = snapshots[0]
            return {
                "symbol": symbol,
                "close": float(getattr(snap, "close", 0.0)),
                "open": float(getattr(snap, "open", 0.0)),
                "high": float(getattr(snap, "high", 0.0)),
                "low": float(getattr(snap, "low", 0.0)),
                "volume": float(getattr(snap, "total_volume", 0.0))
            }
        else:
            raise ValueError("快照回傳列表為空")
    except Exception as e:
        raise ShioajiQueryError(f"查詢即時報價失敗: {str(e)}") from e

def get_kbars(api: sj.Shioaji, symbol: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    # 取得歷史 K 棒資料
    try:
        stock_id = symbol.split(".")[0]
        contract = api.Contracts.Stocks[stock_id]
        kbars = api.kbars(contract, start=start_date, end=end_date)
        if kbars:
            import pandas as pd
            df = pd.DataFrame({**kbars})
            res = []
            for idx, row in df.iterrows():
                res.append({
                    "date": str(row["ts"]),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"])
                })
            return res
        else:
            raise ValueError("K棒回傳資料為空")
    except Exception as e:
        raise ShioajiQueryError(f"查詢歷史 K 棒失敗: {str(e)}") from e
