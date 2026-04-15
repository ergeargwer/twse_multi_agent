import json
from typing import Dict, Any

class DataIngestionAgent:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.is_active = True

    def fetch_price_volume_data(self) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Data Ingestion Agent 已關閉，無法抓取資料。")
        return {"date": "2026-04-14", "open": 800, "high": 815, "low": 795, "close": 810, "volume": 35000, "ma5": 805, "ma20": 790, "ma60": 760}

    def fetch_institutional_margin_data(self) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Data Ingestion Agent 已關閉，無法抓取資料。")
        return {"foreign_investor": 1500, "investment_trust": 300, "dealer": 300, "margin_balance_change": -50}

    def fetch_fundamental_data(self) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Data Ingestion Agent 已關閉，無法抓取資料。")
        return {"pe_ratio": 22.5, "pb_ratio": 4.2, "eps": 35.0, "monthly_revenue_growth_yoy": 12.5}

    def fetch_calendar_events(self) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Data Ingestion Agent 已關閉，無法抓取資料。")
        return {"days_to_ex_dividend": 15, "days_to_margin_recall": 5, "in_etf_rebalance_watchlist": True}

    def close(self):
        self.is_active = False
