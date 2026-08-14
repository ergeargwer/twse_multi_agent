# -*- coding: utf-8 -*-
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_risk_chart(df: pd.DataFrame, stock_id: str) -> go.Figure:
    """以 K 線標記高追價／低殺出，配色對齊儀表板海軍藍風格。"""
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_white",
            height=420,
            title=f"{stock_id} 尚無足夠價量可供行為風險圖",
        )
        return fig

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28],
        subplot_titles=(f"{stock_id} 股價行為風險標記", "成交量"),
    )

    fig.add_trace(
        go.Candlestick(
            x=df["Date"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="價格",
            increasing_line_color="#059669",
            decreasing_line_color="#dc2626",
        ),
        row=1,
        col=1,
    )

    if "VWAP" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["VWAP"],
                line=dict(color="#c33764", width=1.5, dash="dot"),
                name="VWAP (20期)",
            ),
            row=1,
            col=1,
        )

    if "MA20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["MA20"],
                line=dict(color="#1e3c72", width=1.5),
                name="MA (20期)",
            ),
            row=1,
            col=1,
        )

    if "Risk_Type" in df.columns:
        df_chase = df[df["Risk_Type"] == "High Chase"]
        df_sell = df[df["Risk_Type"] == "Low Sell"]
        if not df_chase.empty:
            fig.add_trace(
                go.Scatter(
                    x=df_chase["Date"],
                    y=df_chase["High"] * 1.01,
                    mode="markers",
                    marker=dict(symbol="triangle-down", color="#dc2626", size=12),
                    name="高追價風險",
                    text=df_chase["Risk_Reason"],
                    hovertemplate="<b>高追價風險</b><br>%{text}<br>價格: %{y:.2f}<extra></extra>",
                ),
                row=1,
                col=1,
            )
        if not df_sell.empty:
            fig.add_trace(
                go.Scatter(
                    x=df_sell["Date"],
                    y=df_sell["Low"] * 0.99,
                    mode="markers",
                    marker=dict(symbol="triangle-up", color="#059669", size=12),
                    name="低殺出風險",
                    text=df_sell["Risk_Reason"],
                    hovertemplate="<b>低殺出風險</b><br>%{text}<br>價格: %{y:.2f}<extra></extra>",
                ),
                row=1,
                col=1,
            )

    colors = [
        "#059669" if df.loc[i, "Close"] >= df.loc[i, "Open"] else "#dc2626"
        for i in range(len(df))
    ]
    fig.add_trace(
        go.Bar(x=df["Date"], y=df["Volume"], marker_color=colors, name="成交量"),
        row=2,
        col=1,
    )

    fig.update_layout(
        template="plotly_white",
        height=680,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1),
        margin=dict(t=70, b=40, l=50, r=20),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="價格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)
    return fig
