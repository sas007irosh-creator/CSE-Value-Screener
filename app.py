import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime

# Updated Tickers for 2026 - Using both formats to be safe
TICKER_LIST = ["SAMP", "DFCC", "COMB", "HNB", "JKH", "HAYL", "LOLC", "SUN", "DIAL", "ACL", "MEL"]

st.set_page_config(page_title="CSE Smart Money Screener", layout="wide")
st.title("🐋 CSE Live Technical Screener")

@st.cache_data(ttl=600) # Refresh data every 10 mins during market hours
def get_data(symbol):
    # Try .CM (Yahoo standard) then .N0000
    for suffix in [".CM", ".N0000"]:
        ticker = f"{symbol}{suffix}"
        try:
            # Using a custom session to bypass basic bot blocks
            data = yf.download(ticker, period="1y", interval="1d", progress=False, timeout=10)
            if not data.empty and len(data) > 50:
                return data, ticker
        except:
            continue
    return None, None

def perform_ta(df):
    # --- TECHNICAL INDICATORS ---
    # 1. RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 2. MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # 3. Stochastic (5,3,3 as requested previously)
    low_min = df['Low'].rolling(window=5).min()
    high_max = df['High'].rolling(window=5).max()
    df['%K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min))
    df['%D'] = df['%K'].rolling(window=3).mean()
    
    return df

# --- EXECUTION ---
results = []
status_placeholder = st.empty()

for sym in TICKER_LIST:
    status_placeholder.text(f"Scanning {sym}...")
    df, full_ticker = get_data(sym)
    
    if df is not None:
        df = perform_ta(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        score = 0
        signals = []
        
        # LOGIC 1: MACD Bullish Cross (The "Trend Starter")
        if latest['MACD'] > latest['Signal'] and prev['MACD'] <= prev['Signal']:
            score += 40
            signals.append("MACD Cross")
            
        # LOGIC 2: Stochastic Oversold Reversal
        if latest['%K'] > latest['%D'] and latest['%K'] < 30:
            score += 30
            signals.append("Stoch Recovery")
            
        # LOGIC 3: RSI Strength
        if 45 < latest['RSI'] < 65:
            score += 20
            
        if score > 20: # Only show stocks with a positive trend
            results.append({
                "Stock": sym,
                "Price": round(float(latest['Close']), 2),
                "RSI": round(float(latest['RSI']), 1),
                "Score": score,
                "Signal": ", ".join(signals) if signals else "Neutral-Positive"
            })

status_placeholder.empty()

# --- DISPLAY ---
if results:
    ranked = pd.DataFrame(results).sort_values(by="Score", ascending=False)
    
    # Highlight the Top Pick
    top = ranked.iloc[0]
    st.success(f"### 🚀 Best Opportunity: {top['Stock']}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"Rs. {top['Price']}")
    c2.metric("Technical Score", f"{top['Score']}/100")
    c3.write(f"**Primary Indicators:** {top['Signal']}")
    
    st.divider()
    st.subheader("📊 Market Rankings")
    st.table(ranked)
else:
    st.warning("Scanning complete. No strong 'Buy' signals found at this moment, or market connectivity is limited.")
