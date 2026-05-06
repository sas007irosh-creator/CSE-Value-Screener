import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURATION ---
TICKERS = [
    "SAMP.N0000", "DFCC.N0000", "COMB.N0000", "HNB.N0000", "JKH.N0000",
    "HAYL.N0000", "LOLC.N0000", "SUN.N0000", "DIAL.N0000", "ACL.N0000",
    "TILE.N0000", "LANK.N0000", "RICH.N0000", "VONE.N0000", "MEL.N0000"
]

st.set_page_config(page_title="CSE Smart Money Screener", layout="wide")
st.title("🐋 CSE Smart Money & Breakout Screener")
st.markdown("Scanning for institutional accumulation, major structural breakouts, and early momentum shifts.")

@st.cache_data(ttl=3600) 
def auto_scan():
    scored_results = []
    for t in TICKERS:
        try:
            # Fetch data (works seamlessly after hours by pulling the last available closed session)
            df = yf.download(t, period="2y", interval="1d", progress=False)
            if df.empty or len(df) < 200: continue
            
            # --- ADVANCED TECHNICAL ANALYSIS (Pure Pandas) ---
            
            # 1. Moving Averages
            df['SMA50'] = df['Close'].rolling(50).mean()
            df['SMA200'] = df['Close'].rolling(200).mean()
            
            # 2. RSI (Relative Strength Index) - 14 Day
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # 3. MACD (Moving Average Convergence Divergence)
            df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
            df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = df['EMA12'] - df['EMA26']
            df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            
            # 4. Stochastic Oscillator (14, 3, 3)
            low14 = df['Low'].rolling(14).min()
            high14 = df['High'].rolling(14).max()
            df['Stoch_K'] = 100 * ((df['Close'] - low14) / (high14 - low14))
            df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
            
            # 5. Smart Money / Major Breakout Detection (Institutional Volume + Structure)
            df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
            df['High_50'] = df['High'].rolling(50).max().shift(1) # Previous 50-day resistance
            
            # Extract latest values
            curr_close = df['Close'].iloc[-1]
            curr_vol = df['Volume'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            macd = df['MACD'].iloc[-1]
            macd_sig = df['MACD_Signal'].iloc[-1]
            stoch_k = df['Stoch_K'].iloc[-1]
            stoch_d = df['Stoch_D'].iloc[-1]
            
            # --- EARLY DETECTION SCORING ALGORITHM ---
            score = 0
            signals = []
            
            # Filter noise: Ignore minor reversals, look for major structural breakouts
            is_major_breakout = (curr_close > df['High_50'].iloc[-1]) and (curr_vol > df['Vol_SMA20'].iloc[-1] * 1.5)
            if is_major_breakout:
                score += 50
                signals.append("🔥 MAJOR BREAKOUT (High Vol)")
                
            # Early Momentum: MACD crossover below zero (catching the bottom)
            if (macd > macd_sig) and (df['MACD'].iloc[-2] <= df['MACD_Signal'].iloc[-2]) and (macd < 0):
                score += 30
                signals.append("📈 Early MACD Bullish Cross")
                
            # Early Momentum: Stochastic crossing up from oversold territory
            if (stoch_k > stoch_d) and (stoch_k < 30) and (df['Stoch_K'].iloc[-2] <= df['Stoch_D'].iloc[-2]):
                score += 25
                signals.append("⚡ Stoch Oversold Reversal")
                
            # Trend Health: RSI showing strength but not overbought
            if 50 < rsi < 70:
                score += 15
                
            # Golden Cross / Pre-Cross
            s50, s200 = df['SMA50'].iloc[-1], df['SMA200'].iloc[-1]
            if s50 > s200:
                score += 20
            elif (s200 - s50) / s200 < 0.02:
                score += 15
                if "Pre-Cross Alert" not in signals: signals.append("⏳ Pre-Cross Alert")

            # Fundamentals
            ticker_obj = yf.Ticker(t)
            info = ticker_obj.info
            pe = info.get('trailingPE', 20)
            pb = info.get('priceToBook', 2)
            
            # Value boost
            if pe < 10 and pb < 1.0: score += 20
            
            if score > 0: # Only list stocks showing some form of life
                scored_results.append({
                    "Ticker": t,
                    "Price": round(curr_close, 2),
                    "RSI": round(rsi, 1),
                    "MACD": "Bullish" if macd > macd_sig else "Bearish",
                    "Score": score,
                    "Key Signals": " | ".join(signals) if signals else "Accumulating",
                    "Data": df
                })
        except Exception as e:
            continue
    return scored_results

# --- UI RENDERING ---
with st.spinner("Executing Smart Money Technical Scan..."):
    all_picks = auto_scan()

if all_picks:
    # Rank by the highest technical score
    ranked_df = pd.DataFrame(all_picks).sort_values(by="Score", ascending=False)
    
    top_share = ranked_df.iloc[0]
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.success(f"### 🥇 Top Technical Pick: {top_share['Ticker']}")
        st.metric("Technical/Smart Money Score", top_share['Score'])
        st.write(f"**Current Price:** LKR {top_share['Price']}")
        st.write(f"**RSI (14):** {top_share['RSI']}")
        st.write(f"**MACD Trend:** {top_share['MACD']}")
        st.info(f"**Primary Catalyst:** {top_share['Key Signals']}")
        
    with col2:
        # Advanced Charting with Subplots for Indicators
        df_chart = top_share['Data'].tail(150) # Show last 150 days for clarity
        
        fig = go.Figure()
        # Price and SMAs
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Close'], name="Price", line=dict(color='#00ffcc')))
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA50'], name="50 SMA", line=dict(color='orange', dash='dot')))
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['High_50'], name="50-Day Res", line=dict(color='red', dash='dash')))
        
        fig.update_layout(
            title=f"{top_share['Ticker']} - Structural Analysis",
            template="plotly_dark", 
            height=400,
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📋 Full Technical Ranking")
    display_df = ranked_df.drop(columns=['Data'])
    st.dataframe(display_df, use_container_width=True)
else:
    st.error("Market data currently unavailable.")
