from datetime import datetime, timedelta
from collections import Counter, defaultdict
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# Page Configuration
st.set_page_config(page_title="", layout="wide")

# Custom Styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #333;
        text-align: center;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# SIDEBAR CONFIGURATION
# ---------------------------------------------------------
st.sidebar.header("Settings")

ticker_options = [
    "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "USDCAD=X",
    "USDCHF=X", "USDJPY=X", "USDSGD=X", "GC=F", "BZ=F", "ZB=F",
    "BTC-USD", "EURGBP=X", "EURAUD=X", "EURNZD=X", "EURCAD=X",
    "EURCHF=X", "EURJPY=X", "EURSGD=X", "SGDJPY=X", "GBPAUD=X",
    "GBPNZD=X", "GBPCAD=X", "GBPCHF=X", "GBPJPY=X", "GBPSGD=X",
    "AUDNZD=X", "AUDCAD=X", "AUDCHF=X", "AUDJPY=X", "AUDSGD=X",
    "AAPL", "MSFT", "SPY", "QQQ"
]
symbol = st.sidebar.selectbox("Ticker Symbol", options=ticker_options, index=0)

trend_mode = st.sidebar.selectbox(
    "Trend Mode",
    ["Open, High, Low, Close + Midline", "Above/Below Midline"],
)

reversed_flag = st.sidebar.checkbox("Reverse Score Direction", value=False)

st.sidebar.subheader("Timeframe & History")
# Added "4h" to the timeframe choices
timeframe = st.sidebar.selectbox("Timeframe", ["30m", "60m", "4h", "8h", "1d", "1wk", "1mo", "3mo"], index=2)
history_period = st.sidebar.selectbox("History Range", ["1y", "2y", "5y", "10y", "max"], index=2)

if st.sidebar.button("🔄 Run Analysis"):
    st.rerun()

# ---------------------------------------------------------
# CORE LOGIC: SCORING FUNCTIONS
# ---------------------------------------------------------
def _compute_single_score(p_open, p_high, p_low, p_close, c_close, trend_mode_val, reversed_flag):
    green_candle = p_close >= p_open
    if green_candle:
        midline = ((p_close - p_open) / 2.0) + p_open
    else:
        midline = ((p_open - p_close) / 2.0) + p_close

    score = 0

    if trend_mode_val == "Open, High, Low, Close + Midline":
        if green_candle:
            if c_close >= midline and c_close < p_close:
                score = -1 if reversed_flag else 1
            elif c_close < midline and c_close > p_open:
                score = 1 if reversed_flag else -1
            elif c_close >= p_close and c_close < p_high:
                score = -2 if reversed_flag else 2
            elif c_close <= p_open and c_close > p_low:
                score = 2 if reversed_flag else -2
            elif c_close >= p_high:
                score = -3 if reversed_flag else 3
            elif c_close <= p_low:
                score = 3 if reversed_flag else -3
        else:  # Red candle
            if c_close >= midline and c_close < p_open:
                score = -1 if reversed_flag else 1
            elif c_close < midline and c_close > p_close:
                score = 1 if reversed_flag else -1
            elif c_close >= p_open and c_close < p_high:
                score = -2 if reversed_flag else 2
            elif c_close <= p_close and c_close > p_low:
                score = 2 if reversed_flag else -2
            elif c_close >= p_high:
                score = -3 if reversed_flag else 3
            elif c_close <= p_low:
                score = 3 if reversed_flag else -3

    elif trend_mode_val == "Above/Below Midline":
        if c_close >= midline:
            score = -3 if reversed_flag else 3
        else:
            score = 3 if reversed_flag else -3

    return score


@st.cache_data(ttl=300)
def fetch_data(ticker, period, interval):
    try:
        if interval in ["4h", "8h"]:
            # Yahoo Finance limits hourly data to a max of 730 days (2 years)
            if period in ["5y", "10y", "max"]:
                st.warning(f"⚠️ Yahoo Finance restricts hourly/intraday data to a maximum of 2 years. Automatically adjusting History Range to '2y' for {interval}.")
                period = "2y"
            
            data = yf.download(ticker, period=period, interval="60m", progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            if data is not None and not data.empty:
                if data.index.tz is not None:
                    data.index = data.index.tz_localize(None)
                
                data = data.resample(interval).agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last'
                }).dropna()
        else:
            data = yf.download(ticker, period=period, interval=interval, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
        return data
    except Exception as e:
        return None


# ---------------------------------------------------------
# INTRA-CANDLE EXTREME ANALYSIS
# ---------------------------------------------------------
def analyze_intra_candle_extremes(df, trend_mode_val, reversed_flag, timeframe):
    if df is None or len(df) < 2:
        return None
        
    work_df = df.copy()
    if timeframe in ["30m", "60m", "4h", "8h", "15m", "5m", "1m"]:
        work_df = work_df.iloc[:-1]
        
    hit_plus_3_total = 0
    closed_plus_3_count = 0
    plus_3_reversals = []
    
    hit_neg_3_total = 0
    closed_neg_3_count = 0
    neg_3_reversals = []
    
    for i in range(1, len(work_df)):
        p_open = work_df["Open"].iloc[i-1]
        p_high = work_df["High"].iloc[i-1]
        p_low = work_df["Low"].iloc[i-1]
        p_close = work_df["Close"].iloc[i-1]
        
        c_high = work_df["High"].iloc[i]
        c_low = work_df["Low"].iloc[i]
        c_close = work_df["Close"].iloc[i]
        
        if not reversed_flag:
            hit_plus_3 = c_high >= p_high
            closed_plus_3 = c_close >= p_high
            
            hit_neg_3 = c_low <= p_low
            closed_neg_3 = c_close <= p_low
        else:
            hit_plus_3 = c_low <= p_low
            closed_plus_3 = c_close <= p_low
            
            hit_neg_3 = c_high >= p_high
            closed_neg_3 = c_high >= p_high
            
        if hit_plus_3:
            hit_plus_3_total += 1
            if closed_plus_3:
                closed_plus_3_count += 1
            else:
                actual_score = _compute_single_score(p_open, p_high, p_low, p_close, c_close, trend_mode_val, reversed_flag)
                plus_3_reversals.append(actual_score)
                
        if hit_neg_3:
            hit_neg_3_total += 1
            if closed_neg_3:
                closed_neg_3_count += 1
            else:
                actual_score = _compute_single_score(p_open, p_high, p_low, p_close, c_close, trend_mode_val, reversed_flag)
                neg_3_reversals.append(actual_score)
                
    return {
        "hit_plus_3_total": hit_plus_3_total,
        "closed_plus_3_count": closed_plus_3_count,
        "plus_3_reversals": plus_3_reversals,
        "hit_neg_3_total": hit_neg_3_total,
        "closed_neg_3_count": closed_neg_3_count,
        "neg_3_reversals": neg_3_reversals
    }


# ---------------------------------------------------------
# MAIN DASHBOARD UI
# ---------------------------------------------------------
st.title("")
st.markdown(f"Analyzing how often candles **hit** vs. **close** at extreme scores (**+3 / -3**) during formation for **{symbol}** on **{timeframe}**.")

df = fetch_data(symbol, history_period, timeframe)

if df is None or df.empty:
    st.error(f"Could not retrieve data for ticker '{symbol}'. Try changing the History Range to '1y' or '2y'.")
else:
    results = analyze_intra_candle_extremes(df, trend_mode, reversed_flag, timeframe)
    
    if not results:
        st.warning("Not enough historical data points to generate analytics.")
    else:
        col1, col2 = st.columns(2)
        
        # --- POSITIVE EXTREME (+3) ---
        with col1:
            st.markdown("#### Positive Extreme (+3)")
            hit_p3 = results["hit_plus_3_total"]
            closed_p3 = results["closed_plus_3_count"]
            reversals_p3 = results["plus_3_reversals"]
            
            if hit_p3 > 0:
                close_pct = (closed_p3 / hit_p3) * 100
                st.metric("Total Candles Hitting +3 Level During Formation", hit_p3)
                st.metric("Closed as +3 (Continuation / Holding Extreme)", f"{close_pct:.1f}%", f"{closed_p3} / {hit_p3} times")
                
                st.markdown("---")
                st.markdown("##### Reversal / Pullback Breakdown (Failed to Close at +3)")
                total_rev_p3 = len(reversals_p3)
                if total_rev_p3 > 0:
                    rev_pct = (total_rev_p3 / hit_p3) * 100
                    st.metric("Successfully Reversed / Pulled Back", f"{rev_pct:.1f}%", f"{total_rev_p3} times")
                    
                    counts_p3 = Counter(reversals_p3)
                    df_rev_p3 = pd.DataFrame(list(counts_p3.items()), columns=["Closing Score", "Count"])
                    df_rev_p3["Percentage (%)"] = (df_rev_p3["Count"] / total_rev_p3 * 100).round(2)
                    st.dataframe(df_rev_p3.sort_values(by="Count", ascending=False), use_container_width=True, hide_index=True)
                else:
                    st.success("100% of candles that hit +3 closed as +3 (No pullbacks recorded).")
            else:
                st.info("No +3 extreme hits recorded in this range.")

        # --- NEGATIVE EXTREME (-3) ---
        with col2:
            st.markdown("#### Negative Extreme (-3)")
            hit_n3 = results["hit_neg_3_total"]
            closed_n3 = results["closed_neg_3_count"]
            reversals_n3 = results["neg_3_reversals"]
            
            if hit_n3 > 0:
                close_pct_n3 = (closed_n3 / hit_n3) * 100
                st.metric("Total Candles Hitting -3 Level During Formation", hit_n3)
                st.metric("Closed as -3 (Continuation / Holding Extreme)", f"{close_pct_n3:.1f}%", f"{closed_n3} / {hit_n3} times")
                
                st.markdown("---")
                st.markdown("##### Reversal / Pullback Breakdown (Failed to Close at -3)")
                total_rev_n3 = len(reversals_n3)
                if total_rev_n3 > 0:
                    rev_pct_n3 = (total_rev_n3 / hit_n3) * 100
                    st.metric("Successfully Reversed / Pulled Back", f"{rev_pct_n3:.1f}%", f"{total_rev_n3} times")
                    
                    counts_n3 = Counter(reversals_n3)
                    df_rev_n3 = pd.DataFrame(list(counts_n3.items()), columns=["Closing Score", "Count"])
                    df_rev_n3["Percentage (%)"] = (df_rev_n3["Count"] / total_rev_n3 * 100).round(2)
                    st.dataframe(df_rev_n3.sort_values(by="Count", ascending=False), use_container_width=True, hide_index=True)
                else:
                    st.success("100% of candles that hit -3 closed as -3 (No pullbacks recorded).")
            else:
                st.info("No -3 extreme hits recorded in this range.")
