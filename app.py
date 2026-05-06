import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- CONFIGURATION ---
# Yahoo Finance uses .CM for Colombo Stock Exchange
TICKERS = [
    "SAMP.CM", "DFCC.CM", "COMB.CM", "HNB.CM", "JKH.CM",
    "HAYL.CM", "LOLC.CM", "SUN.CM", "DIAL.CM", "ACL.CM"
]

st.set_page_config(page_title="CSE Smart Money Screener", layout="wide")
st.title("🐋 CSE Smart Money & Breakout Screener")
st.markdown("Scanning for institutional accumulation and structural breakouts using **yfinance** and **shares.lk**.")

# --- ROBUST DATA FETCHER ---
def fetch_shares_lk_price(symbol):
    """Fallback web scraper if Yahoo Finance is down after hours."""
    try:
        # Clean the ticker (e.g., SAMP.CM -> SAMP)
        clean_symbol = symbol.split('.')[0]
        url = f"https://www.shares.lk/stock/{clean_symbol}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Look for the price element (this assumes standard shares.lk HTML structure)
            price_div = soup.find('div', class_='price-value') # Adjust class name if shares.lk updates their site
            if price_div:
                return float(price_div.text.replace(',', '').strip())
    except Exception:
        return None
    return None

@st.cache_data(ttl=3600)
def auto_scan():
    scored_results = []
    
    for t in TICKERS:
        try:
            # 1. Try to fetch historical data for Technical Analysis
            df = yf.download(t, period="2y", interval="1d", progress=False)
            
            # If Yahoo Finance is completely empty, skip (we need history for TA)
            if df.empty or len(df) < 100:
                continue
            
            # 2. Check if the last price is stale/zero (Yahoo Finance after-hours bug)
            curr_close = df['Close'].iloc[-1]
            if pd.isna(curr_close) or curr_close == 0:
                # Fallback to scraping shares.lk for the current price
                live_price = fetch_shares_lk_price(t)
                if live_price:
                    curr_close = live_price
                    # Update the dataframe with the scraped price
                    df.loc[df.index[-1], 'Close'] = live_price
                else:
                    continue # Skip if we can't find a valid price anywhere
            
            # --- ADVANCED TECHNICAL ANALYSIS (Pure Pandas) ---
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['SMA200'] = df['Close'].rolling(200).mean()
            
            # RSI (14 Day)
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # MACD
            df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
            df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = df['EMA12'] - df['EMA26']
            df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            
            # Stochastic Oscillator
            low14 = df['Low'].rolling(14).min()
            high14 = df['High'].rolling(14).max()
            df['Stoch_K'] = 100 * ((df['Close'] - low14) / (high14 - low14))
            df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
            
            # Institutional Structure
            df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
            df['High_50'] = df['High'].rolling(50).max().shift(1)
            
            # Extract latest values safely
            curr_vol = df['Volume'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            macd = df['MACD'].iloc[-1]
            macd_sig = df['MACD_Signal'].iloc[-1]
            stoch_k = df['Stoch_K'].iloc[-1]
            stoch_d = df['Stoch_D'].iloc[-1]
            
            # --- SCORING ALGORITHM ---
            score = 0
            signals = []
            
            # Major Breakout
            if (curr_close > df['High_50'].iloc[-1]) and (curr_vol > df['Vol_SMA20'].iloc[-1] * 1.5):
                score += 50
                signals.append("🔥 MAJOR BREAKOUT")
                
            # Early MACD Cross (Below Zero)
            if (macd > macd_sig) and (df['MACD'].iloc[-2] <= df['MACD_Signal'].iloc[-2]) and (macd < 0):
                score += 30
                signals.append("📈 MACD Bottom Cross")
                
            # Stochastic Oversold Reversal
            if (stoch_k > stoch_d) and (stoch_k < 30) and (df['Stoch_K'].iloc[-2] <= df['Stoch_D'].iloc[-2]):
                score += 25
                signals.append("⚡ Stoch Oversold Bounce")
                
            # Golden Cross / Pre-Cross
            s50, s200 = df['SMA50'].iloc[-1], df['SMA200'].iloc[-1]
            if s50 > s200:
                score += 20
            elif s200 > 0 and ((s200 - s50) / s200 < 0.02):
                score += 15
                signals.append("⏳ Pre-Cross Alert")
            
            if score > 0:
                clean_name = t.replace('.CM', '')
                scored_results.append({
                    "Ticker": clean_name,
                    "Price": round(curr_close, 2),
                    "RSI": round(rsi, 1),
                    "MACD": "Bullish" if macd > macd_sig else "Bearish",
                    "Score": score,
                    "Signals": " | ".join(signals) if signals else "Accumulating",
                    "Data": df
                })
        except Exception as e:
            continue # Silently skip failing tickers
            
    return scored_results

# --- UI EXECUTION ---
with st.spinner("Analyzing structural market shifts..."):
    all_picks = auto_scan()

if all_picks:
    ranked_df = pd.DataFrame(all_picks).sort_values(by="Score", ascending=False)
    top_share = ranked_df.iloc[0]
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.success(f"### 🥇 Top Pick: {top_share['Ticker']}")
        st.metric("Technical Score", top_share['Score'])
        st.write(f"**Price:** LKR {top_share['Price']}")
        st.write(f"**RSI (14):** {top_share['RSI']}")
        st.write(f"**MACD Status:** {top_share['MACD']}")
        st.info(f"**Catalysts:** {top_share['Signals']}")
        
    with col2:
        df_chart = top_share['Data'].tail(150)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Close'], name="Price", line=dict(color='#00ffcc')))
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA50'], name="50 SMA", line=dict(color='orange')))
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA200'], name="200 SMA", line=dict(color='cyan')))
        
        fig.update_layout(
            title=f"{top_share['Ticker']} Structural Analysis",
            template="plotly_dark", 
            height=350,
            margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📋 Full Technical Ranking")
    st.dataframe(ranked_df.drop(columns=['Data']), use_container_width=True)
else:
    st.error("No valid market data available. If the market is closed, check back during CSE hours.")
