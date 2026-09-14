from datetime import datetime
import re
import pandas as pd
import requests
import streamlit as st

# Page Configuration
st.set_page_config(page_title="Macro HTF Liquidity Sweep Scanner (Oanda)", layout="wide")

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
# LOAD CREDENTIALS SAFELY FROM STREAMLIT CLOUD SECRETS
# ---------------------------------------------------------
try:
    secret_token = st.secrets.get("oanda_api_token", "")
    secret_account = st.secrets.get("oanda_account_id", "")
    secret_env = st.secrets.get("oanda_env", "Practice")
except Exception:
    secret_token, secret_account, secret_env = "", "", "Practice"

# ---------------------------------------------------------
# SIDEBAR CONFIGURATION
# ---------------------------------------------------------
st.sidebar.header("Oanda API Settings")

env_index = 0 if secret_env == "Practice" else 1
oanda_env = st.sidebar.selectbox("Environment", ["Practice", "Live"], index=env_index)

if secret_token:
    st.sidebar.success("🔒 Oanda Token loaded from Streamlit Secrets")
    api_token = secret_token
    account_id = secret_account
else:
    api_token = st.sidebar.text_input("Oanda API Token", type="password", value="")
    account_id = st.sidebar.text_input("Oanda Account ID", value="")

st.sidebar.markdown("---")
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

# Ticker groups mapping (Oanda Instrument Format)
group_tickers = {
    "USD": [
        ("EURUSD", "EUR_USD"),
        ("GBPUSD", "GBP_USD"),
        ("AUDUSD", "AUD_USD"),
        ("NZDUSD", "NZD_USD"),
        ("USDCAD", "USD_CAD"),
        ("USDCHF", "USD_CHF"),
        ("USDJPY", "USD_JPY"),
        ("USDSGD", "USD_SGD"),
        ("XAUUSD", "XAU_USD"),
        ("BRENT", "BCO_USD"),
        ("BTCUSD", "BTC_USD"),
    ],
    "EUR": [
        ("EURUSD", "EUR_USD"),
        ("EURGBP", "EUR_GBP"),
        ("EURAUD", "EUR_AUD"),
        ("EURNZD", "EUR_NZD"),
        ("EURCAD", "EUR_CAD"),
        ("EURCHF", "EUR_CHF"),
        ("EURJPY", "EUR_JPY"),
        ("EURSGD", "EUR_SGD"),
    ],
    "GBP": [
        ("GBPUSD", "GBP_USD"),
        ("EURGBP", "EUR_GBP"),
        ("GBPAUD", "GBP_AUD"),
        ("GBPNZD", "GBP_NZD"),
        ("GBPCAD", "GBP_CAD"),
        ("GBPCHF", "GBP_CHF"),
        ("GBPJPY", "GBP_JPY"),
        ("GBPSGD", "GBP_SGD"),
    ],
    "AUD": [
        ("AUDUSD", "AUD_USD"),
        ("EURAUD", "EUR_AUD"),
        ("GBPAUD", "GBP_AUD"),
        ("AUDNZD", "AUD_NZD"),
        ("AUDCAD", "AUD_CAD"),
        ("AUDCHF", "AUD_CHF"),
        ("AUDJPY", "AUD_JPY"),
        ("AUDSGD", "AUD_SGD"),
        ("XAUUSD", "XAU_USD"),
    ],
    "CAD": [
        ("EURCAD", "EUR_CAD"),
        ("GBPCAD", "GBP_CAD"),
        ("AUDCAD", "AUD_CAD"),
        ("USDCAD", "USD_CAD"),
        ("CADCHF", "CAD_CHF"),
        ("CADJPY", "CAD_JPY"),
        ("BRENT", "BCO_USD"),
    ],
    "NZD": [
        ("NZDUSD", "NZD_USD"),
        ("EURNZD", "EUR_NZD"),
        ("GBPNZD", "GBP_NZD"),
        ("AUDNZD", "AUD_NZD"),
        ("NZDCAD", "NZD_CAD"),
        ("NZDCHF", "NZD_CHF"),
    ],
    "JPY": [
        ("EURJPY", "EUR_JPY"),
        ("GBPJPY", "GBP_JPY"),
        ("AUDJPY", "AUD_JPY"),
        ("NZDJPY", "NZD_JPY"),
        ("USDJPY", "USD_JPY"),
        ("CADJPY", "CAD_JPY"),
    ],
    "CHF": [
        ("EURCHF", "EUR_CHF"),
        ("GBPCHF", "GBP_CHF"),
        ("AUDCHF", "AUD_CHF"),
        ("NZDCHF", "NZD_CHF"),
        ("USDCHF", "USD_CHF"),
        ("CADCHF", "CAD_CHF"),
    ],
    "SGD": [
        ("EURSGD", "EUR_SGD"),
        ("GBPSGD", "GBP_SGD"),
        ("AUDSGD", "AUD_SGD"),
        ("NZDSGD", "NZD_SGD"),
        ("USDSGD", "USD_SGD"),
        ("CADSGD", "CAD_SGD"),
    ],
}


# ---------------------------------------------------------
# OANDA DATA FETCHING & MACRO RESAMPLING LOGIC
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def fetch_oanda_candles(instrument, granularity, count=500, token=None, env="Practice"):
    if not token:
        return None
    
    domain = "api-fxtrade.oanda.com" if env == "Live" else "api-fxpractice.oanda.com"
    url = f"https://{domain}/v3/instruments/{instrument}/candles"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {
        "price": "M",
        "granularity": granularity,
        "count": count
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            candles = data.get("candles", [])
            if not candles:
                return None
            
            rows = []
            for c in candles:
                if c.get("complete", True):
                    time = pd.to_datetime(c["time"])
                    mid = c["mid"]
                    rows.append({
                        "Time": time,
                        "Open": float(mid["o"]),
                        "High": float(mid["h"]),
                        "Low": float(mid["l"]),
                        "Close": float(mid["c"])
                    })
            df = pd.DataFrame(rows)
            if not df.empty:
                df.set_index("Time", inplace=True)
            return df
    except Exception:
        return None
    return None


def fetch_htf_data(instrument, tf, token, env):
    if tf == "8h":
        return fetch_oanda_candles(instrument, "H8", count=400, token=token, env=env)
    elif tf == "1d":
        return fetch_oanda_candles(instrument, "D", count=365, token=token, env=env)
    elif tf == "1w":
        return fetch_oanda_candles(instrument, "W", count=104, token=token, env=env)
    elif tf == "1m":
        return fetch_oanda_candles(instrument, "M", count=60, token=token, env=env)
    elif tf in ["3m", "6m", "1y"]:
        df = fetch_oanda_candles(instrument, "M", count=120, token=token, env=env)
        if df is not None and not df.empty:
            rule = "3ME" if tf == "3m" else ("6ME" if tf == "6m" else "1YE")
            try:
                df = df.resample(rule).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
            except Exception:
                rule_fallback = "3M" if tf == "3m" else ("6M" if tf == "6m" else "YE")
                df = df.resample(rule_fallback).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
        return df
    return None


def get_pip_multiplier(ticker):
    ticker_upper = ticker.upper()
    if "JPY" in ticker_upper:
        return 100
    elif any(x in ticker_upper for x in ["BTC", "XAU", "BCO"]):
        return 1
    else:
        return 10000


# ---------------------------------------------------------
# NARROW RANGE (NR) CALCULATION LOGIC
# ---------------------------------------------------------
def get_nr_status(instrument, token, env):
    df_d = fetch_oanda_candles(instrument, "D", count=30, token=token, env=env)
    if df_d is None or len(df_d) < 22:
        return ""
    df_d["Range"] = df_d["High"] - df_d["Low"]
    r = df_d["Range"]
    
    # Check the last completed daily bar (iloc[-2]) against previous historical window
    is_nr4 = r.iloc[-2] == r.iloc[-5:-1].min()
    is_nr7 = r.iloc[-2] == r.iloc[-8:-1].min()
    is_nr21 = r.iloc[-2] == r.iloc[-22:-1].min()
    
    if is_nr21:
        return "[NR21]"
    elif is_nr7:
        return "[NR7]"
    elif is_nr4:
        return "[NR4]"
    return ""


# ---------------------------------------------------------
# STATEFUL SWEEP DETECTION LOGIC
# ---------------------------------------------------------
def detect_sweep(oanda_instrument, tf, df_5m, df_htf):
    if df_5m is None or df_5m.empty or df_htf is None or len(df_htf) < 2:
        return "", 0

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

    mult = get_pip_multiplier(oanda_instrument)
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
                    styles[i] = "color: white; font-weight: bold;"
        elif "NR" in val:
            styles[i] = "font-weight: bold;"
    return styles


def get_group_sweep_df(tickers_to_scan):
    results = []
    if not api_token:
        return pd.DataFrame([{"Ticker": "Missing Token", "Status": "Check Secrets"}])

    for display_name, oanda_inst in tickers_to_scan:
        df_5m = fetch_oanda_candles(oanda_inst, "M5", count=300, token=api_token, env=oanda_env)

        df_tf1 = fetch_htf_data(oanda_inst, tf1, api_token, oanda_env) if tf1_on else None
        df_tf2 = fetch_htf_data(oanda_inst, tf2, api_token, oanda_env) if tf2_on else None
        df_tf3 = fetch_htf_data(oanda_inst, tf3, api_token, oanda_env) if tf3_on else None
        df_tf4 = fetch_htf_data(oanda_inst, tf4, api_token, oanda_env) if tf4_on else None

        s1_str, _ = detect_sweep(oanda_inst, tf1, df_5m, df_tf1) if tf1_on else ("N/A", 0)
        s2_str, _ = detect_sweep(oanda_inst, tf2, df_5m, df_tf2) if tf2_on else ("N/A", 0)
        s3_str, _ = detect_sweep(oanda_inst, tf3, df_5m, df_tf3) if tf3_on else ("N/A", 0)
        s4_str, _ = detect_sweep(oanda_inst, tf4, df_5m, df_tf4) if tf4_on else ("N/A", 0)

        # Get NR label and append to TF1 cell if active
        nr_label = get_nr_status(oanda_inst, api_token, oanda_env)
        if nr_label:
            if s1_str and s1_str != "N/A":
                s1_str = f"{s1_str} {nr_label}"
            else:
                s1_str = nr_label

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
    if not api_token:
        st.warning("⚠️ Oanda API token not found. Please add `oanda_api_token` to your Streamlit Cloud Secrets dashboard.")
        return

    st.caption(f"⏱️ Last updated (Oanda 5m scan): {datetime.now().strftime('%H:%M:%S')} | *NR labels indicate Narrow Range contraction days*")

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
