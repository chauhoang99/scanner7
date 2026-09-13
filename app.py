from datetime import datetime
import re
import pandas as pd
import streamlit as st
import yfinance as yf

# Page Configuration
st.set_page_config(page_title="Macro HTF Liquidity Sweep Scanner (5m)", layout="wide")

# Custom CSS for compact mobile/desktop tables
st.markdown(
    """
    <style>
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
    }
    [data-testid="column"] {
        width: 48% !important;
        flex: 1 1 48% !important;
        min-width: unset !important;
        max-width: 48% !important;
        padding: 0px 2px !important;
    }
    table {
        font-size: 9px !important;
        width: 100% !important;
    }
    th, td {
        padding: 2px 4px !important;
        text-align: center !important;
        white-space: nowrap !important;
    }
    th:first-child, td:first-child {
        text-align: left !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# SIDEBAR CONFIGURATION
# ---------------------------------------------------------
st.sidebar.header("5m Macro Sweep Settings")

auto_refresh_on = st.sidebar.checkbox("Enable Auto-Refresh", value=True)
refresh_speed = st.sidebar.selectbox(
    "Refresh Interval", ["30 seconds", "1 minute", "5 minutes"], index=2
)

interval_map = {"30 seconds": 30, "1 minute": 60, "5 minutes": 300}
run_interval = interval_map[refresh_speed]

if st.sidebar.button("🔄 Refresh Now"):
    st.rerun()

st.sidebar.subheader("Macro Key Level Timeframes")
available_timeframes = ["8h", "1d", "1w", "1m", "3m", "6m", "1y"]

tf1_on = st.sidebar.checkbox("TF #1 On/Off", value=True)
tf1 = st.sidebar.selectbox("TF #1", available_timeframes, index=0)

tf2_on = st.sidebar.checkbox("TF #2 On/Off", value=True)
tf2 = st.sidebar.selectbox("TF #2", available_timeframes, index=1)

tf3_on = st.sidebar.checkbox("TF #3 On/Off", value=True)
tf3 = st.sidebar.selectbox("TF #3", available_timeframes, index=2)

tf4_on = st.sidebar.checkbox("TF #4 On/Off", value=True)
tf4 = st.sidebar.selectbox("TF #4", available_timeframes, index=3)

# Ticker groups mapping
group_tickers = {
    "USD": [
        ("EURUSD", "EURUSD=X"),
        ("GBPUSD", "GBPUSD=X"),
        ("AUDUSD", "AUDUSD=X"),
        ("NZDUSD", "NZDUSD=X"),
        ("USDCAD", "USDCAD=X"),
        ("USDCHF", "USDCHF=X"),
        ("USDJPY", "USDJPY=X"),
        ("USDSGD", "USDSGD=X"),
        ("XAUUSD", "GC=F"),
        ("BRENT", "BZ=F"),
        ("US30", "ZB=F"),
        ("BTCUSD", "BTC-USD"),
    ],
    "EUR": [
        ("EURUSD", "EURUSD=X"),
        ("EURGBP", "EURGBP=X"),
        ("EURAUD", "EURAUD=X"),
        ("EURNZD", "EURNZD=X"),
        ("EURCAD", "EURCAD=X"),
        ("EURCHF", "EURCHF=X"),
        ("EURJPY", "EURJPY=X"),
        ("EURSGD", "EURSGD=X"),
        ("XAUEUR", "XAUEUR=X")
    ],
    "GBP": [
        ("GBPUSD", "GBPUSD=X"),
        ("EURGBP", "EURGBP=X"),
        ("GBPAUD", "GBPAUD=X"),
        ("GBPNZD", "GBPNZD=X"),
        ("GBPCAD", "GBPCAD=X"),
        ("GBPCHF", "GBPCHF=X"),
        ("GBPJPY", "GBPJPY=X"),
        ("GBPSGD", "GBPSGD=X"),
        ("UK10Y", "IGLT.L")
    ],
    "AUD": [
        ("AUDUSD", "AUDUSD=X"),
        ("EURAUD", "EURAUD=X"),
        ("GBPAUD", "GBPAUD=X"),
        ("AUDNZD", "AUDNZD=X"),
        ("AUDCAD", "AUDCAD=X"),
        ("AUDCHF", "AUDCHF=X"),
        ("AUDJPY", "AUDJPY=X"),
        ("AUDSGD", "AUDSGD=X"),
        ("XAUUSD", "GC=F"),
        ("VGB", "VGB.AX")
    ],
    "CAD": [
        ("EURCAD", "EURCAD=X"),
        ("GBPCAD", "GBPCAD=X"),
        ("AUDCAD", "AUDCAD=X"),
        ("USDCAD", "USDCAD=X"),
        ("CADCHF", "CADCHF=X"),
        ("CADJPY", "CADJPY=X"),
        ("BRENT", "BZ=F"),
        ("VAB", "VAB.TO"),
    ],
    "NZD": [
        ("NZDUSD", "NZDUSD=X"),
        ("EURNZD", "EURNZD=X"),
        ("GBPNZD", "GBPNZD=X"),
        ("AUDNZD", "AUDNZD=X"),
        ("NZDCAD", "NZDCAD=X"),
        ("NZDCHF", "NZDCHF=X"),
        ("NGB", "NGB.NZ"),
    ],
    "JPY": [
        ("EURJPY", "EURJPY=X"),
        ("GBPJPY", "GBPJPY=X"),
        ("AUDJPY", "AUDJPY=X"),
        ("NZDJPY", "NZDJPY=X"),
        ("USDJPY", "USDJPY=X"),
        ("CADJPY", "CADJPY=X"),
        ("JGB", "2561.T")
    ],
    "CHF": [
        ("EURCHF", "EURCHF=X"),
        ("GBPCHF", "GBPCHF=X"),
        ("AUDCHF", "AUDCHF=X"),
        ("NZDCHF", "NZDCHF=X"),
        ("USDCHF", "USDCHF=X"),
        ("CADCHF", "CADCHF=X"),
        ("CSBGC", "CSBGC0.SW")
    ],
    "SGD": [
        ("EURSGD", "EURSGD=X"),
        ("GBPSGD", "GBPSGD=X"),
        ("AUDSGD", "AUDSGD=X"),
        ("NZDSGD", "NZDSGD=X"),
        ("USDSGD", "USDSGD=X"),
        ("CADSGD", "CADSGD=X"),
    ],
    "HKD": [
        ("USDHKD", "USDHKD=X"),
        ("EURHKD", "EURHKD=X"),
        ("GBPHKD", "GBPHKD=X"),
        ("AUDHKD", "AUDHKD=X"),
    ],
    "CNY": [
        ("USDCNY", "CNY=X"),
    ],
}


# ---------------------------------------------------------
# DATA FETCHING & MACRO RESAMPLING LOGIC
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def fetch_data(ticker, period, interval):
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception:
        return None


def fetch_htf_data(ticker, tf):
    if tf == "8h":
        df = fetch_data(ticker, period="1y", interval="1h")
        if df is not None and not df.empty:
            df = df.resample("8h").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
        return df
    elif tf == "1d":
        return fetch_data(ticker, period="1y", interval="1d")
    elif tf == "1w":
        return fetch_data(ticker, period="2y", interval="1wk")
    elif tf == "1m":
        return fetch_data(ticker, period="5y", interval="1mo")
    elif tf == "3m":
        return fetch_data(ticker, period="max", interval="3mo")
    elif tf == "6m":
        df = fetch_data(ticker, period="max", interval="1mo")
        if df is not None and not df.empty:
            try:
                df = df.resample("6ME").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
            except Exception:
                df = df.resample("6M").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
        return df
    elif tf == "1y":
        df = fetch_data(ticker, period="max", interval="1mo")
        if df is not None and not df.empty:
            try:
                df = df.resample("1YE").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
            except Exception:
                df = df.resample("YE").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
        return df
    return None


def get_pip_multiplier(ticker):
    """Returns the multiplier to convert raw price distances into pips or points."""
    ticker_upper = ticker.upper()
    if "JPY" in ticker_upper:
        return 100
    elif any(x in ticker_upper for x in ["BTC", "US30", "BRENT", "XAU", "GC=F", "BZ=F", "ZB=F", "UK10Y", "IGLT", "VGB", "VAB", "NGB", "JGB", "2561", "CSBGC"]):
        return 1
    else:
        return 10000


# ---------------------------------------------------------
# STATEFUL SWEEP DETECTION & INVALIDATION LOGIC
# ---------------------------------------------------------
def detect_sweep(yf_ticker, tf, df_5m, df_htf):
    if df_5m is None or df_5m.empty or df_htf is None or len(df_htf) < 2:
        return "No Level", 0

    current_htf_start = df_htf.index[-1]
    key_high = df_htf["High"].iloc[-2]
    key_low = df_htf["Low"].iloc[-2]

    if df_5m.index.tz is not None and current_htf_start.tz is None:
        current_htf_start = current_htf_start.tz_localize(df_5m.index.tz)
    elif df_5m.index.tz is None and current_htf_start.tz is not None:
        current_htf_start = current_htf_start.tz_localize(None)
    elif getattr(df_5m.index.tz, 'zone', None) != getattr(current_htf_start.tz, 'zone', None):
        current_htf_start = current_htf_start.tz_convert(df_5m.index.tz)

    df_5m_current = df_5m[df_5m.index >= current_htf_start]

    if df_5m_current.empty:
        return "", 0

    period_high = df_5m_current["High"].max()
    period_low = df_5m_current["Low"].min()
    current_close = df_5m_current["Close"].iloc[-1]

    mult = get_pip_multiplier(yf_ticker)
    unit = "pips" if mult in [100, 10000] else "pts"

    if period_high > key_high and current_close < key_high:
        dist = (key_high - current_close) * mult
        return f"🔴 ({dist:.1f} {unit})", -1
        
    elif period_low < key_low and current_close > key_low:
        dist = (current_close - key_low) * mult
        return f"🟢 ({dist:.1f} {unit})", 1
        
    else:
        return "", 0


# ---------------------------------------------------------
# ROW STYLING FUNCTION
# ---------------------------------------------------------
def style_row(row):
    styles = [""] * len(row)
    for i, col in enumerate(row.index):
        val = str(row[col])
        if "🔴" in val or "🟢" in val:
            match = re.search(r'\(([\d\.]+)\s+', val)
            if match:
                dist = float(match.group(1))
                if dist < 5.0:
                    if "🔴" in val:
                        styles[i] = "background-color: #ff4d4d; color: white; font-weight: bold;"
                    elif "🟢" in val:
                        styles[i] = "background-color: #00cc66; color: black; font-weight: bold;"
                else:
                    styles[i] = "color: black; font-weight: bold;"
    return styles


def get_group_sweep_df(tickers_to_scan):
    results = []
    for display_name, yf_ticker in tickers_to_scan:
        df_5m = fetch_data(yf_ticker, period="60d", interval="5m")

        df_tf1 = fetch_htf_data(yf_ticker, tf1) if tf1_on else None
        df_tf2 = fetch_htf_data(yf_ticker, tf2) if tf2_on else None
        df_tf3 = fetch_htf_data(yf_ticker, tf3) if tf3_on else None
        df_tf4 = fetch_htf_data(yf_ticker, tf4) if tf4_on else None

        s1_str, _ = detect_sweep(yf_ticker, tf1, df_5m, df_tf1) if tf1_on else ("N/A", 0)
        s2_str, _ = detect_sweep(yf_ticker, tf2, df_5m, df_tf2) if tf2_on else ("N/A", 0)
        s3_str, _ = detect_sweep(yf_ticker, tf3, df_5m, df_tf3) if tf3_on else ("N/A", 0)
        s4_str, _ = detect_sweep(yf_ticker, tf4, df_5m, df_tf4) if tf4_on else ("N/A", 0)

        results.append({
            "Ticker": display_name,
            f"TF 1 ({tf1})": s1_str,
            f"TF 2 ({tf2})": s2_str,
            f"TF 3 ({tf3})": s3_str,
            f"TF 4 ({tf4})": s4_str,
        })
    return pd.DataFrame(results)


# ---------------------------------------------------------
# DASHBOARD RENDERING FRAGMENT
# ---------------------------------------------------------
active_refresh_rate = run_interval if auto_refresh_on else None


@st.fragment(run_every=active_refresh_rate)
def render_sweep_dashboard():
    st.caption(f"⏱️ Last updated (5m scan): {datetime.now().strftime('%H:%M:%S')}")

    group_items = list(group_tickers.items())

    for i in range(0, len(group_items), 2):
        cols = st.columns(2)

        with cols[0]:
            g_name_1, t_list_1 = group_items[i]
            st.markdown(f"##### 💱 {g_name_1} Group")
            df_1 = get_group_sweep_df(t_list_1)
            if not df_1.empty:
                st.table(df_1.style.apply(style_row, axis=1))

        if i + 1 < len(group_items):
            with cols[1]:
                g_name_2, t_list_2 = group_items[i + 1]
                st.markdown(f"##### 💱 {g_name_2} Group")
                df_2 = get_group_sweep_df(t_list_2)
                if not df_2.empty:
                    st.table(df_2.style.apply(style_row, axis=1))

        st.markdown("---")


render_sweep_dashboard()
