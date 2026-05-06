import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURATION ---
# Common CSE Tickers (Voting Shares)
TICKERS = [
    "SAMP.N0000", "DFCC.N0000", "COMB.N0000", "HNB.N0000", "JKH.N0000",
    "HAYL.N0000", "LOLC.N0000", "SUN.N0000", "DIAL.N0000", "ACL.N0000",
    "TILE.N0000", "LANK.N0000", "RICH.N0000", "VONE.N0000"
]

st.set_page_config(page_title="CSE Value Screener", layout="wide")

# --- UI HEADER ---
st.title("📊 CSE Undervalued & Trend Screener")
st.markdown("""
This platform identifies **undervalued** shares with **bullish long-term trends**. 
It scans for the **Golden Cross** (50 SMA crossing above 200 SMA) and **Pre-Cross** signals.
""")

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filter Criteria")
pe_max = st.sidebar.slider("Maximum P/E Ratio", 1.0, 30.0, 12.0)
pb_max = st.sidebar.slider("Maximum P/B Ratio", 0.1, 5.0, 1.2)
st.sidebar.info("Low P/E and P/B ratios often indicate undervalued assets.")

# --- ANALYSIS ENGINE ---
def get_market_data(ticker):
    try:
        # Download 2 years of history for accurate 200-day SMA
        df = yf.download(ticker, period="2y", interval="1d", progress=False)
        if df.empty or len(df) < 200:
            return None
        
        # Technical Analysis
        df['SMA50'] = ta.sma(df['Close'], length=50)
        df['SMA200'] = ta.sma(df['Close'], length=200)
        
        # Signal Detection
        curr_50 = df['SMA50'].iloc[-1]
        curr_200 = df['SMA200'].iloc[-1]
        prev_50 = df['SMA50'].iloc[-2]
        prev_200 = df['SMA200'].iloc[-2]
        
        # Logic: Golden Cross
        is_golden_cross = (curr_50 > curr_200) and (prev_50 <= prev_200)
        
        # Logic: Pre-Cross (Narrowing gap within 2%)
        gap = (curr_200 - curr_50) / curr_200
        is_pre_cross = (curr_50 < curr_200) and (curr_50 > prev_50) and (gap < 0.02)
        
        # Bullish Trend (Long term)
        is_bullish = curr_50 > curr_200
        
        # Fundamentals from yfinance
        stock = yf.Ticker(ticker)
        info = stock.info
        pe = info.get('trailingPE', 0)
        pb = info.get('priceToBook', 0)
        
        return {
            "Ticker": ticker,
            "Price": round(df['Close'].iloc[-1], 2),
            "P/E": round(pe, 2),
            "P/B": round(pb, 2),
            "Signal": "🔥 Golden Cross" if is_golden_cross else ("⚡ Pre-Cross" if is_pre_cross else "Neutral"),
            "Trend": "Bullish" if is_bullish else "Bearish",
            "Data": df
        }
    except Exception:
        return None

# --- EXECUTION ---
if st.button("🚀 Start Market Analysis"):
    results = []
    progress_bar = st.progress(0)
    
    for i, t in enumerate(TICKERS):
        data = get_market_data(t)
        if data:
            # Apply Fundamental Filters
            if (data['P/E'] <= pe_max or data['P/E'] == 0) and (data['P/B'] <= pb_max or data['P/B'] == 0):
                results.append(data)
        progress_bar.progress((i + 1) / len(TICKERS))

    if results:
        df_display = pd.DataFrame(results).drop(columns=['Data'])
        st.subheader("Market Opportunities")
        st.dataframe(df_display, use_container_width=True)
        
        # Visualization Section
        st.divider()
        selected = st.selectbox("Select a share to view the chart:", df_display['Ticker'])
        chart_data = next(item for item in results if item["Ticker"] == selected)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=chart_data['Data'].index, y=chart_data['Data']['Close'], name="Price", line=dict(color='white')))
        fig.add_trace(go.Scatter(x=chart_data['Data'].index, y=chart_data['Data']['SMA50'], name="50 SMA", line=dict(color='orange')))
        fig.add_trace(go.Scatter(x=chart_data['Data'].index, y=chart_data['Data']['SMA200'], name="200 SMA", line=dict(color='cyan')))
        fig.update_layout(title=f"{selected} Trend Analysis", template="plotly_dark", height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No shares found matching these criteria. Try increasing the P/E or P/B limits.")
