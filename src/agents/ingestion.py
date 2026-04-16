import os
import datetime
import requests
from typing import Dict, Any

class DataIngestionAgent:
    def __init__(self, symbol: str):
        self.symbol = symbol # e.g. "2330.TW"
        self.fm_symbol = symbol.split(".")[0] # e.g. "2330"
        self.is_active = True
        self.api_url = "https://api.finmindtrade.com/api/v4/data"
        self.token = os.environ.get("FINMIND_API_KEY", "")
        
    def _fetch_finmind(self, dataset: str, start_date: str, end_date: str = "") -> list:
        params = {
            "dataset": dataset,
            "data_id": self.fm_symbol,
            "start_date": start_date
        }
        if end_date:
            params["end_date"] = end_date
        
        if self.token:
            params["token"] = self.token
            
        try:
            r = requests.get(self.api_url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", [])
                return data
        except Exception as e:
            print(f"[FinMind API Error] {dataset}: {e}")
        return []

    def fetch_price_volume_data(self) -> Dict[str, Any]:
        result = {
            "close": None,
            "ma5": None,
            "ma20": None,
            "ma60": None
        }
        if not self.is_active:
            return result
        
        # Need at least 60 trading days, so fetch 120 calendar days
        start_date = (datetime.date.today() - datetime.timedelta(days=120)).strftime("%Y-%m-%d")
        data = self._fetch_finmind("TaiwanStockPrice", start_date)
        if data:
            closes = [d.get("close", 0) for d in data]
            if closes:
                result["close"] = closes[-1]
                if len(closes) >= 5:
                    result["ma5"] = round(sum(closes[-5:]) / 5, 2)
                if len(closes) >= 20:
                    result["ma20"] = round(sum(closes[-20:]) / 20, 2)
                if len(closes) >= 60:
                    result["ma60"] = round(sum(closes[-60:]) / 60, 2)
        return result

    def fetch_institutional_margin_data(self) -> Dict[str, Any]:
        result = {
            "foreign_investor": None,
            "investment_trust": None,
            "margin_balance_change": None
        }
        if not self.is_active:
            return result
        
        # Fetch last 15 days to get the most recent trading day
        start_date = (datetime.date.today() - datetime.timedelta(days=15)).strftime("%Y-%m-%d")
        
        # Institutional
        inst_data = self._fetch_finmind("TaiwanStockInstitutionalInvestorsBuySell", start_date)
        if inst_data:
            # Get latest date
            latest_date = inst_data[-1].get("date")
            latest_day_data = [d for d in inst_data if d.get("date") == latest_date]
            
            foreign_net = 0
            trust_net = 0
            for row in latest_day_data:
                net = row.get("buy", 0) - row.get("sell", 0)
                name = row.get("name", "")
                if name == "Foreign_Investor":
                    foreign_net += net
                elif name == "Investment_Trust":
                    trust_net += net
            
            result["foreign_investor"] = foreign_net
            result["investment_trust"] = trust_net
        
        # Margin
        margin_data = self._fetch_finmind("TaiwanStockMarginPurchaseShortSale", start_date)
        if margin_data:
            latest_date_m = margin_data[-1].get("date")
            latest_day_margin = [d for d in margin_data if d.get("date") == latest_date_m]
            if latest_day_margin:
                row = latest_day_margin[0]
                buy = row.get("MarginPurchaseBuy", 0)
                sell = row.get("MarginPurchaseSell", 0)
                result["margin_balance_change"] = buy - sell
        
        return result

    def fetch_fundamental_data(self) -> Dict[str, Any]:
        result = {
            "eps": None,
            "monthly_revenue_growth_yoy": None,
            "pe_ratio": None
        }
        if not self.is_active:
            return result
        
        # Revenue
        start_date_rev = (datetime.date.today() - datetime.timedelta(days=400)).strftime("%Y-%m-%d")
        rev_data = self._fetch_finmind("TaiwanStockMonthRevenue", start_date_rev)
        if rev_data and len(rev_data) >= 13:
            latest_rev = rev_data[-1].get("revenue", 0)
            # Find the same month last year.
            last_year_month = rev_data[-1].get("revenue_month")
            last_year_year = rev_data[-1].get("revenue_year") - 1
            last_year_rev = None
            for row in reversed(rev_data[:-1]):
                if row.get("revenue_year") == last_year_year and row.get("revenue_month") == last_year_month:
                    last_year_rev = row.get("revenue", 0)
                    break
            
            if last_year_rev and last_year_rev > 0:
                yoy = (latest_rev - last_year_rev) / last_year_rev * 100
                result["monthly_revenue_growth_yoy"] = round(yoy, 2)
        
        # EPS (Financial Statements)
        start_date_eps = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
        eps_data = self._fetch_finmind("TaiwanStockFinancialStatements", start_date_eps)
        if eps_data:
            # filter for EPS
            eps_rows = [d for d in eps_data if d.get("type") == "EPS"]
            if eps_rows:
                result["eps"] = eps_rows[-1].get("value")
                
        # PE Ratio (Dataset is TaiwanStockPER)
        pe_data = self._fetch_finmind("TaiwanStockPER", start_date_eps)
        if pe_data:
            result["pe_ratio"] = pe_data[-1].get("PER")

        return result

    def fetch_calendar_events(self) -> Dict[str, Any]:
        if not self.is_active:
            return {
                "in_etf_rebalance_watchlist": None,
                "days_to_margin_recall": None,
                "days_to_ex_dividend": None
            }
            
        result = {
            "in_etf_rebalance_watchlist": None,
            "days_to_margin_recall": None,
            "days_to_ex_dividend": None
        }
        
        today = datetime.date.today()
        start_date_evt = today.strftime("%Y-%m-%d")
        
        # 嘗試取得除權息日
        div_data = self._fetch_finmind("TaiwanStockDividend", (today - datetime.timedelta(days=365)).strftime("%Y-%m-%d"))
        if div_data:
            # 尋找未來的除權息日
            for row in div_data:
                ex_div_date_str = row.get("ExDividendTradingDate")
                if ex_div_date_str:
                    try:
                        ex_div_date = datetime.datetime.strptime(ex_div_date_str, "%Y-%m-%d").date()
                        days_diff = (ex_div_date - today).days
                        if days_diff > 0:
                            result["days_to_ex_dividend"] = days_diff
                            break # 取最接近的未來除權息日
                    except Exception:
                        pass
                        
        # 嘗試取得融券回補日 (停券)
        susp_data = self._fetch_finmind("TaiwanStockMarginShortSaleSuspension", start_date_evt)
        if susp_data:
            for row in susp_data:
                suspend_date_str = row.get("MarginShortSaleSuspensionStart")
                if suspend_date_str:
                    try:
                        suspend_date = datetime.datetime.strptime(suspend_date_str, "%Y-%m-%d").date()
                        days_diff = (suspend_date - today).days
                        if days_diff > 0:
                            result["days_to_margin_recall"] = days_diff
                            break
                    except Exception:
                        pass
        return result

    def close(self):
        self.is_active = False
