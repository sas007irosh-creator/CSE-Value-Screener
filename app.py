import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION: Best 10 + High Growth Watchlist ---
TICKERS = [
    "SAMP.CM", "SUN.CM", "DFCC.CM", "COMB.CM", "HNB.CM", 
    "JKH.CM", "HAYL.CM", "LOLC.CM", "ASIR.CM", "WIND.CM",
    "AGST.CM", "ASIY.CM", "LION.CM", "RICH.CM", "VONE.CM"
]

st.set_page_config(page_title="CSE Alpha 10 Screener", layout="wide")
st.title("📊 CSE Alpha 10: Technical & Performance Screener")
st.markdown("Automated scan of the best 10 shares based on structural breakouts and multi-timeframe performance.")

def fetch_live_fallback(symbol):
    """Scrapes shares.lk if yfinance data is stale after-hours."""
    try:
        clean = symbol.split('.')[0]
        url = f"https://www.shares.lk/stock/{clean}"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            p = soup.find('div', class_='price-value')
            return float(p.text.replace(',', '').strip()) if p else None
    except: return None

@st.cache_data(ttl=3600)
def deep_scan():
    results = []
    for t in TICKERS:
        try:
            df = yf.download(t, period="2y", interval="1d", progress=False)
            if df.empty or len(df) < 150: continue
            
            # --- FALLBACK PRICE PATCHING ---
            curr_close = df['Close'].iloc[-1]
            if pd.isna(curr_close) or curr_close == 0:
                live = fetch_live_fallback(t)
                if live: curr_close = live
                else: continue

            # --- PERFORMANCE FILTERS (%) ---
            df_c = df['Close']
            perf = {
                "Day": ((curr_close / df_c.iloc[-2]) - 1) * 100,
                "Week": ((curr_close / df_c.iloc[-5]) - 1) * 100,
                "Month": ((curr_close / df_c.iloc[-21]) - 1) * 100,
                "3Month": ((curr_close / df_c.iloc[-63]) - 1) * 100,
                "Year": ((curr_close / df_c.iloc[-252]) - 1) * 100
            }

            # --- TECHNICAL INDICATORS ---
            # 1. RSI (14)
            delta = df_c.diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            df['RSI'] = 100 - (100 / (1 + (gain/loss)))
            
            # 2. MACD (12, 26, 9)
            df['EMA12'] = df_c.ewm(span=12, adjust=False).mean()
            df['EMA26'] = df_c.ewm(span=26, adjust=False).mean()
            df['MACD'] = df['EMA12'] - df['EMA26']
            df['MACD_Sig'] = df['MACD'].ewm(span=9, adjust=False).mean()
            
            # 3. User's Stochastic (5, 3, 3)
            low5 = df['Low'].rolling(5).min()
            high5 = df['High'].rolling(5).max()
            df['Stoch_K'] = 100 * ((df_c - low5) / (high5 - low5))
            df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()

            # 4. Moving Averages
            df['SMA50'] = df_c.rolling(50).mean()
            df['SMA200'] = df_c.rolling(200).mean()

            # --- ALPHA SCORING LOGIC ---
            # Weighted Performance (40%) + Technical Structure (60%)
            perf_score = (perf['Week']*1 + perf['Month']*2 + perf['3Month']*3 + perf['Year']*4) / 10
            
            tech_score = 0
            signals = []
            
            # Trend: Price > 200 SMA (Long term bullish)
            if curr_close > df['SMA200'].iloc[-1]: tech_score += 20
            
            # Breakout: MACD Crossover
            if df['MACD'].iloc[-1] > df['MACD_Sig'].iloc[-1] and df['MACD'].iloc[-2] <= df['MACD_Sig'].iloc[-2]:
                tech_score += 30
                signals.append("🚀 MACD Cross")
            
            # Momentum: RSI rising from 40-50 (Early Trend)
            if 45 < df['RSI'].iloc[-1] < 65 and df['RSI'].iloc[-1] > df['RSI'].iloc[-2]:
                tech_score += 15
                signals.append("📈 RSI Strength")

            total_score = round(perf_score + tech_score, 2)

            results.append({
                "Ticker": t.split('.')[0],
                "Price": round(curr_close, 2),
                "Day %": round(perf['Day'], 2),
                "Week %": round(perf['Week'], 2),
                "Month %": round(perf['Month'], 2),
                "Year %": round(perf['Year'], 2),
                "RSI": round(df['RSI'].iloc[-1], 1),
                "Alpha Score": total_score,
                "Signals": " | ".join(signals) if signals else "Holding",
                "Data": df
            })
        except: continue
    return results

# --- RENDERING ---
with st.spinner("Calculating Performance & Technical Ranks..."):
    data = deep_scan()

if data:
    # Rank and filter the Best 10
    all_df = pd.DataFrame(data).sort_values(by="Alpha Score", ascending=False)
    top_10 = all_df.head(10)
    
    # 🥇 Top Performing Spotlight
    st.subheader("🏆 Current Market Leader")
    best = top_10.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ticker", best['Ticker'])
    c2.metric("Weekly Perf", f"{best['Week %']}%")
    c3.metric("Yearly Perf", f"{best['Year %']}%")
    c4.metric("Alpha Score", best['Alpha Score'])
    
    # Technical Chart for Top Pick
    df_plot = best['Data'].tail(120)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'], name="Price", line=dict(color='#00ffcc', width=2)))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['SMA50'], name="50 SMA", line=dict(color='orange', dash='dot')))
    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['SMA200'], name="200 SMA", line=dict(color='magenta')))
    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # 📋 The Best 10 Shares Table
    st.divider()
    st.subheader("🔥 Top 10 High Potential Shares")
    st.markdown("Ranked by cumulative performance and technical breakout probability.")
    
    # Formatting for the table
    display_cols = ["Ticker", "Price", "Day %", "Week %", "Month %", "Year %", "RSI", "Alpha Score", "Signals"]
    st.dataframe(top_10[display_cols].style.background_gradient(subset=['Alpha Score'], cmap='BuGn'), use_container_width=True)

else:
    st.warning("Scanning complete. No strong technical outliers found, or market data connectivity is currently limited.")
