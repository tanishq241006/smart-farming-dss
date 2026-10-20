"""AgriSense: a smart farming decision support dashboard."""

from io import BytesIO
from pathlib import Path
import hashlib
import hmac
import json
import os
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

HINDI = {
    "🌾 AgriSense": "🌾 AgriSense",
    "AgriSense helps farmers compare local mandi prices and see weather-aware planning guidance.": "AgriSense किसानों को स्थानीय मंडी भाव की तुलना और मौसम आधारित योजना संकेत देखने में मदद करता है।",
    "How to use this dashboard": "इस डैशबोर्ड का उपयोग कैसे करें",
    "How to use": "कैसे उपयोग करें",
    "Hide guide": "गाइड छिपाएँ",
    "Choose your crop, then select the state, district, and variety you want to compare.": "अपनी फसल चुनें, फिर तुलना के लिए राज्य, जिला और किस्म चुनें।",
    "Compare the reported mandi prices and the weather guide for your home district.": "मंडी के बताए भाव और अपने जिले के मौसम आधारित भाव-संकेत की तुलना करें।",
    "Review the latest published mandi reports and the historical price chart.": "मंडी की नवीनतम प्रकाशित रिपोर्ट और पुराने भावों का चार्ट देखें।",
    "Use the download button to save the market comparison as a CSV file.": "मंडी की तुलना CSV फ़ाइल में सहेजने के लिए डाउनलोड बटन दबाएँ।",
    "Weather guide": "मौसम आधारित संकेत",
    "The weather guide is an illustrative planning aid, not an official mandi quote. Check the reported price and local conditions before making a sale decision.": "मौसम आधारित संकेत केवल योजना बनाने में मदद के लिए है, यह मंडी का आधिकारिक भाव नहीं है। बिक्री का निर्णय लेने से पहले बताए गए भाव और स्थानीय स्थिति जाँचें।",
    "Language / भाषा": "भाषा / Language",
    "English": "English",
    "हिन्दी": "हिन्दी",
    "AGRISENSE · SMART FARMING": "AgriSense · स्मार्ट खेती",
    "Welcome back": "वापसी पर स्वागत है",
    "Your dashboard is set up for **{crop}** in **{district}, {state}**.": "आपका डैशबोर्ड **{district}, {state}** में **{crop}** के लिए तैयार है।",
    "🌙 Dark mode": "🌙 डार्क मोड",
    "Signed in as": "साइन इन किया है",
    "Sign out": "साइन आउट",
    "Your farm profile": "आपकी खेती की जानकारी",
    "Edit farm profile": "खेती की जानकारी बदलें",
    "acres": "एकड़",
    "water": "पानी",
    "Soil": "मिट्टी",
    "Filters": "फ़िल्टर",
    "Crop / commodity": "फसल / वस्तु",
    "Choose the crop to compare across mandis.": "मंडियों की तुलना के लिए फसल चुनें।",
    "State": "राज्य",
    "District": "जिला",
    "Variety": "किस्म",
    "Latest data date": "नवीनतम डेटा की तारीख",
    "Markets in view": "दिखाई गई मंडियाँ",
    "Average modal price": "औसत मंडी भाव",
    "Records in view": "दिखाई गई प्रविष्टियाँ",
    "Market comparison: {crop}": "मंडी तुलना: {crop}",
    "No records match these filters. Try selecting another state or district in the sidebar.": "इन फ़िल्टर से कोई रिकॉर्ड नहीं मिला। साइडबार में दूसरा राज्य या जिला चुनें।",
    "⭐ Best mandi match for your filters": "⭐ आपके फ़िल्टर के अनुसार उपयुक्त मंडी",
    "Weather-adjusted guide": "मौसम आधारित भाव-संकेत",
    "Data date": "डेटा की तारीख",
    "Based on a reported mandi price of ₹{price:,.0f}/quintal. Weather signal: {reason}. This is a planning guide, not a market quote.": "बताया गया मंडी भाव ₹{price:,.0f}/क्विंटल है। मौसम संकेत: {reason}। यह केवल योजना के लिए है, वास्तविक मंडी भाव नहीं।",
    "Your home district has no matching record in this data view. Showing the highest reported price in your selected filters for {crop}. Compare transport, quality, and arrivals before choosing a market.": "आपके गृह जिले का रिकॉर्ड इस दृश्य में नहीं है। चुने गए फ़िल्टर में {crop} का सबसे अधिक बताया गया भाव दिखाया गया है। मंडी चुनने से पहले परिवहन, गुणवत्ता और आवक की तुलना करें।",
    "Price range in selected markets: ₹{low:,.0f}–₹{high:,.0f}/quintal.": "चुनी गई मंडियों में भाव की सीमा: ₹{low:,.0f}–₹{high:,.0f}/क्विंटल।",
    "Highest mandi prices · ₹ per quintal": "सबसे अधिक मंडी भाव · ₹ प्रति क्विंटल",
    "Price guide (₹ per quintal)": "भाव संकेत (₹ प्रति क्विंटल)",
    "Weather guide applies only to your home district. Rule of thumb: +1.5% for 5–19 mm forecast rain, +3% for 20+ mm, and +1% for forecast highs of 38°C or more. Signal: {reason}. Other districts show reported prices unchanged.": "मौसम संकेत केवल आपके गृह जिले पर लागू है। अनुमानित नियम: 5–19 मिमी बारिश पर +1.5%, 20 मिमी या अधिक पर +3%, और 38°C या अधिक तापमान पर +1%। संकेत: {reason}। अन्य जिलों के बताए गए भाव नहीं बदले गए हैं।",
    "Download filtered market comparison (CSV)": "फ़िल्टर की गई मंडी तुलना डाउनलोड करें (CSV)",
    "Price movement since the previous report": "पिछली रिपोर्ट से भाव में बदलाव",
    "Compares matching market, crop, variety, and grade records from {start} to {end}. This is historical movement, not a forecast.": "{start} से {end} तक समान मंडी, फसल, किस्म और ग्रेड के रिकॉर्ड की तुलना। यह पुराने भावों का बदलाव है, पूर्वानुमान नहीं।",
    "Markets matched": "मिलान की गई मंडियाँ",
    "Prices higher": "भाव बढ़े",
    "Prices lower": "भाव घटे",
    "Unchanged": "कोई बदलाव नहीं",
    "No like-for-like market records are available to compare with the previous report.": "पिछली रिपोर्ट से तुलना के लिए समान मंडी रिकॉर्ड उपलब्ध नहीं हैं।",
    "Latest published mandi prices": "मंडी के नवीनतम प्रकाशित भाव",
    "Price history": "भावों का इतिहास",
    "Historical chart appears when multiple reporting dates are available.": "एक से अधिक रिपोर्ट तारीखें उपलब्ध होने पर पुराने भावों का चार्ट दिखेगा।",
    "Arrival date": "आवक की तारीख",
    "Modal price (₹/quintal)": "मंडी भाव (₹/क्विंटल)",
    "History date range": "इतिहास की तारीख़ सीमा",
    "Average modal price (₹/quintal)": "औसत मंडी भाव (₹/क्विंटल)",
    "Decision support only. Market prices vary; verify current prices with the selected mandi.": "यह जानकारी निर्णय में सहायता के लिए है। मंडी भाव बदलते रहते हैं; चुनी हुई मंडी से वर्तमान भाव की पुष्टि करें।",
    "Let’s set up your farm profile": "आइए, आपकी खेती की जानकारी भरें",
    "A few details help us start with the right crop, local mandi prices, and weather location.": "कुछ जानकारी से सही फसल, स्थानीय मंडी भाव और मौसम का स्थान चुनने में मदद मिलेगी।",
    "Your state": "आपका राज्य",
    "Your district": "आपका जिला",
    "Main crop you want to track": "जिस फसल के भाव देखना चाहते हैं",
    "Farm size (acres)": "खेत का आकार (एकड़)",
    "Water access": "सिंचाई की सुविधा",
    "Soil type (if known)": "मिट्टी का प्रकार (यदि पता हो)",
    "Save profile and continue": "जानकारी सहेजें और आगे बढ़ें",
    "Your profile is saved with your account. You can change it later from the sidebar.": "आपकी जानकारी खाते में सहेजी गई है। आप इसे बाद में साइडबार से बदल सकते हैं।",
    "Latest published mandi prices": "मंडी के नवीनतम प्रकाशित भाव",
    "Mandi API · checked every 5 minutes · prices change when new mandi reports are published.": "मंडी API · हर 5 मिनट में जाँच · नई मंडी रिपोर्ट आने पर भाव बदलते हैं।",
    "Refresh now": "अभी रीफ़्रेश करें",
    "Price report state": "भाव रिपोर्ट का राज्य",
    "All districts": "सभी जिले",
    "All varieties": "सभी किस्में",
    "Latest available": "नवीनतम उपलब्ध",
    "Mandi": "मंडी",
    "Price history": "भावों का इतिहास",
    "Mandi report date": "मंडी रिपोर्ट की तारीख",
    "Modal price (₹/quintal)": "मंडी भाव (₹/क्विंटल)",
    "No history was returned for this crop, market, and date range.": "इस फसल, मंडी और तारीख़ों के लिए भावों का इतिहास नहीं मिला।",
    "Latest mandi arrival date: {date}": "मंडी की नवीनतम आवक तारीख: {date}",
    "No current records were returned for this crop and state. The source may not have published a report yet.": "इस फसल और राज्य के लिए अभी रिकॉर्ड नहीं मिला। संभव है कि नई रिपोर्ट प्रकाशित न हुई हो।",
    "⭐ Highest guide in this view: {market}, {district} · ₹{price:,.0f}/quintal": "⭐ इस सूची का सबसे अधिक भाव-संकेत: {market}, {district} · ₹{price:,.0f}/क्विंटल",
    "Download latest mandi report (CSV)": "मंडी की नवीनतम रिपोर्ट डाउनलोड करें (CSV)",
    "Welcome": "स्वागत है",
    "Sign in": "साइन इन",
    "Create account": "खाता बनाएँ",
    "Username": "उपयोगकर्ता नाम",
    "Password": "पासवर्ड",
    "Choose a username": "उपयोगकर्ता नाम चुनें",
    "Create a password": "पासवर्ड बनाएँ",
    "Confirm password": "पासवर्ड की पुष्टि करें",
    "Sign in to compare mandi prices and explore practical farming insights.": "मंडी भावों की तुलना और खेती से जुड़ी उपयोगी जानकारी के लिए साइन इन करें।",
    "Your account stays on this device.": "आपका खाता इसी डिवाइस पर रहता है।",
    "We couldn't sign you in with those details.": "इन जानकारियों से साइन इन नहीं हो पाया।",
    "The passwords don't match.": "दोनों पासवर्ड मेल नहीं खाते।",
    "Choose a username between 3 and 40 characters.": "3 से 40 अक्षरों का उपयोगकर्ता नाम चुनें।",
    "Use only letters, numbers, periods, underscores, or hyphens in the username.": "उपयोगकर्ता नाम में केवल अक्षर, अंक, बिंदु, अंडरस्कोर या हाइफ़न इस्तेमाल करें।",
    "Use a password with at least 8 characters.": "कम से कम 8 अक्षरों का पासवर्ड इस्तेमाल करें।",
    "That username is already registered. Try signing in instead.": "यह उपयोगकर्ता नाम पहले से पंजीकृत है। साइन इन करने की कोशिश करें।",
    "No districts are available for this state in the bundled mandi dataset.": "इस राज्य के लिए मंडी डेटा में जिले उपलब्ध नहीं हैं।",
    "The bundled crop dataset is missing state or crop options, so a farm profile cannot be created.": "फसल डेटा में राज्य या फसल की जानकारी नहीं है, इसलिए खेती की प्रोफ़ाइल नहीं बन सकती।",
    "Weather unavailable": "मौसम की जानकारी उपलब्ध नहीं है",
    "No material rain or heat signal in the 3-day forecast": "तीन दिन के पूर्वानुमान में बारिश या गर्मी का कोई बड़ा संकेत नहीं है",
    "{rain} mm forecast rain over 3 days": "अगले 3 दिनों में {rain} मिमी बारिश का अनुमान",
    "highs up to {temperature}°C": "अधिकतम तापमान {temperature}°C तक",
    "Could not load the price data: {error}": "भाव डेटा लोड नहीं हो पाया: {error}",
    "This file does not contain enough usable crop and location data to build your farm profile.": "इस फ़ाइल में खेती की प्रोफ़ाइल के लिए पर्याप्त फसल और स्थान डेटा नहीं है।",
    "No usable crop names were found in this CSV.": "इस CSV में उपयोग योग्य फसल के नाम नहीं मिले।",
    "Market report state": "भाव रिपोर्ट का राज्य",
    "This crop is from your local dataset; it is not in the API's current commodity list. The price endpoint will still be queried for it.": "यह फसल स्थानीय डेटा में है, API की सूची में नहीं। फिर भी इसके भाव खोजे जाएँगे।",
    "The Mandi API did not return its supported state list.": "मंडी API से समर्थित राज्यों की सूची नहीं मिली।",
    "All mandis": "सभी मंडियाँ",
    "Price report state": "भाव रिपोर्ट का राज्य",
    "History date range": "इतिहास की तारीख़ सीमा",
    "Source: {source} · checked {time}": "स्रोत: {source} · जाँच का समय {time}",
    "Mandi report date": "मंडी रिपोर्ट की तारीख",
    "Mandi price history · {market}": "मंडी भावों का इतिहास · {market}",
    "State average aggregated by the API across reporting mandis.": "API ने रिपोर्ट करने वाली मंडियों का राज्य-औसत निकाला है।",
    "The selected mandi price service is temporarily unavailable: {error}": "चुनी गई मंडी भाव सेवा अभी उपलब्ध नहीं है: {error}",
    "Arrival date": "आवक की तारीख",
    "Good to see you, {user}": "वापसी पर स्वागत है, {user}",
    "Market prices vary; verify current prices with the selected mandi.": "मंडी भाव बदलते रहते हैं; चुनी हुई मंडी से वर्तमान भाव की पुष्टि करें।",
    "Rainfed": "वर्षा आधारित", "Some irrigation": "कुछ सिंचाई", "Reliable irrigation": "नियमित सिंचाई",
    "Not sure": "पता नहीं", "Sandy": "रेतीली", "Loamy": "दोमट", "Clay": "चिकनी मिट्टी",
    "Black": "काली मिट्टी", "Alluvial": "जलोढ़ मिट्टी", "Red": "लाल मिट्टी", "Other": "अन्य",
}


def tr(text: str) -> str:
    """Translate a visible English label when Hindi is selected."""
    if st.session_state.get("ui_language") == "हिन्दी":
        return HINDI.get(text, text)
    return text


def render_language_picker(container=st, show_label: bool = False) -> None:
    container.selectbox(
        "🌐 Language / भाषा", ["English", "हिन्दी"], key="ui_language",
        label_visibility="visible" if show_label else "collapsed",
    )


def render_how_to_use_box() -> None:
    """Render the farmer guide inside the dashboard's How to use popover."""
    st.markdown(f"#### {tr('How to use this dashboard')}")
    st.markdown("1. " + tr("Choose your crop, then select the state, district, and variety you want to compare."))
    st.markdown("2. " + tr("Compare the reported mandi prices and the weather guide for your home district."))
    st.markdown("3. " + tr("Review the latest published mandi reports and the historical price chart."))
    st.markdown("4. " + tr("Use the download button to save the market comparison as a CSV file."))
    st.caption(tr("The weather guide is an illustrative planning aid, not an official mandi quote. Check the reported price and local conditions before making a sale decision."))


def display_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Translate common table headings while preserving the underlying data."""
    if st.session_state.get("ui_language") != "हिन्दी":
        return frame
    hindi_columns = {
        "State": "राज्य", "District": "जिला", "Market": "मंडी", "Commodity": "फसल",
        "Arrival Date": "आवक की तारीख", "Modal Price": "मंडी भाव",
        "Min Price": "न्यूनतम भाव", "Max Price": "अधिकतम भाव",
        "Reported price (₹/quintal)": "बताया गया भाव (₹/क्विंटल)",
        "Weather-adjusted guide (₹/quintal)": "मौसम आधारित संकेत (₹/क्विंटल)",
        "Weather guide (₹/quintal)": "मौसम आधारित संकेत (₹/क्विंटल)",
        "Previous modal price": "पिछला मंडी भाव", "Latest modal price": "नवीनतम मंडी भाव",
        "Change (₹/quintal)": "बदलाव (₹/क्विंटल)", "Change (%)": "बदलाव (%)",
        "Matched variety/grade rows": "मिलान की गई किस्म/ग्रेड प्रविष्टियाँ",
        "Variety": "किस्म", "Grade": "ग्रेड", "Market records": "मंडी रिकॉर्ड",
    }
    return frame.rename(columns=hindi_columns)


def get_database_url() -> str | None:
    """Read a shared database URL from the host environment or Streamlit secrets."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    try:
        return st.secrets.get("DATABASE_URL")
    except (FileNotFoundError, RuntimeError):
        return None


def database_connection():
    """Connect to shared PostgreSQL when configured, otherwise use local SQLite."""
    database_url = get_database_url()
    if database_url:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(database_url, row_factory=dict_row)
    connection = sqlite3.connect(USER_DB)
    connection.row_factory = sqlite3.Row
    return connection


def execute(connection, query: str, params: tuple = ()):
    """Use the placeholder style required by the configured database driver."""
    if get_database_url():
        query = query.replace("?", "%s")
    return connection.execute(query, params)

st.set_page_config(page_title="AgriSense", page_icon="🌾", layout="wide")


def apply_green_theme(dark: bool = False) -> None:
    """Apply the dashboard's light or dark color palette."""
    page_bg = "#000000" if dark else "#F2F8F3"
    card_bg = "#101010" if dark else "#FFFFFF"
    ink = "#F1F1F1" if dark else "#18352A"
    muted = "#B8B8B8" if dark else "#5C7165"
    sidebar_bg = "#080808" if dark else "#EAF3EC"
    border = "#303030" if dark else "#D7E6DA"
    st.markdown(
        """
        <style>
        :root {
            --forest: #1B4332;
            --leaf: #40916C;
            --leaf-deep: #245C43;
            --mint: #CFE3D6;
            --mist: @PAGE_BG;
            --gold: #E9C46A;
            --ink: @INK;
            --muted: @MUTED;
        }
        .stApp {
            background:
                radial-gradient(ellipse at 10% 0%, rgba(64, 145, 108, .12), transparent 35%),
                linear-gradient(135deg, @PAGE_BG 0%, @PAGE_BG 100%);
            color: var(--ink);
        }
        [data-testid="stHeader"] { background: @PAGE_BG; }
        .main .block-container { max-width: 1180px; padding-top: 2.4rem; padding-bottom: 3rem; }
        .agrisense-header-brand {
            position: fixed;
            top: .42rem;
            left: calc(18rem + max(0px, (100vw - 18rem - 1180px) / 2));
            z-index: 1000002;
            color: var(--ink);
            font-size: 1.05rem;
            font-weight: 750;
            line-height: 2.5rem;
            pointer-events: none;
        }
        .st-key-header_how_to_use {
            position: fixed !important;
            top: .28rem !important;
            right: 9rem !important;
            z-index: 1000002 !important;
            width: max-content !important;
        }
        @media (max-width: 760px) {
            .agrisense-header-brand { top: 2.8rem; left: 1rem; }
            .st-key-header_how_to_use { top: 2.75rem !important; right: 1rem !important; }
        }
        h1, h2, h3 { color: var(--ink); letter-spacing: -.025em; }
        p, label, [data-testid="stCaptionContainer"] { color: var(--muted); }
        section[data-testid="stSidebar"] { background: @SIDEBAR; border-right: 1px solid @BORDER; }
        section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 { color: var(--ink); }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: @CARD;
            border: 1px solid @BORDER;
            border-radius: 24px;
            box-shadow: 0 22px 60px rgba(27, 67, 50, .16);
        }
        div[data-testid="stTextInput"] input {
            border-radius: 11px;
            border-color: #C7D9CC;
            background: @CARD;
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
            color: var(--ink);
            border-bottom-color: var(--leaf);
        }
        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: var(--leaf); }
        div[data-testid="stMetric"] {
            background: @CARD;
            border: 1px solid @BORDER;
            border-radius: 16px;
            padding: 1rem 1.15rem;
        }
        div[data-testid="stMetricLabel"] p { color: var(--muted); }
        div[data-testid="stMetricValue"] { color: var(--ink); }
        [data-testid="stDataFrame"] { border: 1px solid #DDE9DF; border-radius: 12px; overflow: hidden; }
        [data-testid="stSelectbox"] label, [data-testid="stMultiSelect"] label { color: var(--ink); }
        .stMarkdown, [data-testid="stExpander"] { color: var(--ink); }
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
        """.replace("@PAGE_BG", page_bg).replace("@CARD", card_bg).replace("@INK", ink)
        .replace("@MUTED", muted).replace("@SIDEBAR", sidebar_bg).replace("@BORDER", border),
        unsafe_allow_html=True,
    )


def initialize_user_store() -> None:
    """Create account and farmer profile tables in the configured database."""
    shared_database = bool(get_database_url())
    binary_type = "BYTEA" if shared_database else "BLOB"
    timestamp_type = "TIMESTAMPTZ" if shared_database else "TEXT"
    with database_connection() as connection:
        execute(connection,
            """CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_salt {binary_type} NOT NULL,
                password_hash {binary_type} NOT NULL,
                created_at {timestamp_type} NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""".format(binary_type=binary_type, timestamp_type=timestamp_type)
        )
        execute(connection, "CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_idx ON users (LOWER(username))")
        execute(connection,
            """CREATE TABLE IF NOT EXISTS farmer_profiles (
                username TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                district TEXT NOT NULL,
                crop TEXT NOT NULL,
                farm_size_acres REAL NOT NULL,
                irrigation TEXT NOT NULL,
                soil_type TEXT NOT NULL,
                updated_at {timestamp_type} NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE
            )""".format(timestamp_type=timestamp_type)
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
        with database_connection() as connection:
            execute(connection,
                "INSERT INTO users (username, password_salt, password_hash) VALUES (?, ?, ?)",
                (username, salt, password_hash),
            )
    except Exception as exc:
        if not isinstance(exc, sqlite3.IntegrityError) and getattr(exc, "sqlstate", None) != "23505":
            raise
        return False, "That username is already registered. Try signing in instead."
    return True, username


def authenticate(username: str, password: str) -> bool:
    with database_connection() as connection:
        row = execute(connection,
            "SELECT username, password_salt, password_hash FROM users WHERE LOWER(username) = LOWER(?)",
            (username.strip(),),
        ).fetchone()
    if row is None:
        return False
    stored_username, salt, stored_hash = row["username"], row["password_salt"], row["password_hash"]
    candidate_hash = hash_password(password, salt)
    if not hmac.compare_digest(candidate_hash, stored_hash):
        return False
    st.session_state["authenticated_user"] = stored_username
    return True


def get_farmer_profile(username: str) -> dict | None:
    with database_connection() as connection:
        row = execute(connection, "SELECT * FROM farmer_profiles WHERE LOWER(username) = LOWER(?)", (username,)).fetchone()
    return dict(row) if row else None


def save_farmer_profile(username: str, profile: dict) -> None:
    with database_connection() as connection:
        execute(connection,
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
    st.title(tr("Let’s set up your farm profile"))
    st.write(tr("A few details help us start with the right crop, local mandi prices, and weather location."))
    states = sorted(dataframe["State"].dropna().unique())
    crops = sorted(dataframe["Commodity"].dropna().unique())
    if not states or not crops:
        st.error(tr("The bundled crop dataset is missing state or crop options, so a farm profile cannot be created."))
        return

    def reset_profile_district() -> None:
        selected_state = st.session_state.get("profile_state")
        state_districts = sorted(dataframe.loc[dataframe["State"] == selected_state, "District"].dropna().astype(str).unique())
        st.session_state["profile_district"] = state_districts[0] if state_districts else ""

    default_state = existing["state"] if existing and existing["state"] in states else states[0]
    if st.session_state.get("profile_state") not in states:
        st.session_state["profile_state"] = default_state
    state = st.selectbox(tr("Your state"), states, key="profile_state", on_change=reset_profile_district)
    districts = sorted(dataframe.loc[dataframe["State"] == state, "District"].dropna().astype(str).unique())
    if not districts:
        st.warning(tr("No districts are available for this state in the bundled mandi dataset."))
        return
    default_district = existing["district"] if existing and existing["district"] in districts else districts[0]
    if st.session_state.get("profile_district") not in districts:
        st.session_state["profile_district"] = default_district
    with st.container(border=True):
        col1, col2 = st.columns(2)
        district = col2.selectbox(tr("Your district"), districts, key="profile_district")
        crop_index = crops.index(existing["crop"]) if existing and existing["crop"] in crops else 0
        crop = col1.selectbox(tr("Main crop you want to track"), crops, index=crop_index, key="profile_crop")
        farm_size = col2.number_input(tr("Farm size (acres)"), min_value=0.1, max_value=100000.0,
                                      value=float(existing["farm_size_acres"]) if existing else 1.0, step=0.5)
        irrigation_options = ["Rainfed", "Some irrigation", "Reliable irrigation"]
        soil_options = ["Not sure", "Sandy", "Loamy", "Clay", "Black", "Alluvial", "Red", "Other"]
        irrigation_index = irrigation_options.index(existing["irrigation"]) if existing and existing["irrigation"] in irrigation_options else 0
        soil_index = soil_options.index(existing["soil_type"]) if existing and existing["soil_type"] in soil_options else 0
        irrigation = col1.selectbox(tr("Water access"), irrigation_options, index=irrigation_index, format_func=tr)
        soil_type = col2.selectbox(tr("Soil type (if known)"), soil_options, index=soil_index, format_func=tr)
        submitted = st.button(tr("Save profile and continue"), type="primary", use_container_width=True)
    if submitted:
        save_farmer_profile(username, {
            "state": state, "district": district, "crop": crop, "farm_size_acres": farm_size,
            "irrigation": irrigation, "soil_type": soil_type,
        })
        st.session_state.pop("editing_profile", None)
        st.rerun()
    st.caption(tr("Your profile is saved with your account. You can change it later from the sidebar."))


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


def weather_price_factor(data: dict) -> tuple[float, str]:
    """Return a small, explainable weather scenario factor (not a market forecast)."""
    daily = data.get("daily", {})
    rain = sum(float(value or 0) for value in daily.get("precipitation_sum", [])[:3])
    high_temps = [float(value) for value in daily.get("temperature_2m_max", [])[:3] if value is not None]
    adjustment = 0.03 if rain >= 20 else 0.015 if rain >= 5 else 0.0
    reasons = [tr("{rain} mm forecast rain over 3 days").format(rain=f"{rain:.0f}")] if adjustment else []
    if high_temps and max(high_temps) >= 38:
        adjustment += 0.01
        reasons.append(tr("highs up to {temperature}°C").format(temperature=f"{max(high_temps):.0f}"))
    return 1 + adjustment, "; ".join(reasons) if reasons else tr("No material rain or heat signal in the 3-day forecast")


def get_profile_weather(profile: dict) -> tuple[dict, dict] | None:
    try:
        location, data = get_weather(f"{profile['district']}, {profile['state']}, India")
        return location, data
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None


@st.fragment(run_every=300)
def render_live_price_feed(commodity: str, commodity_options: list[str], profile: dict,
                           weather_factor: float = 1.0) -> None:
    """Refresh price reports every five minutes and use the API's own lookup/history endpoints."""
    st.subheader(tr("Latest published mandi prices"))
    st.caption(tr("Mandi API · checked every 5 minutes · prices change when new mandi reports are published."))
    if st.button(tr("Refresh now"), key="refresh_prices"):
        get_mandi_api_states.clear()
        get_mandi_api_commodities.clear()
        get_mandi_api_markets.clear()
        get_mandi_api_prices.clear()
        get_mandi_api_history.clear()
    try:
        api_states = get_mandi_api_states()
        if not api_states:
            st.warning(tr("The Mandi API did not return its supported state list."))
            return
        preferred_state = profile["state"] if profile["state"] in api_states else ("Maharashtra" if "Maharashtra" in api_states else api_states[0])
        live_state = st.selectbox(tr("Price report state"), api_states, index=api_states.index(preferred_state), key="live_api_state")

        api_commodities = get_mandi_api_commodities(live_state)
        commodity_choices = sorted(set(api_commodities) | set(commodity_options))
        preferred_crop = commodity if commodity in commodity_choices else (api_commodities[0] if api_commodities else commodity_choices[0])
        live_commodity = st.selectbox(tr("Crop / commodity"), commodity_choices,
                                      index=commodity_choices.index(preferred_crop), key="live_api_commodity")
        if live_commodity not in api_commodities:
            st.caption(tr("This crop is from your local dataset; it is not in the API's current commodity list. The price endpoint will still be queried for it."))

        market_rows = get_mandi_api_markets(live_state)
        district_names = sorted({str(row.get("district", "")).strip() for row in market_rows if row.get("district")})
        district_default = profile["district"] if profile["district"] in district_names else "All districts"
        district_options = ["All districts"] + district_names
        district_key = "live_api_district"
        if st.session_state.get(district_key) not in district_options:
            st.session_state[district_key] = district_default
        live_district = st.selectbox(tr("District"), district_options, format_func=tr, key=district_key)
        eligible_markets = [row for row in market_rows if live_district == "All districts" or str(row.get("district", "")).strip() == live_district]
        market_values = list(dict.fromkeys(str(row.get("market", "")) for row in eligible_markets if row.get("market")))
        market_labels = {str(row.get("market", "")): f"{str(row.get('market', '')).strip()} · {str(row.get('district', '')).strip()}" for row in eligible_markets if row.get("market")}
        market_options = [None] + market_values
        if st.session_state.get("live_api_market") not in market_options:
            st.session_state["live_api_market"] = None
        live_market = st.selectbox(tr("Mandi"), market_options, format_func=lambda value: tr("All mandis") if value is None else market_labels.get(value, value.strip()), key="live_api_market")

        initial_prices, _ = get_mandi_api_prices(live_commodity, live_state, market=live_market)
        if live_district != "All districts":
            initial_prices = initial_prices[initial_prices["District"].astype(str).str.strip() == live_district]
        varieties = sorted(initial_prices["Variety"].dropna().astype(str).unique()) if "Variety" in initial_prices else []
        variety_options = ["All varieties"] + varieties
        if st.session_state.get("live_api_variety") not in variety_options:
            st.session_state["live_api_variety"] = "All varieties"
        live_variety = st.selectbox(tr("Variety"), variety_options, format_func=tr, key="live_api_variety")
        date_values = sorted(initial_prices["Arrival Date"].dropna().dt.strftime("%Y-%m-%d").unique(), reverse=True) if not initial_prices.empty else []
        date_options = ["Latest available"] + date_values
        if st.session_state.get("live_api_date") not in date_options:
            st.session_state["live_api_date"] = "Latest available"
        live_date = st.selectbox(tr("Arrival date"), date_options, format_func=tr, key="live_api_date")
        selected_date = None if live_date == "Latest available" else live_date
        live_prices, meta = get_mandi_api_prices(
            live_commodity, live_state, market=live_market,
            variety=None if live_variety == "All varieties" else live_variety,
            report_date=selected_date,
        )
        if live_district != "All districts":
            live_prices = live_prices[live_prices["District"].astype(str).str.strip() == live_district]
        source_name = "mandi-api.onrender.com"

        st.markdown(f"#### {tr('Price history')}")
        if not initial_prices.empty:
            last_report = initial_prices["Arrival Date"].max().date()
            first_report = initial_prices["Arrival Date"].min().date()
        else:
            last_report = datetime.now().date()
            first_report = last_report - timedelta(days=30)
        range_start = max(first_report, last_report - timedelta(days=30))
        range_value = st.date_input(
            tr("History date range"), value=(range_start, last_report),
            key=f"live_history_range_{live_state}_{live_commodity}",
        )
        if isinstance(range_value, tuple) and len(range_value) == 2:
            from_date, to_date = range_value
            if from_date and to_date:
                history, history_meta = get_mandi_api_history(
                    live_state, live_commodity, live_market, from_date.isoformat(), to_date.isoformat()
                )
                if not history.empty:
                    history_title = tr("Mandi price history · {market}").format(
                        market=live_market.strip() if live_market else live_state + (" औसत" if st.session_state.get("ui_language") == "हिन्दी" else " average"))
                    history_chart = px.line(history, x="Arrival Date", y="Modal Price", markers=True,
                                            title=history_title, hover_data=[c for c in ("Min Price", "Max Price", "Market records") if c in history])
                    history_chart.update_layout(xaxis_title=tr("Mandi report date"), yaxis_title=tr("Modal price (₹/quintal)"),
                                                template="plotly_dark" if st.session_state.get("dark_mode") else "plotly_white")
                    st.plotly_chart(history_chart, use_container_width=True)
                    if history_meta.get("mode") == "STATE_AGGREGATE":
                        st.caption(tr("State average aggregated by the API across reporting mandis."))
                else:
                    st.info(tr("No history was returned for this crop, market, and date range."))
        checked = datetime.now().astimezone().strftime('%d %b %Y, %I:%M %p %Z')
        st.caption(tr("Source: {source} · checked {time}").format(source=source_name, time=checked))
        if live_prices.empty:
            st.info(tr("No current records were returned for this crop and state. The source may not have published a report yet."))
            return
        report_date = live_prices["Arrival Date"].max() if "Arrival Date" in live_prices else None
        latest = live_prices[live_prices["Arrival Date"] == report_date].copy() if pd.notna(report_date) else live_prices.copy()
        latest["Weather guide (₹/quintal)"] = latest["Modal Price"]
        home_district_rows = latest["District"].astype(str).str.strip().eq(profile["district"])
        if live_state == profile["state"]:
            latest.loc[home_district_rows, "Weather guide (₹/quintal)"] = (
                latest.loc[home_district_rows, "Modal Price"] * weather_factor
            ).round(0)
        if pd.notna(report_date):
            st.caption(tr("Latest mandi arrival date: {date}").format(date=f"{report_date:%d %b %Y}"))
        if "Modal Price" in latest and not latest.empty:
            best = latest.loc[latest["Weather guide (₹/quintal)"].idxmax()]
            message = tr("⭐ Highest guide in this view: {market}, {district} · ₹{price:,.0f}/quintal")
            st.success(message.format(market=best.get('Market', 'Market'), district=best.get('District', ''),
                                      price=best['Weather guide (₹/quintal)']))
        st.dataframe(display_columns(latest), use_container_width=True, hide_index=True)
        st.download_button(
            tr("Download latest mandi report (CSV)"), latest.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{commodity.lower().replace(' ', '-')}-latest-mandi-prices.csv",
            mime="text/csv", key="download_live_prices",
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        st.warning(tr("The selected mandi price service is temporarily unavailable: {error}").format(error=exc))


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
    lang_left, lang_right = st.columns([5, 1])
    with lang_right:
        render_language_picker()
    left, center, right = st.columns([1, 1.8, 1], vertical_alignment="center")
    with center:
        with st.container(border=True, key="login_card"):
            st.markdown('<div class="login-mark">🌾</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="login-eyebrow">{tr("AGRISENSE · SMART FARMING")}</div>', unsafe_allow_html=True)
            st.title(tr("Welcome"))
            st.markdown(
                f'<div class="login-note">{tr("Sign in to compare mandi prices and explore practical farming insights.")}</div>',
                unsafe_allow_html=True,
            )

            sign_in, register = st.tabs([tr("Sign in"), tr("Create account")])
            with sign_in:
                with st.form("sign_in_form"):
                    username = st.text_input(tr("Username"), key="sign_in_username")
                    password = st.text_input(tr("Password"), type="password", key="sign_in_password")
                    submitted = st.form_submit_button(tr("Sign in"), type="primary", use_container_width=True)
                if submitted:
                    if authenticate(username, password):
                        st.rerun()
                    st.error(tr("We couldn't sign you in with those details."))

            with register:
                with st.form("register_form"):
                    new_username = st.text_input(tr("Choose a username"), key="register_username")
                    new_password = st.text_input(tr("Create a password"), type="password", key="register_password")
                    confirm_password = st.text_input(tr("Confirm password"), type="password", key="register_confirm")
                    submitted = st.form_submit_button(tr("Create account"), type="primary", use_container_width=True)
                if submitted:
                    if new_password != confirm_password:
                        st.error(tr("The passwords don't match."))
                    else:
                        created, message = create_account(new_username, new_password)
                        if created:
                            st.session_state["authenticated_user"] = message
                            st.rerun()
                        st.error(tr(message))
            st.markdown(
                f'<div class="login-note" style="font-size:.76rem;margin:.9rem 0 0">{tr("Your account stays on this device.")}</div>',
                unsafe_allow_html=True,
            )


def render_dashboard() -> None:
    user = st.session_state["authenticated_user"]
    st.markdown('<div class="agrisense-header-brand">🌾 AgriSense</div>', unsafe_allow_html=True)
    with st.popover(f"📘 {tr('How to use')}", key="header_how_to_use"):
        render_how_to_use_box()
    st.subheader(tr("Good to see you, {user}").format(user=user))
    st.caption(tr("AgriSense helps farmers compare local mandi prices and see weather-aware planning guidance."))
    with st.sidebar:
        render_language_picker(show_label=True)
        st.header(tr("Filters"))
        st.session_state.setdefault("dark_mode", False)
        dark_mode = st.toggle(tr("🌙 Dark mode"), key="dark_mode")
        apply_green_theme(dark_mode)
        st.write(f"**{tr('Signed in as')}: {user}**")
        if st.button(tr("Sign out"), use_container_width=True):
            st.session_state.pop("authenticated_user", None)
            st.rerun()

    try:
        df = load_data(None, str(DEFAULT_DATA))
    except (OSError, pd.errors.ParserError, ValueError) as exc:
        st.error(tr("Could not load the price data: {error}").format(error=exc))
        st.stop()

    if df.empty or df["State"].dropna().empty or df["Commodity"].dropna().empty:
        st.error(tr("This file does not contain enough usable crop and location data to build your farm profile."))
        st.stop()
    profile = get_farmer_profile(user)
    if not profile or st.session_state.get("editing_profile", False):
        render_farmer_setup(user, df, profile)
        st.stop()
    weather_result = get_profile_weather(profile)
    weather_factor, weather_reason = weather_price_factor(weather_result[1]) if weather_result else (1.0, tr("Weather unavailable"))

    with st.sidebar:
        st.divider()
        st.markdown(f"**{tr('Your farm profile')}**")
        st.caption(f"{profile['crop']} · {profile['district']}, {profile['state']}")
        st.caption(f"{profile['farm_size_acres']:g} {tr('acres')} · {tr(profile['irrigation'])} {tr('water')}")
        st.caption(f"{tr('Soil')}: {tr(profile['soil_type'])}")
        if st.button(tr("Edit farm profile"), use_container_width=True):
            st.session_state["editing_profile"] = True
            st.rerun()

    st.caption(tr("Your dashboard is set up for **{crop}** in **{district}, {state}**.").format(
        crop=profile["crop"], district=profile["district"], state=profile["state"]))

    commodity_options = sorted(df["Commodity"].dropna().unique())
    if not commodity_options:
        st.error(tr("No usable crop names were found in this CSV."))
        st.stop()
    crop_index = commodity_options.index(profile["crop"]) if profile["crop"] in commodity_options else 0
    selected_commodity = st.sidebar.selectbox(tr("Crop / commodity"), commodity_options, index=crop_index,
                                               help=tr("Choose the crop to compare across mandis."))
    commodity_df = df[df["Commodity"] == selected_commodity]
    state_options = sorted(commodity_df["State"].dropna().unique())
    state_default = [profile["state"]] if profile["state"] in state_options else state_options
    selected_states = st.sidebar.multiselect(tr("State"), state_options, default=state_default)
    filtered = commodity_df[commodity_df["State"].isin(selected_states)]

    districts = sorted(filtered["District"].dropna().unique())
    district_default = [profile["district"]] if profile["district"] in districts else districts
    selected_districts = st.sidebar.multiselect(tr("District"), districts, default=district_default)
    filtered = filtered[filtered["District"].isin(selected_districts)]

    selected_varieties = None
    varieties = sorted(filtered["Variety"].dropna().unique()) if "Variety" in filtered else []
    if varieties:
        selected_varieties = st.sidebar.multiselect(tr("Variety"), varieties, default=varieties)
        filtered = filtered[filtered["Variety"].isin(selected_varieties)]

    latest_date = df["Arrival_Date"].max()
    snapshot = filtered[filtered["Arrival_Date"] == latest_date]
    market_count = snapshot["Market"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(tr("Latest data date"), latest_date.strftime("%d %b %Y"))
    col2.metric(tr("Markets in view"), f"{market_count:,}")
    col3.metric(tr("Average modal price"), f"₹{snapshot['Modal Price'].mean():,.0f}" if not snapshot.empty else "—")
    col4.metric(tr("Records in view"), f"{len(snapshot):,}")

    st.subheader(tr("Market comparison: {crop}").format(crop=selected_commodity))
    if snapshot.empty:
        st.info(tr("No records match these filters. Try selecting another state or district in the sidebar."))
    else:
        price_fields = {name: (name, "mean") for name in ("Min Price", "Max Price") if name in snapshot}
        price_fields["Modal Price"] = ("Modal Price", "mean")
        compare = snapshot.groupby(["State", "District", "Market"], as_index=False).agg(**price_fields)
        compare["Reported price (₹/quintal)"] = compare["Modal Price"].round(0)
        compare["Weather-adjusted guide (₹/quintal)"] = compare["Reported price (₹/quintal)"]
        home_weather = (compare["State"].eq(profile["state"]) & compare["District"].eq(profile["district"]))
        compare.loc[home_weather, "Weather-adjusted guide (₹/quintal)"] = (
            compare.loc[home_weather, "Reported price (₹/quintal)"] * weather_factor
        ).round(0)
        compare["Modal Price"] = compare["Reported price (₹/quintal)"]
        rank_price = "Weather-adjusted guide (₹/quintal)"
        compare = compare.sort_values(rank_price, ascending=False)
        high, low = compare.iloc[0], compare.iloc[-1]
        home_markets = compare[(compare["State"] == profile["state"]) & (compare["District"] == profile["district"])]
        recommendation = home_markets.iloc[0] if not home_markets.empty else high
        with st.container(border=True):
            st.markdown(f"### {tr('⭐ Best mandi match for your filters')}")
            rec_col1, rec_col2, rec_col3 = st.columns([2, 1, 1])
            rec_col1.markdown(f"**{recommendation['Market']}**  \n{recommendation['District']}, {recommendation['State']}")
            rec_col2.metric(tr("Weather-adjusted guide"), f"₹{recommendation[rank_price]:,.0f}/क्विंटल" if st.session_state.get("ui_language") == "हिन्दी" else f"₹{recommendation[rank_price]:,.0f}/quintal")
            rec_col3.metric(tr("Data date"), latest_date.strftime("%d %b %Y"))
            if not home_markets.empty:
                caption = tr("Based on a reported mandi price of ₹{price:,.0f}/quintal. Weather signal: {reason}. This is a planning guide, not a market quote.")
                st.caption(caption.format(price=recommendation["Reported price (₹/quintal)"], reason=weather_reason))
            else:
                caption = tr("Your home district has no matching record in this data view. Showing the highest reported price in your selected filters for {crop}. Compare transport, quality, and arrivals before choosing a market.")
                st.caption(caption.format(crop=selected_commodity))
            if low["Market"] != high["Market"]:
                caption = tr("Price range in selected markets: ₹{low:,.0f}–₹{high:,.0f}/quintal.")
                st.caption(caption.format(low=low["Modal Price"], high=high["Modal Price"]))
        fig = px.bar(
            compare.head(25).sort_values(rank_price),
            x=rank_price,
            y="Market",
            color="State",
            color_discrete_sequence=["#1B4332", "#40916C", "#74A892", "#A8CDB4", "#E9C46A"],
            title=tr("Highest mandi prices · ₹ per quintal"),
            text=rank_price,
            hover_data=["Reported price (₹/quintal)", "District", "State"],
        )
        fig.update_layout(xaxis_title=tr("Price guide (₹ per quintal)"), yaxis_title="", showlegend=False,
                          template="plotly_dark" if dark_mode else "plotly_white", margin=dict(l=10, r=20, t=55, b=20))
        fig.update_traces(orientation="h", texttemplate="₹%{x:,.0f}", textposition="outside",
                          marker_line_width=0, cliponaxis=False)
        fig.update_yaxes(automargin=True, categoryorder="total ascending")
        st.plotly_chart(fig, use_container_width=True)
        caption = tr("Weather guide applies only to your home district. Rule of thumb: +1.5% for 5–19 mm forecast rain, +3% for 20+ mm, and +1% for forecast highs of 38°C or more. Signal: {reason}. Other districts show reported prices unchanged.")
        st.caption(caption.format(reason=weather_reason))
        st.dataframe(display_columns(compare), use_container_width=True, hide_index=True, height=420)
        st.download_button(
            tr("Download filtered market comparison (CSV)"),
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
            st.subheader(tr("Price movement since the previous report"))
            caption = tr("Compares matching market, crop, variety, and grade records from {start} to {end}. This is historical movement, not a forecast.")
            st.caption(caption.format(start=f"{previous_date:%d %b %Y}", end=f"{latest_date:%d %b %Y}"))
            rising = int((changes["Change (₹/quintal)"] > 0).sum())
            falling = int((changes["Change (₹/quintal)"] < 0).sum())
            unchanged = int((changes["Change (₹/quintal)"].round(2) == 0).sum())
            move_cols = st.columns(4)
            move_cols[0].metric(tr("Markets matched"), f"{len(changes):,}")
            move_cols[1].metric(tr("Prices higher"), f"{rising:,}")
            move_cols[2].metric(tr("Prices lower"), f"{falling:,}")
            move_cols[3].metric(tr("Unchanged"), f"{unchanged:,}")
            st.dataframe(display_columns(changes.round({"Previous modal price": 0, "Latest modal price": 0,
                                        "Change (₹/quintal)": 0, "Change (%)": 1})),
                         use_container_width=True, hide_index=True)
        else:
            st.info(tr("No like-for-like market records are available to compare with the previous report."))

    with st.expander(tr("Latest published mandi prices"), expanded=True):
        render_live_price_feed(selected_commodity, commodity_options, profile, weather_factor)

    st.subheader(tr("Price history"))
    date_count = df["Arrival_Date"].nunique()
    if date_count < 2:
        st.info(tr("Historical chart appears when multiple reporting dates are available."))
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
        history_fig.update_layout(xaxis_title=tr("Arrival date"), yaxis_title=tr("Average modal price (₹/quintal)"))
        history_fig.update_layout(template="plotly_dark" if dark_mode else "plotly_white",
                                  hovermode="x unified", margin=dict(l=10, r=20, t=25, b=20))
        history_fig.update_traces(line={"width": 3}, marker={"size": 8},
                                  hovertemplate="%{x|%d %b %Y}<br>₹%{y:,.0f}/quintal<extra></extra>")
        st.plotly_chart(history_fig, use_container_width=True)

    st.caption(tr("Decision support only. Market prices vary; verify current prices with the selected mandi."))


initialize_user_store()
st.session_state.setdefault("authenticated_user", None)
if st.session_state["authenticated_user"]:
    render_dashboard()
else:
    apply_green_theme(st.session_state.get("dark_mode", False))
    render_login_page()
