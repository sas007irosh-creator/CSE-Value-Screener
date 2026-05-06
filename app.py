import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURATION ---
# The screener automatically scans this "Master List" of high-liquidity CSE stocks
TICKERS = [
    "SAMP.N0000", "DFCC.N0000", "COMB.N0000", "HNB.N0000", "JKH.N0000",
    "HAYL.N0000", "LOLC.N0000", "SUN.N0000", "DIAL.N0000", "ACL.N0000",
    "TILE.N0000", "LANK.N0000", "RICH.N0000", "VONE.N0000", "NEST.N0000"
]

st.set_page_config(page_title="CSE Auto-Alpha", layout="wide")

st.title("🏆 Best Value & Growth: Daily Top Picks")
st.markdown("Analysis based on live data from **Yahoo Finance** and **CSE Market Metrics**.")

@st.cache_data(ttl=3600) # Refreshes data every hour automatically
def auto_scan():
    scored_results = []
    for t in TICKERS:
        try:
            df = yf.download(t, period="2y", interval="1d", progress=False)
            if df.empty or len(df) < 200: continue
            
            # Technicals
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['SMA200'] = df['Close'].rolling(200).mean()
            
            curr_close = df['Close'].iloc[-1]
            s50 = df['SMA50'].iloc[-1]
            s200 = df['SMA200'].iloc[-1]
            
            # Fundamental Data
            ticker_obj = yf.Ticker(t)
            info = ticker_obj.info
            pe = info.get('trailingPE', 20) # Default to 20 if missing
            pb = info.get('priceToBook', 2)   # Default to 2 if missing
            
            # SCORING ALGORITHM
            # 1. Value Score (Lower is better, max 40 pts)
            value_score = max(0, 40 - (pe * 1.5) - (pb * 5))
            
            # 2. Momentum Score (30-day growth, max 30 pts)
            month_ago_price = df['Close'].iloc[-22]
            growth_pct = (curr_close - month_ago_price) / month_ago_price
            momentum_score = min(30, growth_pct * 100)
            
            # 3. Trend Score (Golden Cross/Bullish, max 30 pts)
            trend_score = 0
            status = "Neutral"
            if s50 > s200:
                trend_score = 30
                status = "Bullish"
                if (df['SMA50'].iloc[-2] <= df['SMA200'].iloc[-2]):
                    status = "🔥 GOLDEN CROSS"
                    trend_score = 40 # Bonus for fresh breakout
            elif (s200 - s50) / s200 < 0.02:
                status = "⚡ PRE-CROSS"
                trend_score = 20
                
            total_score = value_score + momentum_score + trend_score
            
            scored_results.append({
                "Ticker": t,
                "Price": round(curr_close, 2),
                "P/E": round(pe, 2),
                "P/B": round(pb, 2),
                "Growth (30d)": f"{round(growth_pct*100, 2)}%",
                "Signal": status,
                "Alpha Score": round(total_score, 1),
                "Data": df
            })
        except:
            continue
    return scored_results

# --- AUTO-EXECUTION ---
with st.spinner("Analyzing market for best opportunities..."):
    all_picks = auto_scan()

if all_picks:
    # Sort by the highest Alpha Score automatically
    ranked_df = pd.DataFrame(all_picks).sort_values(by="Alpha Score", ascending=False)
    
    top_share = ranked_df.iloc[0]
    
    # Hero Section for the #1 Pick
    col1, col2 = st.columns([1, 2])
    with col1:
        st.success(f"### 🥇 Top Pick: {top_share['Ticker']}")
        st.metric("Alpha Score", top_share['Alpha Score'])
        st.write(f"**Current Price:** LKR {top_share['Price']}")
        st.write(f"**Valuation:** P/E {top_share['P/E']} | P/B {top_share['P/B']}")
        st.write(f"**Status:** {top_share['Signal']}")
        
    with col2:
        # Automatic Chart for Top Pick
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=top_share['Data'].index, y=top_share['Data']['Close'], name="Price"))
        fig.add_trace(go.Scatter(x=top_share['Data'].index, y=top_share['Data']['SMA50'], name="50 SMA"))
        fig.add_trace(go.Scatter(x=top_share['Data'].index, y=top_share['Data']['SMA200'], name="200 SMA"))
        fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📋 Full Market Ranking")
    st.dataframe(ranked_df.drop(columns=['Data']), use_container_width=True)
else:
    st.error("Market data currently unavailable. Please check back during CSE trading hours.")
