from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Optional, Tuple, Dict, List
import re

import pandas as pd
import requests
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Macro HTF Liquidity Sweep & Dynamic OR-NR Scanner",
    layout="wide",
)

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
        padding: 0 2px !important;
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


# ============================================================
# SECRETS
# ============================================================
try:
    secret_token = st.secrets.get("oanda_api_token", "")
    secret_account = st.secrets.get("oanda_account_id", "")
    secret_env = st.secrets.get("oanda_env", "Practice")
except Exception:
    secret_token = ""
    secret_account = ""
    secret_env = "Practice"


# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.header("OANDA API Settings")

env_index = 0 if secret_env == "Practice" else 1
oanda_env = st.sidebar.selectbox(
    "Environment",
    ["Practice", "Live"],
    index=env_index,
)

if secret_token:
    st.sidebar.success("🔒 OANDA token loaded from Streamlit Secrets")
    api_token = secret_token
    account_id = secret_account
else:
    api_token = st.sidebar.text_input("OANDA API Token", type="password", value="")
    account_id = st.sidebar.text_input("OANDA Account ID", value="")

st.sidebar.markdown("---")
st.sidebar.header("Refresh")

auto_refresh_on = st.sidebar.checkbox("Enable Auto-Refresh", value=True)
refresh_speed = st.sidebar.selectbox(
    "Refresh Interval",
    ["15 seconds", "30 seconds", "1 minute", "5 minutes"],
    index=1,
)

interval_map = {
    "15 seconds": 15,
    "30 seconds": 30,
    "1 minute": 60,
    "5 minutes": 300,
}
run_interval = interval_map[refresh_speed]

if "manual_refresh_nonce" not in st.session_state:
    st.session_state.manual_refresh_nonce = 0

if st.sidebar.button("🔄 Refresh Now"):
    st.session_state.manual_refresh_nonce += 1
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("5m Macro Sweep Settings")

st.sidebar.subheader("Opening Range (OR) & NR Settings")
or_duration_mins = st.sidebar.selectbox(
    "OR Duration",
    [15, 30, 60, 120],
    index=2,
)

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

st.sidebar.markdown("---")
st.sidebar.header("Display")

show_data_age = st.sidebar.checkbox("Show data age", value=True)
show_debug = st.sidebar.checkbox("Show debug details", value=False)
highlight_distance = st.sidebar.number_input(
    "Highlight sweep distance below",
    min_value=0.0,
    max_value=1000.0,
    value=5.0,
    step=0.5,
)


# ============================================================
# TICKER GROUPS
# ============================================================
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


# ============================================================
# HELPERS
# ============================================================
def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def get_oanda_domain(env: str) -> str:
    return "api-fxtrade.oanda.com" if env == "Live" else "api-fxpractice.oanda.com"


def get_pip_multiplier(ticker: str) -> int:
    ticker_upper = ticker.upper()
    if "JPY" in ticker_upper:
        return 100
    if any(x in ticker_upper for x in ["BTC", "XAU", "BCO"]):
        return 1
    return 10000


def ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    if out.index.tz is None:
        out.index = pd.to_datetime(out.index, utc=True)
    else:
        out.index = out.index.tz_convert("UTC")
    return out


def format_age(ts: Optional[pd.Timestamp]) -> str:
    if ts is None or pd.isna(ts):
        return "N/A"
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")

    seconds = max(0, int((utc_now() - ts).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def get_current_session_info() -> Tuple[int, str]:
    current_utc_hour = datetime.now(timezone.utc).hour
    if 0 <= current_utc_hour < 8:
        return 0, "Tokyo"
    if 8 <= current_utc_hour < 13:
        return 8, "London"
    return 13, "New York"


# ============================================================
# OANDA FETCHING
# ============================================================
@st.cache_data(ttl=5, show_spinner=False)
def fetch_oanda_candles(
    instrument: str,
    granularity: str,
    count: int,
    token: str,
    env: str,
    include_incomplete: bool = False,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Fetch candles from OANDA.

    include_incomplete=False:
        only complete candles are returned.

    include_incomplete=True:
        current incomplete candle is retained. This is required to identify
        the current OANDA HTF period correctly.
    """
    if not token:
        return None, "Missing OANDA API token"

    domain = get_oanda_domain(env)
    url = f"https://{domain}/v3/instruments/{instrument}/candles"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    params = {
        "price": "M",
        "granularity": granularity,
        "count": count,
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=12,
        )

        if response.status_code != 200:
            msg = response.text[:250].replace("\n", " ")
            return None, f"HTTP {response.status_code}: {msg}"

        payload = response.json()
        candles = payload.get("candles", [])

        if not candles:
            return None, "OANDA returned no candles"

        rows = []
        for candle in candles:
            complete = bool(candle.get("complete", False))
            if not include_incomplete and not complete:
                continue

            mid = candle.get("mid")
            if not mid:
                continue

            rows.append(
                {
                    "Time": pd.to_datetime(candle["time"], utc=True),
                    "Open": float(mid["o"]),
                    "High": float(mid["h"]),
                    "Low": float(mid["l"]),
                    "Close": float(mid["c"]),
                    "Complete": complete,
                }
            )

        if not rows:
            return None, "No usable candles after filtering"

        df = pd.DataFrame(rows).set_index("Time").sort_index()
        return df, None

    except requests.Timeout:
        return None, "OANDA request timed out"
    except requests.RequestException as exc:
        return None, f"OANDA request error: {exc}"
    except Exception as exc:
        return None, f"Unexpected fetch error: {exc}"


def fetch_live_m5(
    instrument: str,
    token: str,
    env: str,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    # 2500 x M5 ~= 8.7 days, enough for OR/NR statistics.
    # Keep only completed M5 bars so sweep confirmation is not based on a
    # still-forming 5-minute candle.
    return fetch_oanda_candles(
        instrument=instrument,
        granularity="M5",
        count=2500,
        token=token,
        env=env,
        include_incomplete=False,
    )


def fetch_direct_htf(
    instrument: str,
    granularity: str,
    count: int,
    token: str,
    env: str,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    # Retain OANDA's current incomplete HTF candle. Its timestamp gives us
    # the correct current period boundary.
    return fetch_oanda_candles(
        instrument=instrument,
        granularity=granularity,
        count=count,
        token=token,
        env=env,
        include_incomplete=True,
    )


def resample_monthly_periods(
    monthly_df: pd.DataFrame,
    months_per_period: int,
) -> pd.DataFrame:
    """
    Convert OANDA M candles into 3M / 6M / 12M calendar periods.

    We explicitly assign every monthly candle to a UTC calendar-period start,
    then aggregate OHLC. The current period remains marked incomplete.
    """
    if monthly_df is None or monthly_df.empty:
        return monthly_df

    df = ensure_utc_index(monthly_df).copy()

    records = []
    for ts, row in df.iterrows():
        year = ts.year
        month = ts.month

        zero_based = month - 1
        bucket_start_month = (zero_based // months_per_period) * months_per_period + 1
        bucket_start = pd.Timestamp(
            year=year,
            month=bucket_start_month,
            day=1,
            tz="UTC",
        )

        records.append(
            {
                "PeriodStart": bucket_start,
                "Open": row["Open"],
                "High": row["High"],
                "Low": row["Low"],
                "Close": row["Close"],
                "Complete": bool(row["Complete"]),
                "SourceTime": ts,
            }
        )

    tmp = pd.DataFrame(records)

    agg = (
        tmp.groupby("PeriodStart", sort=True)
        .agg(
            Open=("Open", "first"),
            High=("High", "max"),
            Low=("Low", "min"),
            Close=("Close", "last"),
            Complete=("Complete", "all"),
            LastSourceTime=("SourceTime", "max"),
        )
        .sort_index()
    )

    # A grouped multi-month period should be incomplete if it contains the
    # current incomplete monthly candle.
    return agg


def fetch_htf_data(
    instrument: str,
    tf: str,
    token: str,
    env: str,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    if tf == "8h":
        return fetch_direct_htf(instrument, "H8", 400, token, env)
    if tf == "1d":
        return fetch_direct_htf(instrument, "D", 365, token, env)
    if tf == "1w":
        return fetch_direct_htf(instrument, "W", 104, token, env)
    if tf == "1m":
        return fetch_direct_htf(instrument, "M", 72, token, env)

    if tf in {"3m", "6m", "1y"}:
        monthly, err = fetch_direct_htf(
            instrument,
            "M",
            180,
            token,
            env,
        )
        if err:
            return None, err
        if monthly is None or monthly.empty:
            return None, "No monthly data available"

        months = {"3m": 3, "6m": 6, "1y": 12}[tf]
        return resample_monthly_periods(monthly, months), None

    return None, f"Unsupported timeframe: {tf}"


# ============================================================
# CURRENT HTF PERIOD + SWEEP LOGIC
# ============================================================
def get_current_and_previous_htf(
    df_htf: pd.DataFrame,
) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Timestamp], Optional[str]]:
    """
    Returns:
        current_row
        previous_completed_row
        current_period_start
        error

    The key idea:
    - current HTF row may be incomplete.
    - sweep key levels come from the previous COMPLETED HTF period.
    - M5 scanning begins at the current HTF period's actual start.
    """
    if df_htf is None or df_htf.empty:
        return None, None, None, "No HTF data"

    df = ensure_utc_index(df_htf).sort_index()

    current_row = df.iloc[-1]
    current_start = df.index[-1]

    # If the most recent row is incomplete, it is the current HTF candle.
    if "Complete" in df.columns and not bool(current_row["Complete"]):
        completed_before = df.iloc[:-1]
    else:
        # This can happen at a boundary just after a candle completes before
        # OANDA has delivered the new incomplete candle.
        # In that case do not pretend the completed candle is the current one.
        return None, None, None, "Current HTF candle not available yet"

    if completed_before.empty:
        return None, None, None, "No previous completed HTF candle"

    previous_row = completed_before.iloc[-1]

    return current_row, previous_row, current_start, None


def detect_sweep(
    instrument: str,
    tf: str,
    df_m5: pd.DataFrame,
    df_htf: pd.DataFrame,
) -> Tuple[str, int, Dict[str, object]]:
    """
    Stateful current-period sweep detection.

    Red sweep:
        current HTF period traded above previous completed HTF high,
        and latest completed M5 close is back below that high.

    Green sweep:
        current HTF period traded below previous completed HTF low,
        and latest completed M5 close is back above that low.
    """
    debug = {
        "tf": tf,
        "current_start": None,
        "key_high": None,
        "key_low": None,
        "period_high": None,
        "period_low": None,
        "latest_m5_close": None,
        "latest_m5_time": None,
        "error": None,
    }

    if df_m5 is None or df_m5.empty:
        debug["error"] = "No M5 data"
        return "⚠️ DATA", 0, debug

    if df_htf is None or df_htf.empty:
        debug["error"] = "No HTF data"
        return "⚠️ DATA", 0, debug

    m5 = ensure_utc_index(df_m5)
    htf = ensure_utc_index(df_htf)

    current_row, previous_row, current_start, err = get_current_and_previous_htf(htf)
    if err:
        debug["error"] = err
        return "⚠️ DATA", 0, debug

    key_high = float(previous_row["High"])
    key_low = float(previous_row["Low"])

    current_m5 = m5[m5.index >= current_start]
    if current_m5.empty:
        debug["error"] = "No completed M5 bars inside current HTF period"
        return "…", 0, debug

    period_high = float(current_m5["High"].max())
    period_low = float(current_m5["Low"].min())
    latest_close = float(current_m5["Close"].iloc[-1])
    latest_time = current_m5.index[-1]

    debug.update(
        {
            "current_start": current_start,
            "key_high": key_high,
            "key_low": key_low,
            "period_high": period_high,
            "period_low": period_low,
            "latest_m5_close": latest_close,
            "latest_m5_time": latest_time,
        }
    )

    mult = get_pip_multiplier(instrument)
    unit = "pips" if mult in (100, 10000) else "pts"

    high_swept = period_high > key_high
    low_swept = period_low < key_low

    # If both sides have swept, report the side corresponding to where the
    # latest completed M5 close has reclaimed. If it is inside both levels,
    # show both sweeps rather than losing information.
    red_confirmed = high_swept and latest_close < key_high
    green_confirmed = low_swept and latest_close > key_low

    if red_confirmed and green_confirmed:
        red_dist = (key_high - latest_close) * mult
        green_dist = (latest_close - key_low) * mult
        return (
            f"🔴 ({red_dist:.1f} {unit}) / 🟢 ({green_dist:.1f} {unit})",
            2,
            debug,
        )

    if red_confirmed:
        dist = (key_high - latest_close) * mult
        return f"🔴 ({dist:.1f} {unit})", -1, debug

    if green_confirmed:
        dist = (latest_close - key_low) * mult
        return f"🟢 ({dist:.1f} {unit})", 1, debug

    # Useful state markers:
    # A level may already have been breached but not yet reclaimed.
    if high_swept and latest_close >= key_high:
        return "🔺 above prev high", 0, debug

    if low_swept and latest_close <= key_low:
        return "🔻 below prev low", 0, debug

    return "", 0, debug


# ============================================================
# OR / NR LOGIC
# ============================================================
def get_or_nr_status_from_m5(
    df_m5: pd.DataFrame,
    instrument: str,
    or_start_h: int,
    or_dur_mins: int,
) -> str:
    """
    Reuses the already-fetched M5 history.
    No second OANDA M5 request is made.
    """
    if df_m5 is None or df_m5.empty:
        return ""

    df = ensure_utc_index(df_m5).copy()
    df["Date"] = df.index.date

    start_total_mins = or_start_h * 60 + or_dur_mins
    end_h = (start_total_mins // 60) % 24
    end_m = start_total_mins % 60

    or_start_t = time(or_start_h, 0)
    or_end_t = time(end_h, end_m)

    mult = get_pip_multiplier(instrument)
    records = []

    for date_val, day_df in df.groupby("Date"):
        t = day_df.index.time

        if or_end_t > or_start_t:
            mask = (t >= or_start_t) & (t < or_end_t)
        else:
            # Defensive support for ranges that cross midnight.
            mask = (t >= or_start_t) | (t < or_end_t)

        or_df = day_df[mask]
        if or_df.empty or len(or_df) < 2:
            continue

        or_high = float(or_df["High"].max())
        or_low = float(or_df["Low"].min())
        or_size = (or_high - or_low) * mult

        if or_size > 0:
            records.append(
                {
                    "Date": date_val,
                    "OR_Size": or_size,
                }
            )

    df_or = pd.DataFrame(records)
    if len(df_or) < 25:
        return ""

    df_or["NR4"] = (
        df_or["OR_Size"]
        == df_or["OR_Size"].rolling(window=4, min_periods=4).min()
    )
    df_or["NR7"] = (
        df_or["OR_Size"]
        == df_or["OR_Size"].rolling(window=7, min_periods=7).min()
    )
    df_or["NR21"] = (
        df_or["OR_Size"]
        == df_or["OR_Size"].rolling(window=21, min_periods=21).min()
    )

    latest = df_or.iloc[-1]

    if bool(latest["NR21"]):
        return "[NR21]"
    if bool(latest["NR7"]):
        return "[NR7]"
    if bool(latest["NR4"]):
        return "[NR4]"
    return ""


# ============================================================
# SCANNER ENGINE
# ============================================================
def active_timeframes() -> List[Tuple[str, bool]]:
    return [
        (tf1, tf1_on),
        (tf2, tf2_on),
        (tf3, tf3_on),
        (tf4, tf4_on),
    ]


def all_unique_instruments() -> Dict[str, str]:
    """
    Map OANDA instrument -> preferred display name.
    Fetch each unique OANDA instrument only once per refresh cycle.
    """
    out = {}
    for items in group_tickers.values():
        for display, inst in items:
            out.setdefault(inst, display)
    return out


def build_market_snapshot(
    token: str,
    env: str,
) -> Tuple[
    Dict[str, pd.DataFrame],
    Dict[Tuple[str, str], pd.DataFrame],
    Dict[str, str],
]:
    m5_map: Dict[str, pd.DataFrame] = {}
    htf_map: Dict[Tuple[str, str], pd.DataFrame] = {}
    errors: Dict[str, str] = {}

    instruments = list(all_unique_instruments().keys())

    # Deduplicate selected timeframes too.
    selected_tfs = []
    for tf, enabled in active_timeframes():
        if enabled and tf not in selected_tfs:
            selected_tfs.append(tf)

    for instrument in instruments:
        df_m5, err = fetch_live_m5(instrument, token, env)
        if err:
            errors[f"{instrument}|M5"] = err
        elif df_m5 is not None:
            m5_map[instrument] = df_m5

        for tf in selected_tfs:
            df_htf, err = fetch_htf_data(instrument, tf, token, env)
            if err:
                errors[f"{instrument}|{tf}"] = err
            elif df_htf is not None:
                htf_map[(instrument, tf)] = df_htf

    return m5_map, htf_map, errors


def get_group_sweep_df(
    tickers_to_scan,
    or_start_h: int,
    or_dur_mins: int,
    m5_map: Dict[str, pd.DataFrame],
    htf_map: Dict[Tuple[str, str], pd.DataFrame],
) -> Tuple[pd.DataFrame, List[dict]]:
    rows = []
    debug_rows = []

    for display_name, instrument in tickers_to_scan:
        df_m5 = m5_map.get(instrument)

        row = {"Ticker": display_name}
        tf_results = []

        configs = [
            ("TF 1", tf1, tf1_on),
            ("TF 2", tf2, tf2_on),
            ("TF 3", tf3, tf3_on),
            ("TF 4", tf4, tf4_on),
        ]

        for label, tf, enabled in configs:
            col_name = f"{label} ({tf})"

            if not enabled:
                row[col_name] = "N/A"
                continue

            df_htf = htf_map.get((instrument, tf))
            sweep_str, signal, debug = detect_sweep(
                instrument,
                tf,
                df_m5,
                df_htf,
            )
            row[col_name] = sweep_str
            tf_results.append((col_name, sweep_str, signal))
            debug_rows.append(
                {
                    "Ticker": display_name,
                    "Instrument": instrument,
                    "Column": col_name,
                    **debug,
                }
            )

        # Append OR/NR to TF1 as in the original dashboard.
        nr_label = get_or_nr_status_from_m5(
            df_m5=df_m5,
            instrument=instrument,
            or_start_h=or_start_h,
            or_dur_mins=or_dur_mins,
        )

        tf1_col = f"TF 1 ({tf1})"
        if tf1_on and nr_label:
            existing = str(row.get(tf1_col, ""))
            if existing and existing not in ("N/A", "⚠️ DATA"):
                row[tf1_col] = f"{existing} {nr_label}"
            elif existing == "⚠️ DATA":
                row[tf1_col] = f"{existing} {nr_label}"
            else:
                row[tf1_col] = nr_label

        if show_data_age:
            if df_m5 is not None and not df_m5.empty:
                row["M5 Age"] = format_age(df_m5.index[-1])
            else:
                row["M5 Age"] = "NO DATA"

        rows.append(row)

    return pd.DataFrame(rows), debug_rows


# ============================================================
# STYLING
# ============================================================
def style_row(row: pd.Series):
    styles = [""] * len(row)

    for i, col in enumerate(row.index):
        val = str(row[col])

        if "⚠️ DATA" in val or "NO DATA" in val:
            styles[i] = (
                "background-color: #7a3e00; "
                "color: white; font-weight: bold;"
            )
            continue

        if "🔺" in val or "🔻" in val:
            styles[i] = "font-weight: bold;"
            continue

        if "🔴" in val or "🟢" in val:
            matches = re.findall(r"\(([\d.]+)\s+", val)
            min_dist = min([float(x) for x in matches], default=999999)

            if min_dist < float(highlight_distance):
                if "🔴" in val and "🟢" not in val:
                    styles[i] = (
                        "background-color: #ff4d4d; "
                        "color: white; font-weight: bold;"
                    )
                elif "🟢" in val and "🔴" not in val:
                    styles[i] = (
                        "background-color: #00cc66; "
                        "color: black; font-weight: bold;"
                    )
                else:
                    styles[i] = "font-weight: bold;"
            else:
                styles[i] = "font-weight: bold;"

        elif "NR" in val:
            styles[i] = "font-weight: bold;"

    return styles


# ============================================================
# DASHBOARD
# ============================================================
active_refresh_rate = run_interval if auto_refresh_on else None


@st.fragment(run_every=active_refresh_rate)
def render_sweep_dashboard():
    if not api_token:
        st.warning(
            "⚠️ OANDA API token not found. "
            "Add `oanda_api_token` to Streamlit Secrets."
        )
        return

    refresh_started = utc_now()
    or_start_hour, current_session_name = get_current_session_info()

    with st.spinner("Fetching fresh OANDA market data..."):
        m5_map, htf_map, fetch_errors = build_market_snapshot(
            api_token,
            oanda_env,
        )

    # Determine newest and oldest latest-M5 timestamps across instruments.
    latest_times = [
        df.index[-1]
        for df in m5_map.values()
        if df is not None and not df.empty
    ]

    if latest_times:
        newest_m5 = max(latest_times)
        oldest_m5 = min(latest_times)
        max_data_age = format_age(oldest_m5)
        newest_age = format_age(newest_m5)
    else:
        newest_m5 = None
        oldest_m5 = None
        max_data_age = "N/A"
        newest_age = "N/A"

    st.caption(
        f"⏱️ Dashboard refresh UTC: "
        f"{refresh_started.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Newest completed M5 age: {newest_age} | "
        f"Oldest instrument M5 age: {max_data_age} | "
        f"Active Session: {current_session_name} "
        f"({or_duration_mins}m OR-NR tracking)"
    )

    if fetch_errors:
        st.warning(
            f"⚠️ {len(fetch_errors)} market-data request(s) failed. "
            "Affected cells are marked as data unavailable."
        )

    group_items = list(group_tickers.items())
    all_debug_rows = []

    for i in range(0, len(group_items), 2):
        cols = st.columns(2)

        with cols[0]:
            group_name, tickers = group_items[i]
            st.markdown(f"##### 💱 {group_name} Group")

            df_group, dbg = get_group_sweep_df(
                tickers,
                or_start_hour,
                or_duration_mins,
                m5_map,
                htf_map,
            )
            all_debug_rows.extend(dbg)

            if not df_group.empty:
                st.table(df_group.style.apply(style_row, axis=1))

        if i + 1 < len(group_items):
            with cols[1]:
                group_name, tickers = group_items[i + 1]
                st.markdown(f"##### 💱 {group_name} Group")

                df_group, dbg = get_group_sweep_df(
                    tickers,
                    or_start_hour,
                    or_duration_mins,
                    m5_map,
                    htf_map,
                )
                all_debug_rows.extend(dbg)

                if not df_group.empty:
                    st.table(df_group.style.apply(style_row, axis=1))

        st.markdown("---")

    if show_debug:
        with st.expander("Debug: current HTF period / key levels / API errors"):
            if fetch_errors:
                st.markdown("**Fetch errors**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"Request": key, "Error": value}
                            for key, value in fetch_errors.items()
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            if all_debug_rows:
                debug_df = pd.DataFrame(all_debug_rows)
                preferred_cols = [
                    "Ticker",
                    "Instrument",
                    "Column",
                    "tf",
                    "current_start",
                    "key_high",
                    "key_low",
                    "period_high",
                    "period_low",
                    "latest_m5_close",
                    "latest_m5_time",
                    "error",
                ]
                debug_df = debug_df[
                    [c for c in preferred_cols if c in debug_df.columns]
                ]
                st.dataframe(
                    debug_df,
                    use_container_width=True,
                    hide_index=True,
                )


render_sweep_dashboard()
