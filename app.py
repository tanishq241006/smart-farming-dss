"""Starter dashboard for the Smart Farming Decision Support System."""

from io import BytesIO
from pathlib import Path
import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "CROP DATA.csv"
PRIOR_DAY_DATA = ROOT / "CROP DATA 2026-10-14.csv"
USER_DB = ROOT / "app_users.sqlite3"
PASSWORD_ROUNDS = 310_000

st.set_page_config(page_title="Smart Farming DSS", page_icon="🌾", layout="wide")


def apply_green_theme() -> None:
    """Use the forest green, leaf green, mint, and warm gold from the project deck."""
    st.markdown(
        """
        <style>
        :root {
            --forest: #1B4332;
            --leaf: #40916C;
            --leaf-deep: #245C43;
            --mint: #CFE3D6;
            --mist: #F2F8F3;
            --gold: #E9C46A;
            --ink: #18352A;
            --muted: #5C7165;
        }
        .stApp {
            background:
                radial-gradient(ellipse at 10% 0%, rgba(207, 227, 214, .55), transparent 35%),
                linear-gradient(135deg, #F7FBF7 0%, #EEF6F0 55%, #F8FAF5 100%);
            color: var(--ink);
        }
        [data-testid="stHeader"] { background: rgba(247, 251, 247, .88); }
        .main .block-container { max-width: 1180px; padding-top: 2.4rem; padding-bottom: 3rem; }
        h1, h2, h3 { color: var(--forest); letter-spacing: -.025em; }
        p, label, [data-testid="stCaptionContainer"] { color: var(--muted); }
        section[data-testid="stSidebar"] { background: #EAF3EC; border-right: 1px solid #D7E6DA; }
        section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 { color: var(--forest); }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #FFFFFF;
            border: 1px solid #C7DCCB;
            border-radius: 24px;
            box-shadow: 0 22px 60px rgba(27, 67, 50, .16);
        }
        div[data-testid="stTextInput"] input {
            border-radius: 11px;
            border-color: #C7D9CC;
            background: #FBFDFC;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: var(--leaf);
            box-shadow: 0 0 0 2px rgba(64, 145, 108, .16);
        }
        .stButton button[kind="primaryFormSubmit"],
        .stButton button[kind="primary"], button[kind="primary"] {
            background: var(--forest);
            border: 1px solid var(--forest);
            border-radius: 11px;
            color: white;
            font-weight: 650;
            transition: background .15s ease, transform .15s ease, box-shadow .15s ease;
        }
        .stButton button[kind="primaryFormSubmit"]:hover,
        .stButton button[kind="primary"]:hover, button[kind="primary"]:hover {
            background: var(--leaf-deep);
            border-color: var(--leaf-deep);
            box-shadow: 0 7px 18px rgba(27, 67, 50, .18);
            transform: translateY(-1px);
        }
        div[data-testid="stTabs"] button[role="tab"] { color: var(--muted); }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            color: var(--forest);
            border-bottom-color: var(--leaf);
        }
        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: var(--leaf); }
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, .78);
            border: 1px solid #DDE9DF;
            border-radius: 16px;
            padding: 1rem 1.15rem;
        }
        div[data-testid="stMetricLabel"] p { color: var(--muted); }
        div[data-testid="stMetricValue"] { color: var(--forest); }
        [data-testid="stDataFrame"] { border: 1px solid #DDE9DF; border-radius: 12px; overflow: hidden; }
        .login-mark {
            width: 62px; height: 62px; margin: 0 auto 1rem; border-radius: 20px;
            display: grid; place-items: center; color: var(--forest); font-size: 31px;
            background: linear-gradient(145deg, #E5F2E8, #CFE3D6);
            border: 1px solid #C8DDCD;
        }
        .login-eyebrow {
            color: var(--leaf); font-size: .73rem; font-weight: 750;
            letter-spacing: .13em; text-align: center; margin: 0 0 .5rem;
        }
        .login-note {
            color: var(--muted); font-size: .88rem; text-align: center;
            line-height: 1.55; margin: -.3rem 0 1.2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_user_store() -> None:
    """Create the local account table on first run."""
    with sqlite3.connect(USER_DB) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                password_salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS farmer_profiles (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                state TEXT NOT NULL,
                district TEXT NOT NULL,
                crop TEXT NOT NULL,
                farm_size_acres REAL NOT NULL,
                irrigation TEXT NOT NULL,
                soil_type TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE
            )"""
        )


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ROUNDS)


def create_account(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if len(username) < 3 or len(username) > 40:
        return False, "Choose a username between 3 and 40 characters."
    if not all(char.isalnum() or char in "._-" for char in username):
        return False, "Use only letters, numbers, periods, underscores, or hyphens in the username."
    if len(password) < 8:
        return False, "Use a password with at least 8 characters."

    salt = secrets.token_bytes(16)
    password_hash = hash_password(password, salt)
    try:
        with sqlite3.connect(USER_DB) as connection:
            connection.execute(
                "INSERT INTO users (username, password_salt, password_hash) VALUES (?, ?, ?)",
                (username, salt, password_hash),
            )
    except sqlite3.IntegrityError:
        return False, "That username is already registered. Try signing in instead."
    return True, username


def authenticate(username: str, password: str) -> bool:
    with sqlite3.connect(USER_DB) as connection:
        row = connection.execute(
            "SELECT username, password_salt, password_hash FROM users WHERE username = ? COLLATE NOCASE",
            (username.strip(),),
        ).fetchone()
    if row is None:
        return False
    stored_username, salt, stored_hash = row
    candidate_hash = hash_password(password, salt)
    if not hmac.compare_digest(candidate_hash, stored_hash):
        return False
    st.session_state["authenticated_user"] = stored_username
    return True


def get_farmer_profile(username: str) -> dict | None:
    with sqlite3.connect(USER_DB) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM farmer_profiles WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    return dict(row) if row else None


def save_farmer_profile(username: str, profile: dict) -> None:
    with sqlite3.connect(USER_DB) as connection:
        connection.execute(
            """INSERT INTO farmer_profiles
               (username, state, district, crop, farm_size_acres, irrigation, soil_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(username) DO UPDATE SET state=excluded.state, district=excluded.district,
               crop=excluded.crop, farm_size_acres=excluded.farm_size_acres,
               irrigation=excluded.irrigation, soil_type=excluded.soil_type,
               updated_at=CURRENT_TIMESTAMP""",
            (username, profile["state"], profile["district"], profile["crop"],
             profile["farm_size_acres"], profile["irrigation"], profile["soil_type"]),
        )


def render_farmer_setup(username: str, dataframe: pd.DataFrame, existing: dict | None = None) -> None:
    """Collect a small profile before opening the personalized dashboard."""
    st.title("Let’s set up your farm profile")
    st.write("A few details help us start with the right crop, local mandi prices, and weather location.")
    states = sorted(dataframe["State"].dropna().unique())
    crops = sorted(dataframe["Commodity"].dropna().unique())
    if not states or not crops:
        st.error("The bundled crop dataset is missing state or crop options, so a farm profile cannot be created.")
        return

    def reset_profile_district() -> None:
        selected_state = st.session_state.get("profile_state")
        state_districts = sorted(dataframe.loc[dataframe["State"] == selected_state, "District"].dropna().astype(str).unique())
        st.session_state["profile_district"] = state_districts[0] if state_districts else ""

    default_state = existing["state"] if existing and existing["state"] in states else states[0]
    if st.session_state.get("profile_state") not in states:
        st.session_state["profile_state"] = default_state
    state = st.selectbox("Your state", states, key="profile_state", on_change=reset_profile_district)
    districts = sorted(dataframe.loc[dataframe["State"] == state, "District"].dropna().astype(str).unique())
    if not districts:
        st.warning("No districts are available for this state in the bundled mandi dataset.")
        return
    default_district = existing["district"] if existing and existing["district"] in districts else districts[0]
    if st.session_state.get("profile_district") not in districts:
        st.session_state["profile_district"] = default_district
    with st.container(border=True):
        col1, col2 = st.columns(2)
        district = col2.selectbox("Your district", districts, key="profile_district")
        crop_index = crops.index(existing["crop"]) if existing and existing["crop"] in crops else 0
        crop = col1.selectbox("Main crop you want to track", crops, index=crop_index, key="profile_crop")
        farm_size = col2.number_input("Farm size (acres)", min_value=0.1, max_value=100000.0,
                                      value=float(existing["farm_size_acres"]) if existing else 1.0, step=0.5)
        irrigation_options = ["Rainfed", "Some irrigation", "Reliable irrigation"]
        soil_options = ["Not sure", "Sandy", "Loamy", "Clay", "Black", "Alluvial", "Red", "Other"]
        irrigation_index = irrigation_options.index(existing["irrigation"]) if existing and existing["irrigation"] in irrigation_options else 0
        soil_index = soil_options.index(existing["soil_type"]) if existing and existing["soil_type"] in soil_options else 0
        irrigation = col1.selectbox("Water access", irrigation_options, index=irrigation_index)
        soil_type = col2.selectbox("Soil type (if known)", soil_options, index=soil_index)
        submitted = st.button("Save profile and continue", type="primary", use_container_width=True)
    if submitted:
        save_farmer_profile(username, {
            "state": state, "district": district, "crop": crop, "farm_size_acres": farm_size,
            "irrigation": irrigation, "soil_type": soil_type,
        })
        st.session_state.pop("editing_profile", None)
        st.rerun()
    st.caption("Your profile is stored locally on this device. You can change it later from the sidebar.")


@st.cache_data
def load_data(file_bytes: bytes | None, default_path: str) -> pd.DataFrame:
    if file_bytes is not None:
        data = pd.read_csv(BytesIO(file_bytes))
    else:
        data = pd.read_csv(default_path)

    data = data.rename(
        columns={
            "Min_x0020_Price": "Min Price",
            "Max_x0020_Price": "Max Price",
            "Modal_x0020_Price": "Modal Price",
        }
    )
    required = {"State", "District", "Market", "Commodity", "Arrival_Date", "Modal Price"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    data["Arrival_Date"] = pd.to_datetime(data["Arrival_Date"], dayfirst=True, errors="coerce")
    for column in ("Min Price", "Max Price", "Modal Price"):
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["Arrival_Date", "Modal Price", "Commodity", "Market"])


@st.cache_data(ttl=900, show_spinner=False)
def get_weather(place: str) -> tuple[dict, dict]:
    """Resolve a district and return current conditions plus a five-day forecast."""
    geo_query = urlencode({"name": place, "count": 1, "language": "en", "format": "json", "countryCode": "IN"})
    with urlopen(f"https://geocoding-api.open-meteo.com/v1/search?{geo_query}", timeout=12) as response:
        locations = json.loads(response.read().decode("utf-8")).get("results", [])
    if not locations:
        raise ValueError(f"Could not find coordinates for {place}.")
    location = locations[0]
    weather_query = urlencode({
        "latitude": location["latitude"], "longitude": location["longitude"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
        "forecast_days": 5, "timezone": "auto",
    })
    with urlopen(f"https://api.open-meteo.com/v1/forecast?{weather_query}", timeout=12) as response:
        forecast = json.loads(response.read().decode("utf-8"))
    return location, forecast


def _mandi_api_get(path: str, params: dict | None = None) -> dict:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(f"https://mandi-api.onrender.com/v1/{path}{query}", headers={"User-Agent": "SmartFarmingDSS/1.0"})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("success", False):
        raise ValueError(payload.get("message", f"Mandi API request failed: {path}"))
    return payload


@st.cache_data(ttl=21600, show_spinner=False)
def get_mandi_api_states() -> list[str]:
    return _mandi_api_get("states").get("data", [])


@st.cache_data(ttl=21600, show_spinner=False)
def get_mandi_api_commodities(state: str) -> list[str]:
    return _mandi_api_get("commodities", {"state": state}).get("data", [])


@st.cache_data(ttl=21600, show_spinner=False)
def get_mandi_api_markets(state: str) -> list[dict]:
    return _mandi_api_get("markets", {"state": state}).get("data", [])


def normalize_mandi_records(records: list[dict]) -> pd.DataFrame:
    prices = pd.DataFrame(records).rename(columns={
        "state": "State", "district": "District", "market": "Market",
        "commodity": "Commodity", "arrival_date": "Arrival Date",
        "min_price": "Min Price", "max_price": "Max Price", "modal_price": "Modal Price",
        "variety": "Variety", "grade": "Grade", "fetched_at": "Fetched At",
    })
    if not prices.empty:
        prices["Arrival Date"] = pd.to_datetime(prices["Arrival Date"], errors="coerce")
        if "Fetched At" in prices:
            prices["Fetched At"] = pd.to_datetime(prices["Fetched At"], errors="coerce")
        for column in ("Min Price", "Max Price", "Modal Price"):
            if column in prices:
                prices[column] = pd.to_numeric(prices[column], errors="coerce")
    return prices


@st.cache_data(ttl=300, show_spinner=False)
def get_mandi_api_prices(commodity: str, state: str, market: str | None = None,
                         variety: str | None = None, report_date: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Fetch current and recent mandi reports from the public mandi-api service."""
    params = {"state": state, "commodity": commodity}
    if market:
        params["market"] = market
    if variety:
        params["variety"] = variety
    if report_date:
        params["date"] = report_date
    payload = _mandi_api_get("prices", params)
    return normalize_mandi_records(payload.get("data", [])), payload.get("meta", {})


@st.cache_data(ttl=900, show_spinner=False)
def get_mandi_api_history(state: str, commodity: str, market: str | None,
                          from_date: str, to_date: str) -> tuple[pd.DataFrame, dict]:
    params = {"state": state, "commodity": commodity, "from": from_date, "to": to_date}
    if market:
        params["market"] = market
    payload = _mandi_api_get("prices/history", params)
    rows = payload.get("data", [])
    history = pd.DataFrame(rows).rename(columns={
        "arrival_date": "Arrival Date", "avg_modal_price": "Modal Price",
        "avg_min_price": "Min Price", "avg_max_price": "Max Price",
        "modal_price": "Modal Price", "min_price": "Min Price", "max_price": "Max Price",
        "data_points": "Market records",
    })
    if not history.empty:
        history["Arrival Date"] = pd.to_datetime(history["Arrival Date"], errors="coerce")
        for column in ("Modal Price", "Min Price", "Max Price", "Market records"):
            if column in history:
                history[column] = pd.to_numeric(history[column], errors="coerce")
    return history, payload.get("meta", {})


def weather_description(code: int) -> str:
    """Translate common WMO weather codes to short labels."""
    if code == 0:
        return "Clear sky"
    if code in (1, 2, 3):
        return "Mainly clear" if code == 1 else "Partly cloudy" if code == 2 else "Overcast"
    if code in (45, 48):
        return "Fog"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "Rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return "Conditions unavailable"


def render_weather(dataframe: pd.DataFrame, selected_states: list[str], profile: dict) -> None:
    st.subheader("Local weather forecast")
    states = sorted(selected_states)
    if not states:
        st.info("Select a state and district in the sidebar to view the local forecast.")
        return
    default_state = profile["state"] if profile["state"] in states else states[0]
    state = st.selectbox("Weather location · state", states, index=states.index(default_state), key="weather_state")
    available_districts = sorted(dataframe.loc[dataframe["State"] == state, "District"].dropna().unique())
    if not available_districts:
        st.info("No districts are listed for this state in the selected crop data.")
        return
    default_district = profile["district"] if profile["district"] in available_districts else available_districts[0]
    if st.session_state.get("weather_district") not in available_districts:
        st.session_state["weather_district"] = default_district
    district = st.selectbox("Weather location · district", available_districts, key="weather_district")
    place = f"{district}, {state}, India"
    try:
        location, data = get_weather(place)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        st.warning(f"Weather is temporarily unavailable: {exc}")
        return
    current = data.get("current", {})
    st.caption(f"{location.get('name', district)}, {location.get('admin1', state)} · Open-Meteo · updated {current.get('time', 'recently')}")
    cols = st.columns(4)
    cols[0].metric("Conditions", weather_description(int(current.get("weather_code", -1))))
    cols[1].metric("Temperature", f"{current.get('temperature_2m', '—')} °C")
    cols[2].metric("Humidity", f"{current.get('relative_humidity_2m', '—')}%")
    cols[3].metric("Rain now", f"{current.get('precipitation', '—')} mm")
    daily = data.get("daily", {})
    forecast_df = pd.DataFrame({
        "Date": daily.get("time", []),
        "Conditions": [weather_description(int(code)) for code in daily.get("weather_code", [])],
        "Low (°C)": daily.get("temperature_2m_min", []),
        "High (°C)": daily.get("temperature_2m_max", []),
        "Rain chance (%)": daily.get("precipitation_probability_max", []),
        "Rain (mm)": daily.get("precipitation_sum", []),
    })
    st.dataframe(forecast_df, use_container_width=True, hide_index=True)
    rain_next_days = sum(float(amount or 0) for amount in daily.get("precipitation_sum", [])[:3])
    if rain_next_days >= 10:
        st.info(f"Farm note for your {profile['irrigation'].lower()} setup: around {rain_next_days:.0f} mm of rain is forecast over the next three days. Check local field conditions and the forecast again before planning irrigation or field work.")
    elif profile["irrigation"] == "Rainfed":
        st.info("Farm note: no substantial rain appears in this three-day forecast. Keep checking local forecasts; this is not a crop water requirement estimate.")
    else:
        st.caption(f"Farm context: {profile['farm_size_acres']:g} acres · {profile['irrigation']} · soil listed as {profile['soil_type']}.")


@st.fragment(run_every=300)
def render_live_price_feed(commodity: str, commodity_options: list[str], profile: dict) -> None:
    """Refresh price reports every five minutes and use the API's own lookup/history endpoints."""
    st.subheader("Latest published mandi prices")
    st.caption("Mandi API · checked every 5 minutes · prices change when new mandi reports are published.")
    if st.button("Refresh now", key="refresh_prices"):
        get_mandi_api_states.clear()
        get_mandi_api_commodities.clear()
        get_mandi_api_markets.clear()
        get_mandi_api_prices.clear()
        get_mandi_api_history.clear()
    try:
        api_states = get_mandi_api_states()
        if not api_states:
            st.warning("The Mandi API did not return its supported state list.")
            return
        preferred_state = profile["state"] if profile["state"] in api_states else ("Maharashtra" if "Maharashtra" in api_states else api_states[0])
        live_state = st.selectbox("Price report state", api_states, index=api_states.index(preferred_state), key="live_api_state")

        api_commodities = get_mandi_api_commodities(live_state)
        commodity_choices = sorted(set(api_commodities) | set(commodity_options))
        preferred_crop = commodity if commodity in commodity_choices else (api_commodities[0] if api_commodities else commodity_choices[0])
        live_commodity = st.selectbox("Crop / commodity", commodity_choices,
                                      index=commodity_choices.index(preferred_crop), key="live_api_commodity")
        if live_commodity not in api_commodities:
            st.caption("This crop is from your local dataset; it is not in the API's current commodity list. The price endpoint will still be queried for it.")

        market_rows = get_mandi_api_markets(live_state)
        district_names = sorted({str(row.get("district", "")).strip() for row in market_rows if row.get("district")})
        district_default = profile["district"] if profile["district"] in district_names else "All districts"
        district_options = ["All districts"] + district_names
        district_key = "live_api_district"
        if st.session_state.get(district_key) not in district_options:
            st.session_state[district_key] = district_default
        live_district = st.selectbox("District", district_options, key=district_key)
        eligible_markets = [row for row in market_rows if live_district == "All districts" or str(row.get("district", "")).strip() == live_district]
        market_values = list(dict.fromkeys(str(row.get("market", "")) for row in eligible_markets if row.get("market")))
        market_labels = {str(row.get("market", "")): f"{str(row.get('market', '')).strip()} · {str(row.get('district', '')).strip()}" for row in eligible_markets if row.get("market")}
        market_options = [None] + market_values
        if st.session_state.get("live_api_market") not in market_options:
            st.session_state["live_api_market"] = None
        live_market = st.selectbox("Mandi", market_options, format_func=lambda value: "All mandis" if value is None else market_labels.get(value, value.strip()), key="live_api_market")

        initial_prices, _ = get_mandi_api_prices(live_commodity, live_state, market=live_market)
        if live_district != "All districts":
            initial_prices = initial_prices[initial_prices["District"].astype(str).str.strip() == live_district]
        varieties = sorted(initial_prices["Variety"].dropna().astype(str).unique()) if "Variety" in initial_prices else []
        variety_options = ["All varieties"] + varieties
        if st.session_state.get("live_api_variety") not in variety_options:
            st.session_state["live_api_variety"] = "All varieties"
        live_variety = st.selectbox("Variety", variety_options, key="live_api_variety")
        date_values = sorted(initial_prices["Arrival Date"].dropna().dt.strftime("%Y-%m-%d").unique(), reverse=True) if not initial_prices.empty else []
        date_options = ["Latest available"] + date_values
        if st.session_state.get("live_api_date") not in date_options:
            st.session_state["live_api_date"] = "Latest available"
        live_date = st.selectbox("Arrival date", date_options, key="live_api_date")
        selected_date = None if live_date == "Latest available" else live_date
        live_prices, meta = get_mandi_api_prices(
            live_commodity, live_state, market=live_market,
            variety=None if live_variety == "All varieties" else live_variety,
            report_date=selected_date,
        )
        if live_district != "All districts":
            live_prices = live_prices[live_prices["District"].astype(str).str.strip() == live_district]
        source_name = "mandi-api.onrender.com"

        st.markdown("#### Price history")
        if not initial_prices.empty:
            last_report = initial_prices["Arrival Date"].max().date()
            first_report = initial_prices["Arrival Date"].min().date()
        else:
            last_report = datetime.now().date()
            first_report = last_report - timedelta(days=30)
        range_start = max(first_report, last_report - timedelta(days=30))
        range_value = st.date_input(
            "History date range", value=(range_start, last_report),
            key=f"live_history_range_{live_state}_{live_commodity}",
        )
        if isinstance(range_value, tuple) and len(range_value) == 2:
            from_date, to_date = range_value
            if from_date and to_date:
                history, history_meta = get_mandi_api_history(
                    live_state, live_commodity, live_market, from_date.isoformat(), to_date.isoformat()
                )
                if not history.empty:
                    history_title = f"{live_commodity} price history · {live_market.strip() if live_market else live_state + ' average'}"
                    history_chart = px.line(history, x="Arrival Date", y="Modal Price", markers=True,
                                            title=history_title, hover_data=[c for c in ("Min Price", "Max Price", "Market records") if c in history])
                    history_chart.update_layout(xaxis_title="Mandi report date", yaxis_title="Modal price (₹/quintal)")
                    st.plotly_chart(history_chart, use_container_width=True)
                    if history_meta.get("mode") == "STATE_AGGREGATE":
                        st.caption("State average aggregated by the API across reporting mandis.")
                else:
                    st.info("No history was returned for this crop, market, and date range.")
        st.caption(f"Source: {source_name} · checked {datetime.now().astimezone().strftime('%d %b %Y, %I:%M %p %Z')}")
        if live_prices.empty:
            st.info("No current records were returned for this crop and state. The source may not have published a report yet.")
            return
        report_date = live_prices["Arrival Date"].max() if "Arrival Date" in live_prices else None
        latest = live_prices[live_prices["Arrival Date"] == report_date].copy() if pd.notna(report_date) else live_prices.copy()
        if pd.notna(report_date):
            st.caption(f"Latest mandi arrival date: {report_date:%d %b %Y}")
        if meta.get("latest_fetched_at"):
            st.caption(f"API source last fetched: {meta['latest_fetched_at']}")
        if "Modal Price" in latest and not latest.empty:
            best = latest.loc[latest["Modal Price"].idxmax()]
            st.success(f"⭐ Highest reported price in this view: {best.get('Market', 'Market')}, {best.get('District', '')} · ₹{best['Modal Price']:,.0f}/quintal")
        st.dataframe(latest, use_container_width=True, hide_index=True)
        st.download_button(
            "Download latest mandi report (CSV)", latest.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{commodity.lower().replace(' ', '-')}-latest-mandi-prices.csv",
            mime="text/csv", key="download_live_prices",
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        st.warning(f"The selected mandi price service is temporarily unavailable: {exc}")


def build_daily_price_changes(current: pd.DataFrame, previous: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Compare like-for-like mandi, variety, and grade price reports across two dates."""
    if current.empty or previous.empty:
        return pd.DataFrame(), None
    current_date = current["Arrival_Date"].max()
    previous_date = previous[previous["Arrival_Date"] < current_date]["Arrival_Date"].max()
    if pd.isna(previous_date):
        return pd.DataFrame(), None
    current_rows = current[current["Arrival_Date"] == current_date]
    previous_rows = previous[previous["Arrival_Date"] == previous_date]
    match_keys = ["State", "District", "Market", "Commodity"]
    match_keys.extend(name for name in ("Variety", "Grade") if name in current_rows and name in previous_rows)
    latest = current_rows.groupby(match_keys, dropna=False, as_index=False)["Modal Price"].mean()
    prior = previous_rows.groupby(match_keys, dropna=False, as_index=False)["Modal Price"].mean()
    matched = latest.merge(prior, on=match_keys, suffixes=("_latest", "_previous"))
    if matched.empty:
        return pd.DataFrame(), previous_date
    matched["Change (₹/quintal)"] = matched["Modal Price_latest"] - matched["Modal Price_previous"]
    market_changes = matched.groupby(["State", "District", "Market"], as_index=False).agg(
        **{
            "Previous modal price": ("Modal Price_previous", "mean"),
            "Latest modal price": ("Modal Price_latest", "mean"),
            "Change (₹/quintal)": ("Change (₹/quintal)", "mean"),
            "Matched variety/grade rows": ("Change (₹/quintal)", "size"),
        }
    )
    market_changes["Change (%)"] = (
        market_changes["Change (₹/quintal)"] / market_changes["Previous modal price"].replace(0, pd.NA) * 100
    )
    return market_changes.sort_values("Change (₹/quintal)", ascending=False), previous_date


def render_login_page() -> None:
    left, center, right = st.columns([1, 1.8, 1], vertical_alignment="center")
    with center:
        with st.container(border=True, key="login_card"):
            st.markdown('<div class="login-mark">🌾</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-eyebrow">SMART FARMING · BETTER DECISIONS</div>', unsafe_allow_html=True)
            st.title("Welcome")
            st.markdown(
                '<div class="login-note">Sign in to compare mandi prices and explore practical farming insights.</div>',
                unsafe_allow_html=True,
            )

            sign_in, register = st.tabs(["Sign in", "Create account"])
            with sign_in:
                with st.form("sign_in_form"):
                    username = st.text_input("Username", key="sign_in_username")
                    password = st.text_input("Password", type="password", key="sign_in_password")
                    submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
                if submitted:
                    if authenticate(username, password):
                        st.rerun()
                    st.error("We couldn't sign you in with those details.")

            with register:
                with st.form("register_form"):
                    new_username = st.text_input("Choose a username", key="register_username")
                    new_password = st.text_input("Create a password", type="password", key="register_password")
                    confirm_password = st.text_input("Confirm password", type="password", key="register_confirm")
                    submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
                if submitted:
                    if new_password != confirm_password:
                        st.error("The passwords don't match.")
                    else:
                        created, message = create_account(new_username, new_password)
                        if created:
                            st.session_state["authenticated_user"] = message
                            st.rerun()
                        st.error(message)
            st.markdown(
                '<div class="login-note" style="font-size:.76rem;margin:.9rem 0 0">Your account stays on this device.</div>',
                unsafe_allow_html=True,
            )


def render_dashboard() -> None:
    user = st.session_state["authenticated_user"]
    with st.sidebar:
        st.write(f"Signed in as **{user}**")
        if st.button("Sign out", use_container_width=True):
            st.session_state.pop("authenticated_user", None)
            st.rerun()

    try:
        df = load_data(None, str(DEFAULT_DATA))
    except (OSError, pd.errors.ParserError, ValueError) as exc:
        st.error(f"Could not load the price data: {exc}")
        st.stop()

    if df.empty or df["State"].dropna().empty or df["Commodity"].dropna().empty:
        st.error("This file does not contain enough usable crop and location data to build your farm profile.")
        st.stop()
    profile = get_farmer_profile(user)
    if not profile or st.session_state.get("editing_profile", False):
        render_farmer_setup(user, df, profile)
        st.stop()

    with st.sidebar:
        st.divider()
        st.markdown("**Your farm profile**")
        st.caption(f"{profile['crop']} · {profile['district']}, {profile['state']}")
        st.caption(f"{profile['farm_size_acres']:g} acres · {profile['irrigation']} water")
        st.caption(f"Soil: {profile['soil_type']}")
        if st.button("Edit farm profile", use_container_width=True):
            st.session_state["editing_profile"] = True
            st.rerun()

    st.title(f"Good to see you, {user}")
    st.caption(f"Your dashboard is set up for **{profile['crop']}** in **{profile['district']}, {profile['state']}**.")

    st.sidebar.header("Filters")
    commodity_options = sorted(df["Commodity"].dropna().unique())
    if not commodity_options:
        st.error("No usable crop names were found in this CSV.")
        st.stop()
    crop_index = commodity_options.index(profile["crop"]) if profile["crop"] in commodity_options else 0
    selected_commodity = st.sidebar.selectbox("Crop / commodity", commodity_options, index=crop_index,
                                               help="Choose the crop to compare across mandis.")
    commodity_df = df[df["Commodity"] == selected_commodity]
    state_options = sorted(commodity_df["State"].dropna().unique())
    state_default = [profile["state"]] if profile["state"] in state_options else state_options
    selected_states = st.sidebar.multiselect("State", state_options, default=state_default)
    filtered = commodity_df[commodity_df["State"].isin(selected_states)]

    districts = sorted(filtered["District"].dropna().unique())
    district_default = [profile["district"]] if profile["district"] in districts else districts
    selected_districts = st.sidebar.multiselect("District", districts, default=district_default)
    filtered = filtered[filtered["District"].isin(selected_districts)]

    selected_varieties = None
    varieties = sorted(filtered["Variety"].dropna().unique()) if "Variety" in filtered else []
    if varieties:
        selected_varieties = st.sidebar.multiselect("Variety", varieties, default=varieties)
        filtered = filtered[filtered["Variety"].isin(selected_varieties)]

    latest_date = df["Arrival_Date"].max()
    snapshot = filtered[filtered["Arrival_Date"] == latest_date]
    market_count = snapshot["Market"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Latest data date", latest_date.strftime("%d %b %Y"))
    col2.metric("Markets in view", f"{market_count:,}")
    col3.metric("Average modal price", f"₹{snapshot['Modal Price'].mean():,.0f}" if not snapshot.empty else "—")
    col4.metric("Records in view", f"{len(snapshot):,}")

    st.subheader(f"Market comparison: {selected_commodity}")
    if snapshot.empty:
        st.info("No records match these filters. Try selecting another state or district in the sidebar.")
    else:
        price_fields = {name: (name, "mean") for name in ("Min Price", "Max Price") if name in snapshot}
        price_fields["Modal Price"] = ("Modal Price", "mean")
        compare = snapshot.groupby(["State", "District", "Market"], as_index=False).agg(**price_fields)
        compare["Modal Price"] = compare["Modal Price"].round(0)
        compare = compare.sort_values("Modal Price", ascending=False)
        high, low = compare.iloc[0], compare.iloc[-1]
        home_markets = compare[(compare["State"] == profile["state"]) & (compare["District"] == profile["district"])]
        recommendation = home_markets.iloc[0] if not home_markets.empty else high
        with st.container(border=True):
            st.markdown("### ⭐ Best mandi match for your filters")
            rec_col1, rec_col2, rec_col3 = st.columns([2, 1, 1])
            rec_col1.markdown(f"**{recommendation['Market']}**  \n{recommendation['District']}, {recommendation['State']}")
            rec_col2.metric("Reported modal price", f"₹{recommendation['Modal Price']:,.0f}/quintal")
            rec_col3.metric("Data date", latest_date.strftime("%d %b %Y"))
            if not home_markets.empty:
                st.caption(f"Highest reported price for {profile['crop']} in your home district. Compare transport, quality, and arrivals before choosing a market.")
            else:
                st.caption(f"Your home district has no matching record in this data view. Showing the highest reported price in your selected filters for {selected_commodity}. Compare transport, quality, and arrivals before choosing a market.")
            if low["Market"] != high["Market"]:
                st.caption(f"Price range in selected markets: ₹{low['Modal Price']:,.0f}–₹{high['Modal Price']:,.0f}/quintal.")
        fig = px.bar(
            compare.head(25).sort_values("Modal Price"),
            x="Market",
            y="Modal Price",
            color="State",
            color_discrete_sequence=["#1B4332", "#40916C", "#74A892", "#A8CDB4", "#E9C46A"],
            hover_data=[name for name in ("District", "Min Price", "Max Price") if name in compare],
            title="25 highest reported market prices (₹ per quintal)",
        )
        fig.update_layout(xaxis_title="Modal price (₹/quintal)", yaxis_title="Market", showlegend=True)
        fig.update_traces(orientation="h")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(compare, use_container_width=True, hide_index=True, height=420)
        st.download_button(
            "Download filtered market comparison (CSV)",
            compare.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{selected_commodity.lower().replace(' ', '-')}-market-comparison.csv",
            mime="text/csv",
        )

    previous_data = df if df["Arrival_Date"].nunique() > 1 else None
    if previous_data is None and PRIOR_DAY_DATA.exists():
        try:
            previous_data = load_data(None, str(PRIOR_DAY_DATA))
        except (OSError, pd.errors.ParserError, ValueError):
            previous_data = None
    if previous_data is not None:
        prior_filtered = previous_data[previous_data["Commodity"] == selected_commodity]
        prior_filtered = prior_filtered[prior_filtered["State"].isin(selected_states)]
        prior_filtered = prior_filtered[prior_filtered["District"].isin(selected_districts)]
        if selected_varieties is not None and "Variety" in prior_filtered:
            prior_filtered = prior_filtered[prior_filtered["Variety"].isin(selected_varieties)]
        changes, previous_date = build_daily_price_changes(snapshot, prior_filtered)
        if not changes.empty:
            st.subheader("Price movement since the previous report")
            st.caption(f"Compares matching market, crop, variety, and grade records from {previous_date:%d %b %Y} to {latest_date:%d %b %Y}. This is historical movement, not a forecast.")
            rising = int((changes["Change (₹/quintal)"] > 0).sum())
            falling = int((changes["Change (₹/quintal)"] < 0).sum())
            unchanged = int((changes["Change (₹/quintal)"].round(2) == 0).sum())
            move_cols = st.columns(4)
            move_cols[0].metric("Markets matched", f"{len(changes):,}")
            move_cols[1].metric("Prices higher", f"{rising:,}")
            move_cols[2].metric("Prices lower", f"{falling:,}")
            move_cols[3].metric("Unchanged", f"{unchanged:,}")
            st.dataframe(changes.round({"Previous modal price": 0, "Latest modal price": 0,
                                        "Change (₹/quintal)": 0, "Change (%)": 1}),
                         use_container_width=True, hide_index=True)
        else:
            st.info("No like-for-like market records are available to compare with the previous report.")

    with st.expander("Latest published mandi prices", expanded=True):
        render_live_price_feed(selected_commodity, commodity_options, profile)

    render_weather(df, selected_states, profile)

    st.subheader("Price history and forecasting")
    date_count = df["Arrival_Date"].nunique()
    if date_count < 2:
        st.warning(
            f"The current CSV contains {date_count} distinct date. A forecast model cannot be trained "
            "from a single-day snapshot. Add historical daily or weekly records for the same crop and "
            "market before enabling predictions."
        )
    else:
        history = filtered.groupby("Arrival_Date", as_index=False)["Modal Price"].mean()
        history_fig = px.line(
            history,
            x="Arrival_Date",
            y="Modal Price",
            markers=True,
            color_discrete_sequence=["#245C43"],
        )
        history_fig.update_traces(line={"width": 3}, marker={"size": 8})
        history_fig.update_layout(xaxis_title="Arrival date", yaxis_title="Average modal price (₹/quintal)")
        st.plotly_chart(history_fig, use_container_width=True)
        st.info("Historical trend is shown. Forecasting will be added after data quality and model evaluation.")

    st.caption("Decision support only. Market prices vary; verify current prices with the selected mandi.")


apply_green_theme()
initialize_user_store()
st.session_state.setdefault("authenticated_user", None)
if st.session_state["authenticated_user"]:
    render_dashboard()
else:
    render_login_page()
