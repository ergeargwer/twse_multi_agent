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
SIGNAL_NONE = "無明顯訊號"


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


def evaluate_risks(df: pd.DataFrame, vwap_dev_threshold: float = 1.05) -> pd.DataFrame:
    """依序標記高追價與低殺出；同一根 K 線兩者互斥，高追價優先。"""
    df = df.copy()
    if df.empty:
        return df

    df["Risk_Type"] = pd.Series([None] * len(df), dtype=object)
    df["Risk_Reason"] = ""

    for i in range(1, len(df)):
        close = df.loc[i, "Close"]
        prev_close = df.loc[i - 1, "Close"]
        vol = df.loc[i, "Volume"]
        prev_vol = df.loc[i - 1, "Volume"]
        vwap = df.loc[i, "VWAP"]
        ma20 = df.loc[i, "MA20"]
        vol_ma = df.loc[i, "Volume_MA20"]
        res = df.loc[i, "Resistance"]
        sup = df.loc[i, "Support"]
        tr = df.loc[i, "TR"]
        atr = df.loc[i, "ATR"]
        low = df.loc[i, "Low"]

        chase_reasons: List[str] = []
        if pd.notna(vwap) and vwap > 0 and close > (vwap * vwap_dev_threshold):
            chase_reasons.append(f"價格大幅偏離VWAP(>{(vwap_dev_threshold - 1) * 100:.1f}%)")
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
            df.loc[i, "Risk_Type"] = "High Chase"
            df.loc[i, "Risk_Reason"] = "; ".join(chase_reasons)
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
            df.loc[i, "Risk_Type"] = "Low Sell"
            df.loc[i, "Risk_Reason"] = "; ".join(sell_reasons)

    return df


def _format_date(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return str(value)
    return ts.strftime("%Y-%m-%d")


def run_behavior_risk(
    raw_history: List[Dict[str, Any]],
    vwap_dev_threshold_pct: float = 5.0,
    warmup_bars: int = 20,
) -> Dict[str, Any]:
    """從 raw_history 算出指標、風險標記與摘要。"""
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
        "vwap_dev_threshold_pct": float(vwap_dev_threshold_pct),
    }

    df = history_to_ohlcv(raw_history)
    if df.empty:
        return empty

    threshold = 1.0 + (float(vwap_dev_threshold_pct) / 100.0)
    df = calculate_indicators(df)
    df = evaluate_risks(df, vwap_dev_threshold=threshold)
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

    high_chase_count = int((view["Risk_Type"] == "High Chase").sum())
    low_sell_count = int((view["Risk_Type"] == "Low Sell").sum())
    latest_type: Optional[str] = None
    latest_reason = ""
    if not recent.empty:
        latest_type = recent.iloc[-1]["Risk_Type"]
        latest_reason = str(recent.iloc[-1]["Risk_Reason"] or "")

    if latest_type == "High Chase":
        signal = SIGNAL_HIGH_CHASE
    elif latest_type == "Low Sell":
        signal = SIGNAL_LOW_SELL
    else:
        signal = SIGNAL_NONE

    findings: List[str] = []
    if latest_type == "High Chase":
        findings.append(f"最近一筆行為標記為高追價風險：{latest_reason}")
    elif latest_type == "Low Sell":
        findings.append(f"最近一筆行為標記為低殺出風險：{latest_reason}")
    else:
        findings.append("暖身期之後未偵測到顯著的高追價或低殺出行為標記。")

    findings.append(
        f"分析區間內高追價 {high_chase_count} 筆、低殺出 {low_sell_count} 筆"
        f"（VWAP 乖離閾值 {vwap_dev_threshold_pct:.1f}%）。"
    )
    last_close = float(view.iloc[-1]["Close"]) if not view.empty else None
    last_vwap = float(view.iloc[-1]["VWAP"]) if not view.empty and pd.notna(view.iloc[-1]["VWAP"]) else None
    if last_close is not None and last_vwap:
        deviation_pct = (last_close / last_vwap - 1.0) * 100.0
        findings.append(f"最新收盤相對 20 期 VWAP 乖離約 {deviation_pct:+.2f}%。")

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
        "vwap_dev_threshold_pct": float(vwap_dev_threshold_pct),
    }
