# -*- coding: utf-8 -*-
"""股價行為風險：VWAP 乖離、量價背離、支撐假跌破等客觀標記。

邏輯移植自 stock_risk_alert，改吃 Shared Context 的日線 raw_history，
不另打 FinMind。輸出僅為行為標記，不含買賣建議或主力判斷。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

SIGNAL_HIGH_CHASE = "高追價風險"
SIGNAL_LOW_SELL = "低殺出風險"
SIGNAL_OVERSOLD = "月線負乖離型態"
SIGNAL_EXTREME_OVERSOLD = "月線極端負乖離型態"
SIGNAL_NONE = "無明顯訊號"

RISK_HIGH_CHASE = "High Chase"
RISK_LOW_SELL = "Low Sell"
RISK_OVERSOLD = "Oversold"
RISK_EXTREME_OVERSOLD = "Extreme Oversold"


def history_to_ohlcv(raw_history: List[Dict[str, Any]]) -> pd.DataFrame:
    """將 ingestion 的 raw_history 轉成統一欄位的 OHLCV DataFrame。"""
    columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    if not raw_history:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(raw_history)
    df = df.rename(columns={
        "date": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    })
    missing = [col for col in columns if col not in df.columns]
    if missing:
        return pd.DataFrame(columns=columns)

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date").reset_index(drop=True)
    return df[columns]


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """計算滾動 20 期 VWAP、MA20、支撐壓力與 ATR。"""
    df = df.copy()
    if df.empty:
        return df

    df["Typical_Price"] = (df["High"] + df["Low"] + df["Close"]) / 3
    df["Volume_TP"] = df["Typical_Price"] * df["Volume"]
    vol_sum = df["Volume"].rolling(window=20, min_periods=1).sum().replace(0, np.nan)
    df["VWAP"] = df["Volume_TP"].rolling(window=20, min_periods=1).sum() / vol_sum
    df["MA20"] = df["Close"].rolling(window=20, min_periods=1).mean()
    df["MA20_Dev_Pct"] = (df["Close"] / df["MA20"] - 1.0) * 100.0
    df.loc[df["MA20"].isna() | (df["MA20"] <= 0), "MA20_Dev_Pct"] = None
    df["Volume_MA20"] = df["Volume"].rolling(window=20, min_periods=1).mean()
    df["Support"] = df["Low"].rolling(window=20, min_periods=1).min().shift(1)
    df["Resistance"] = df["High"].rolling(window=20, min_periods=1).max().shift(1)

    df["Prev_Close"] = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - df["Prev_Close"]).abs()
    tr3 = (df["Low"] - df["Prev_Close"]).abs()
    df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = df["TR"].rolling(window=14, min_periods=1).mean()

    df["Support"] = df["Support"].fillna(df["Low"])
    df["Resistance"] = df["Resistance"].fillna(df["High"])
    df["Prev_Close"] = df["Prev_Close"].fillna(df["Close"])
    df["ATR"] = df["ATR"].fillna(df["TR"])
    return df


def _atr_ready(index: int) -> bool:
    return index > 15


def _load_ma20_thresholds(overbought_pct, oversold_pct, extreme_pct):
    from src.core.rule_config import get_agent_rules
    rules = get_agent_rules("behavior_risk_agent")
    if overbought_pct is None:
        overbought_pct = rules["ma20_overbought_dev_pct"]
    if oversold_pct is None:
        oversold_pct = rules["ma20_oversold_dev_pct"]
    if extreme_pct is None:
        extreme_pct = rules["ma20_extreme_oversold_dev_pct"]
    return float(overbought_pct), float(oversold_pct), float(extreme_pct)


def evaluate_risks(
    df: pd.DataFrame,
    ma20_overbought_pct: float = None,
    ma20_oversold_pct: float = None,
    ma20_extreme_oversold_pct: float = None,
) -> pd.DataFrame:
    """標記月線乖離型態、高追價與低殺出；同一根 K 線只保留一種標記。"""
    df = df.copy()
    if df.empty:
        return df

    overbought_pct, oversold_pct, extreme_pct = _load_ma20_thresholds(
        ma20_overbought_pct, ma20_oversold_pct, ma20_extreme_oversold_pct
    )

    df["Risk_Type"] = pd.Series([None] * len(df), dtype=object)
    df["Risk_Reason"] = ""

    for i in range(1, len(df)):
        close = df.loc[i, "Close"]
        prev_close = df.loc[i - 1, "Close"]
        vol = df.loc[i, "Volume"]
        prev_vol = df.loc[i - 1, "Volume"]
        ma20 = df.loc[i, "MA20"]
        ma20_dev = df.loc[i, "MA20_Dev_Pct"] if "MA20_Dev_Pct" in df.columns else None
        if ma20_dev is None or (isinstance(ma20_dev, float) and pd.isna(ma20_dev)):
            if pd.notna(ma20) and ma20 > 0:
                ma20_dev = (close / ma20 - 1.0) * 100.0
            else:
                ma20_dev = None
        vol_ma = df.loc[i, "Volume_MA20"]
        res = df.loc[i, "Resistance"]
        sup = df.loc[i, "Support"]
        tr = df.loc[i, "TR"]
        atr = df.loc[i, "ATR"]
        low = df.loc[i, "Low"]

        if ma20_dev is not None and ma20_dev <= extreme_pct:
            df.loc[i, "Risk_Type"] = RISK_EXTREME_OVERSOLD
            df.loc[i, "Risk_Reason"] = (
                f"當前收盤與月線乖離達 {ma20_dev:.1f}%，歷史上此乖離幅度多發生於大盤跌深階段，"
                "屬於統計上的極端型態，僅供風險觀察參考，不代表後續走勢必然反轉。"
            )
            continue

        chase_reasons: List[str] = []
        if ma20_dev is not None and ma20_dev >= overbought_pct:
            chase_reasons.append(f"收盤相對月線(MA20)正乖離達 {ma20_dev:.1f}%（門檻 {overbought_pct:.1f}%）")
        if pd.notna(res) and close >= res and pd.notna(atr) and tr < (atr * 0.8) and _atr_ready(i):
            chase_reasons.append("創新高但波動急縮，動能可能衰退")
        if (
            close > prev_close
            and pd.notna(ma20)
            and close > ma20
            and vol < (prev_vol * 0.7)
            and pd.notna(vol_ma)
            and vol_ma > 0
            and prev_vol > vol_ma
        ):
            chase_reasons.append("價格上漲但成交量顯著萎縮")

        if chase_reasons:
            df.loc[i, "Risk_Type"] = RISK_HIGH_CHASE
            df.loc[i, "Risk_Reason"] = "; ".join(chase_reasons)
            continue

        if ma20_dev is not None and ma20_dev <= oversold_pct:
            df.loc[i, "Risk_Type"] = RISK_OVERSOLD
            df.loc[i, "Risk_Reason"] = (
                f"收盤相對月線(MA20)負乖離達 {ma20_dev:.1f}%，屬統計上的超跌型態觀察，不含走勢預測。"
            )
            continue

        sell_reasons: List[str] = []
        if pd.notna(sup) and close < sup and pd.notna(vol_ma) and vol < (vol_ma * 0.8):
            sell_reasons.append("跌破近期支撐區，但市場未見放量恐慌")
        if pd.notna(sup) and low < sup and close > sup and i > 2:
            sell_reasons.append("盤中跌破支撐後迅速收回，可能為假跌破洗盤")
        if (
            pd.notna(sup)
            and sup > 0
            and abs(close - sup) / sup < 0.02
            and pd.notna(atr)
            and tr < (atr * 0.7)
            and _atr_ready(i)
        ):
            sell_reasons.append("價格在支撐區反覆測試且波動極小")

        if sell_reasons:
            df.loc[i, "Risk_Type"] = RISK_LOW_SELL
            df.loc[i, "Risk_Reason"] = "; ".join(sell_reasons)

    return df


def _format_date(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return str(value)
    return ts.strftime("%Y-%m-%d")


def run_behavior_risk(
    raw_history: List[Dict[str, Any]],
    ma20_dev_threshold_pct: float = None,
    warmup_bars: int = 20,
) -> Dict[str, Any]:
    """從 raw_history 算出月線乖離與行為風險標記。"""
    overbought_pct, oversold_pct, extreme_pct = _load_ma20_thresholds(
        ma20_dev_threshold_pct, None, None
    )
    empty = {
        "frame": pd.DataFrame(),
        "recent_events": [],
        "latest_risk_type": None,
        "latest_risk_reason": "",
        "signal": SIGNAL_NONE,
        "findings": ["價量歷史不足，無法計算行為風險標記。"],
        "summary": "行為風險未產出（缺少足夠的日線價量）。本標記僅描述已發生的量價乖離，不含走勢預測。",
        "bars_analyzed": 0,
        "high_chase_count": 0,
        "low_sell_count": 0,
        "oversold_count": 0,
        "extreme_oversold_count": 0,
        "ma20_dev_threshold_pct": overbought_pct,
    }

    df = history_to_ohlcv(raw_history)
    if df.empty:
        return empty

    df = calculate_indicators(df)
    df = evaluate_risks(
        df,
        ma20_overbought_pct=overbought_pct,
        ma20_oversold_pct=oversold_pct,
        ma20_extreme_oversold_pct=extreme_pct,
    )
    view = df.iloc[warmup_bars:].reset_index(drop=True) if len(df) > warmup_bars else df.reset_index(drop=True)

    flagged = view[view["Risk_Type"].notna()]
    recent = flagged.tail(10)
    recent_events = []
    for _, row in recent.iterrows():
        recent_events.append({
            "date": _format_date(row["Date"]),
            "risk_type": row["Risk_Type"],
            "risk_reason": row["Risk_Reason"],
            "close": float(row["Close"]),
        })

    high_chase_count = int((view["Risk_Type"] == RISK_HIGH_CHASE).sum())
    low_sell_count = int((view["Risk_Type"] == RISK_LOW_SELL).sum())
    oversold_count = int((view["Risk_Type"] == RISK_OVERSOLD).sum())
    extreme_count = int((view["Risk_Type"] == RISK_EXTREME_OVERSOLD).sum())
    latest_type: Optional[str] = None
    latest_reason = ""
    if not recent.empty:
        latest_type = recent.iloc[-1]["Risk_Type"]
        latest_reason = str(recent.iloc[-1]["Risk_Reason"] or "")

    signal_map = {
        RISK_HIGH_CHASE: SIGNAL_HIGH_CHASE,
        RISK_LOW_SELL: SIGNAL_LOW_SELL,
        RISK_OVERSOLD: SIGNAL_OVERSOLD,
        RISK_EXTREME_OVERSOLD: SIGNAL_EXTREME_OVERSOLD,
    }
    signal = signal_map.get(latest_type, SIGNAL_NONE)

    findings: List[str] = []
    if latest_type == RISK_EXTREME_OVERSOLD:
        findings.append(latest_reason)
    elif latest_type == RISK_OVERSOLD:
        findings.append(f"最近一筆行為標記為月線負乖離型態：{latest_reason}")
    elif latest_type == RISK_HIGH_CHASE:
        findings.append(f"最近一筆行為標記為高追價風險：{latest_reason}")
    elif latest_type == RISK_LOW_SELL:
        findings.append(f"最近一筆行為標記為低殺出風險：{latest_reason}")
    else:
        findings.append("暖身期之後未偵測到顯著的月線乖離或量價背離標記。")

    findings.append(
        f"分析區間內高追價 {high_chase_count} 筆、低殺出 {low_sell_count} 筆、"
        f"月線負乖離 {oversold_count} 筆、極端負乖離 {extreme_count} 筆"
        f"（月線正乖離門檻 {overbought_pct:.1f}%）。"
    )
    if not view.empty and pd.notna(view.iloc[-1].get("MA20_Dev_Pct")):
        findings.append(f"最新收盤相對月線(MA20)乖離約 {float(view.iloc[-1]['MA20_Dev_Pct']):+.2f}%。")

    summary = (
        f"行為風險標記完成（訊號：{signal}）。"
        "本報告只記錄已發生的量價極端乖離與背離，嚴禁解讀為買賣點或主力動向。"
    )

    return {
        "frame": view,
        "recent_events": recent_events,
        "latest_risk_type": latest_type,
        "latest_risk_reason": latest_reason,
        "signal": signal,
        "findings": findings,
        "summary": summary,
        "bars_analyzed": int(len(view)),
        "high_chase_count": high_chase_count,
        "low_sell_count": low_sell_count,
        "oversold_count": oversold_count,
        "extreme_oversold_count": extreme_count,
        "ma20_dev_threshold_pct": overbought_pct,
    }
