from typing import Dict, Any

class TechnicalAgent:
    def __init__(self):
        self.is_active = True
        
    def analyze(self, ingested_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Technical Agent 已關閉，無法執行分析。")
            
        price_data = ingested_data.get("price_action", {})
        current_close = price_data.get("close", 0)
        ma5 = price_data.get("ma5", 805)
        ma20 = price_data.get("ma20", 790)
        ma60 = price_data.get("ma60", 760)
        
        # Calculate KD and custom signals using history
        raw_history = price_data.get("raw_history", [])
        
        bottom_signal = "無明顯訊號"
        top_reversal_signal = "無明顯訊號"
        
        if len(raw_history) >= 30:
            # 1. Calculate KD
            k_vals = []
            d_vals = []
            k_curr = 50.0
            d_curr = 50.0
            for i in range(len(raw_history)):
                if i < 8:
                    k_vals.append(50.0)
                    d_vals.append(50.0)
                    continue
                # Get past 9 days
                past_9 = raw_history[i-8:i+1]
                highs = [x["high"] for x in past_9]
                lows = [x["low"] for x in past_9]
                close_t = raw_history[i]["close"]
                max_high = max(highs)
                min_low = min(lows)
                if max_high > min_low:
                    rsv = (close_t - min_low) / (max_high - min_low) * 100
                else:
                    rsv = 50.0
                k_curr = (2.0/3.0) * k_curr + (1.0/3.0) * rsv
                d_curr = (2.0/3.0) * d_curr + (1.0/3.0) * k_curr
                k_vals.append(k_curr)
                d_vals.append(d_curr)
                
            # 2. Check bottom_signal
            n = len(raw_history)
            for i in range(max(20, n - 13), n - 3):
                # 大跌後
                if raw_history[i]["close"] >= raw_history[i-10]["close"] * 0.92:
                    continue
                # 單日爆量
                prev_20_vols = [x["volume"] for x in raw_history[i-20:i]]
                avg_vol = sum(prev_20_vols) / len(prev_20_vols) if prev_20_vols else 1
                if raw_history[i]["volume"] <= 3.0 * avg_vol:
                    continue
                # 收紅K或長下影線
                is_red = raw_history[i]["close"] > raw_history[i]["open"]
                body = abs(raw_history[i]["close"] - raw_history[i]["open"])
                lower_shadow = min(raw_history[i]["open"], raw_history[i]["close"]) - raw_history[i]["low"]
                is_long_lower_shadow = lower_shadow > 2.0 * body if body > 0 else lower_shadow > 0.01 * raw_history[i]["close"]
                if not (is_red or is_long_lower_shadow):
                    continue
                # 後續 3 天量縮不破底
                confirmed = True
                for j in range(i + 1, i + 4):
                    if raw_history[j]["low"] < raw_history[i]["low"]:
                        confirmed = False
                        break
                    if raw_history[j]["volume"] >= raw_history[i]["volume"]:
                        confirmed = False
                        break
                if not confirmed:
                    continue
                # KD 黃金交叉
                kd_cross = False
                for j in range(i, min(i + 4, n)):
                    if k_vals[j-1] <= d_vals[j-1] and k_vals[j] > d_vals[j]:
                        kd_cross = True
                        break
                if kd_cross:
                    bottom_signal = "底部換手訊號"
                    break
                    
            # 3. Check top_reversal_signal
            found_top = False
            for i in range(n-3, n):
                past_20 = raw_history[i-20:i]
                highest_close = max(x["close"] for x in past_20)
                highest_high = max(x["high"] for x in past_20)
                if raw_history[i]["close"] >= highest_close or raw_history[i]["high"] >= highest_high:
                    avg_vol = sum(x["volume"] for x in past_20) / 20.0
                    if raw_history[i]["volume"] > 2.5 * avg_vol:
                        if raw_history[i]["open"] - raw_history[i]["close"] > 0.02 * raw_history[i]["close"]:
                            top_reversal_signal = "高點防守訊號"
                            found_top = True
                            break
                            
            if not found_top and n >= 65:
                def get_ma(idx, period):
                    vals = [x["close"] for x in raw_history[idx - period + 1 : idx + 1]]
                    return sum(vals) / period
                ma5_prev = get_ma(n-6, 5)
                ma20_prev = get_ma(n-6, 20)
                ma60_prev = get_ma(n-6, 60)
                if ma5_prev > ma20_prev > ma60_prev:
                    ma20_curr = get_ma(n-1, 20)
                    ma5_curr = get_ma(n-1, 5)
                    if current_close < ma20_curr or ma5_curr < ma20_curr:
                        top_reversal_signal = "高點防守訊號"

        objective_findings = []
        if ma5 > ma20 > ma60:
            objective_findings.append("短期、中期與長期均線 (5MA>20MA>60MA) 呈現多頭排列狀態。")
        elif ma5 < ma20 < ma60:
            objective_findings.append("各級均線反轉，目前呈現空頭排列。")
        else:
            objective_findings.append("各級均線目前處於糾結且方向不明朗之盤整階段。")
            
        if current_close >= ma5:
            objective_findings.append("當前收盤價位於 5 日均線之上，動能指標偏向強勢。")
        else:
            objective_findings.append("當前收盤價已失守 5 日短天期均線。")
            
        if bottom_signal == "底部換手訊號":
            objective_findings.append("符合底部換手特徵：大跌後爆量收紅K/下影線，後續量縮不破底且KD黃金交叉。")
        if top_reversal_signal == "高點防守訊號":
            objective_findings.append("符合高點防守特徵：出現創高爆量長黑K或原強勢均線多頭排列股轉弱。")
            
        report = {
            "agent_name": "Technical Agent",
            "metrics_extracted": ["close_price", "ma5", "ma20", "ma60"],
            "objective_findings": objective_findings,
            "summary": f"技術面型態判定完成（目前收盤價為 {current_close}）。報告僅記錄當前量價與均線特徵，不含未來走勢預估。",
            "bottom_signal": bottom_signal,
            "top_reversal_signal": top_reversal_signal
        }
        return report

    def close(self):
        self.is_active = False
