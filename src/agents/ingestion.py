import os
import datetime
import requests
import pandas as pd
from typing import Dict, Any

class DataIngestionAgent:
    def __init__(self, symbol: str):
        self.symbol = symbol # e.g. "2330.TW"
        self.fm_symbol = symbol.split(".")[0] # e.g. "2330"
        self.is_active = True
        self.api_url = "https://api.finmindtrade.com/api/v4/data"
        self.token = os.environ.get("FINMIND_API_KEY", "")
        
        # Initialize Shioaji API if credentials are provided
        self.sj_active = False
        from src.integrations.shioaji_client import get_credentials, is_simulation
        sj_api_key, sj_secret_key = get_credentials()
        sj_simulation = is_simulation()

        if sj_api_key and sj_secret_key:
            try:
                import shioaji as sj
                print(f"[Shioaji API] Initializing API Client (Simulation={sj_simulation})...")
                self.sj_api = sj.Shioaji(simulation=sj_simulation)
                self.sj_api.login(api_key=sj_api_key, secret_key=sj_secret_key)
                self.sj_active = True
                print("[Shioaji API] Login successful.")
            except Exception as e:
                print(f"[Shioaji API Init Error] Failed to connect/login: {e}")
                self.sj_active = False
        
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
            "ma60": None,
            "raw_history": []
        }
        if not self.is_active:
            return result
        
        # Need at least 60 trading days, so fetch 120 calendar days
        start_date = (datetime.date.today() - datetime.timedelta(days=120)).strftime("%Y-%m-%d")
        
        # Try fetching from Shioaji first
        if self.sj_active:
            print(f"[Shioaji API] Fetching daily K-bars for {self.fm_symbol} (120 days)...")
            try:
                contract = self.sj_api.Contracts.Stocks[self.fm_symbol]
                
                # Fetch in 30-day chunks to respect API limitations
                today = datetime.date.today()
                chunks = []
                for i in range(4):
                    chunk_start = (today - datetime.timedelta(days=(i+1)*30 - 1)).strftime("%Y-%m-%d")
                    chunk_end = (today - datetime.timedelta(days=i*30)).strftime("%Y-%m-%d")
                    
                    kbars = self.sj_api.kbars(contract, start=chunk_start, end=chunk_end)
                    if kbars:
                        df_chunk = pd.DataFrame({**kbars})
                        chunks.append(df_chunk)
                
                if chunks:
                    df = pd.concat(chunks).drop_duplicates(subset=["ts"]).sort_values("ts")
                    closes = df["Close"].tolist()
                    if closes:
                        result["close"] = closes[-1]
                        if len(closes) >= 5:
                            result["ma5"] = round(sum(closes[-5:]) / 5, 2)
                        if len(closes) >= 20:
                            result["ma20"] = round(sum(closes[-20:]) / 20, 2)
                        if len(closes) >= 60:
                            result["ma60"] = round(sum(closes[-60:]) / 60, 2)
                        
                        raw_history = []
                        for idx, row in df.iterrows():
                            raw_history.append({
                                "date": str(row["ts"]),
                                "open": float(row["Open"]),
                                "high": float(row["High"]),
                                "low": float(row["Low"]),
                                "close": float(row["Close"]),
                                "volume": float(row["Volume"])
                            })
                        result["raw_history"] = raw_history
                        print(f"[Shioaji API] Price, MAs and raw history successfully fetched from Shioaji.")
                        return result
            except Exception as e:
                print(f"[Shioaji API Error] Failed to fetch kbars: {e}. Falling back to FinMind...")
        
        # Fallback to FinMind
        print("[FinMind API] Fetching price/volume data...")
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
                
                raw_history = []
                for d in data:
                    raw_history.append({
                        "date": d.get("date"),
                        "open": float(d.get("open", 0)),
                        "high": float(d.get("max", 0)),
                        "low": float(d.get("min", 0)),
                        "close": float(d.get("close", 0)),
                        "volume": float(d.get("Trading_Volume", 0))
                    })
                result["raw_history"] = raw_history
        return result

    def fetch_institutional_margin_data(self) -> Dict[str, Any]:
        result = {
            "foreign_investor": None,
            "investment_trust": None,
            "margin_balance_change": None,
            "raw_history": []
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
            
            # Group daily net buy/sell for history
            daily_net = {}
            for row in inst_data:
                d = row.get("date")
                name = row.get("name")
                net = row.get("buy", 0) - row.get("sell", 0)
                if d not in daily_net:
                    daily_net[d] = {"foreign_investor_net": 0, "investment_trust_net": 0}
                if name == "Foreign_Investor":
                    daily_net[d]["foreign_investor_net"] += net
                elif name == "Investment_Trust":
                    daily_net[d]["investment_trust_net"] += net
            
            result["raw_history"] = [{"date": k, **v} for k, v in sorted(daily_net.items())]
        
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
            "pe_ratio": None,
            "pe_ratio_5y_avg": None,
            "pe_ratio_5y_stdev": None,
            "latest_revenue": None,
            "last_year_revenue": None
        }
        if not self.is_active:
            return result
        
        # Revenue
        start_date_rev = (datetime.date.today() - datetime.timedelta(days=400)).strftime("%Y-%m-%d")
        rev_data = self._fetch_finmind("TaiwanStockMonthRevenue", start_date_rev)
        if rev_data and len(rev_data) >= 13:
            latest_rev = rev_data[-1].get("revenue", 0)
            result["latest_revenue"] = latest_rev
            # Find the same month last year.
            last_year_month = rev_data[-1].get("revenue_month")
            last_year_year = rev_data[-1].get("revenue_year") - 1
            last_year_rev = None
            for row in reversed(rev_data[:-1]):
                if row.get("revenue_year") == last_year_year and row.get("revenue_month") == last_year_month:
                    last_year_rev = row.get("revenue", 0)
                    break
            result["last_year_revenue"] = last_year_rev
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
                
        # PE Ratio (Dataset is TaiwanStockPER) - Fetch 5 years for average
        start_date_pe = (datetime.date.today() - datetime.timedelta(days=5*365)).strftime("%Y-%m-%d")
        pe_data = self._fetch_finmind("TaiwanStockPER", start_date_pe)
        if pe_data:
            result["pe_ratio"] = pe_data[-1].get("PER")
            # Calculate 5-year average (only count positive PEs)
            pe_vals = [row.get("PER", 0) for row in pe_data if row.get("PER", 0) > 0]
            if pe_vals:
                mean_pe = sum(pe_vals) / len(pe_vals)
                result["pe_ratio_5y_avg"] = round(mean_pe, 2)
                if len(pe_vals) >= 2:
                    variance = sum((value - mean_pe) ** 2 for value in pe_vals) / (len(pe_vals) - 1)
                    result["pe_ratio_5y_stdev"] = round(variance ** 0.5, 2)
                else:
                    result["pe_ratio_5y_stdev"] = None

        return result

    def fetch_calendar_events(self) -> Dict[str, Any]:
        if not self.is_active:
            return {
                "in_etf_rebalance_watchlist": None,
                "days_to_margin_recall": None,
                "days_to_ex_dividend": None,
                "margin_maintenance_ratio": None,
                "has_large_buyback": None
            }
            
        result = {
            "in_etf_rebalance_watchlist": None,
            "days_to_margin_recall": None,
            "days_to_ex_dividend": None,
            "margin_maintenance_ratio": None,
            "has_large_buyback": None
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

    def fetch_usd_index_signal(self) -> Dict[str, Any]:
        """美元指數（ICE DXY），不是美元兌台幣。FRED 需金鑰，改用 Yahoo DX-Y.NYB。"""
        result = {
            "usd_index_20d_high": None,
            "usd_index_latest": None,
            "usd_index_data_source": "",
            "usd_index_error": "",
        }
        if not self.is_active:
            return result

        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=2mo"
        try:
            response = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "twse-multi-agent/usd-index"},
            )
            response.raise_for_status()
            payload = response.json()
            series = ((payload.get("chart") or {}).get("result") or [None])[0]
            if not series:
                result["usd_index_error"] = "Yahoo 回傳不含 DX-Y.NYB 序列"
                return result
            closes = ((series.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
            values = [float(item) for item in closes if item is not None]
            if len(values) < 20:
                result["usd_index_error"] = f"美元指數有效收盤僅 {len(values)} 筆，不足 20 日"
                result["usd_index_data_source"] = "Yahoo Finance DX-Y.NYB"
                if values:
                    result["usd_index_latest"] = values[-1]
                return result
            window = values[-20:]
            latest = window[-1]
            result["usd_index_latest"] = latest
            result["usd_index_20d_high"] = latest >= max(window)
            result["usd_index_data_source"] = "Yahoo Finance DX-Y.NYB (ICE Dollar Index)"
        except Exception as exc:
            result["usd_index_error"] = str(exc)
        return result

    def close(self):
        self.is_active = False
        if hasattr(self, "sj_api") and self.sj_active:
            try:
                self.sj_api.logout()
                print("[Shioaji API] Logged out successfully.")
            except Exception:
                pass
