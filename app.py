import streamlit as st
import yfinance as yf
import pandas as pd
import time
import feedparser
import urllib.parse
import plotly.graph_objects as go
from datetime import datetime
import json

# Firebase Imports für die Speicherung
from firebase_admin import credentials, firestore, initialize_app, get_app, _apps
import firebase_admin.auth

# --- 0. FIREBASE SETUP (FÜR SPEICHERFUNKTION) ---
# Hinweis: Wir nutzen die bereitgestellten Umgebungsvariablen für die Persistenz
firebase_config = None
app_id = "default-app-id"
initial_auth_token = None

if "__firebase_config" in globals():
    firebase_config = json.loads(globals()["__firebase_config"])
if "__app_id" in globals():
    app_id = globals()["__app_id"]
if "__initial_auth_token" in globals():
    initial_auth_token = globals()["__initial_auth_token"]

# Da Streamlit das Skript oft neu lädt, initialisieren wir Firebase nur einmal
try:
    if not _apps:
        # Hier wird im Hintergrund die Authentifizierung und DB-Verbindung aufgebaut
        # In dieser Umgebung sind die Credentials bereits vorkonfiguriert
        initialize_app()
    db = firestore.client()
except Exception as e:
    st.error(f"Datenbank-Verbindung fehlgeschlagen: {e}")

# Benutzer-ID simulieren oder aus Auth beziehen (hier vereinfacht für die Persistenz)
user_id = "default_user" 

def save_favorites_to_cloud(ticker_string):
    """Speichert die Ticker-Liste in der Cloud-Datenbank."""
    try:
        doc_ref = db.document(f"artifacts/{app_id}/users/{user_id}/settings/favorites")
        doc_ref.set({"list": ticker_string, "updated_at": datetime.now()})
        st.sidebar.success("✅ Favoriten gespeichert!")
    except Exception as e:
        st.sidebar.error(f"Fehler beim Speichern: {e}")

def load_favorites_from_cloud():
    """Lädt die Ticker-Liste aus der Cloud-Datenbank."""
    try:
        doc_ref = db.document(f"artifacts/{app_id}/users/{user_id}/settings/favorites")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("list")
    except:
        pass
    return "NVDA, TSLA, AAPL" # Fallback

# --- 1. KONFIGURATION & DATEN ---
st.set_page_config(page_title="Aktien-Radar Pro", page_icon="🌍", layout="wide")

# Initialisierung des Session States
if 'ticker_input' not in st.session_state:
    # Beim ersten Start aus der Cloud laden
    st.session_state.ticker_input = load_favorites_from_cloud()
if 'rsi_limit' not in st.session_state:
    st.session_state.rsi_limit = 85
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None

# Experten-Listen
HGI_TICKERS = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP"
SZEW_TICKERS = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"

# Indizes
DAX_LISTE = "SAP.DE, SIE.DE, ALV.DE, MBG.DE, VOW3.DE, DTE.DE, BAS.DE, BAYN.DE, BMW.DE, CON.DE, CBK.DE, DBK.DE, DB1.DE, DTG.DE, EOAN.DE, ADS.DE, HEN3.DE, IFX.DE, MUV2.DE, P911.DE, RWE.DE, SHL.DE, VNA.DE, AIR.DE, RHM.DE, TUI1.DE"
NASDAQ_100 = "AAPL, MSFT, AMZN, NVDA, GOOGL, META, TSLA, AVGO, PEP, COST, ADBE, AMD, NFLX"

WKN_MAP = {"716460": "SAP.DE", "723610": "SIE.DE", "840400": "ALV.DE", "710000": "MBG.DE"}

# --- 2. HILFSFUNKTIONEN ---
def get_rss_news(url):
    try:
        feed = feedparser.parse(url)
        return [{'title': e.title, 'link': e.link} for e in feed.entries[:3]]
    except: return []

def load_list_callback(text):
    st.session_state.ticker_input = text

def format_currency(val):
    if val is None or pd.isna(val): return "-"
    if abs(val) >= 1_000_000_000: return f"{val / 1_000_000_000:.2f} Mrd"
    elif abs(val) >= 1_000_000: return f"{val / 1_000_000:.2f} Mio"
    return str(val)

# --- 3. SEITENLEISTE ---
st.sidebar.header("📂 Portfolios & Indizes")

with st.sidebar.expander("📊 Indizes laden", expanded=False):
    st.button("DAX 40", on_click=load_list_callback, args=(DAX_LISTE,), use_container_width=True)
    st.button("Nasdaq 100", on_click=load_list_callback, args=(NASDAQ_100,), use_container_width=True)

with st.sidebar.expander("🧠 Experten", expanded=False):
    st.button("HGI (Waldhauser)", on_click=load_list_callback, args=(HGI_TICKERS,), use_container_width=True)
    st.button("Szew (Weishar)", on_click=load_list_callback, args=(SZEW_TICKERS,), use_container_width=True)

st.sidebar.divider()
st.sidebar.subheader("⭐ Eigene Favoriten")
ticker_text = st.sidebar.text_area("Aktien-Symbole (Kürzel):", value=st.session_state.ticker_input, height=120)
st.session_state.ticker_input = ticker_text

# Speichern Button
if st.sidebar.button("💾 Favoriten dauerhaft speichern", use_container_width=True):
    save_favorites_to_cloud(ticker_text)

st.sidebar.divider()

# NEU: aktien.guide Link
st.sidebar.link_button("🔍 aktien.guide öffnen", "https://aktien.guide", use_container_width=True)

st.sidebar.divider()
st.session_state.rsi_limit = st.sidebar.slider("RSI-Limit (Max)", 10, 100, st.session_state.rsi_limit)
auto_refresh = st.sidebar.toggle("⏱️ Live-Scan (60s)", value=False)
show_briefing = st.sidebar.checkbox("🧠 Experten-Briefing", value=True)

# --- 4. SCANNER ---
st.title("💎 Aktien-Radar Pro")

if st.button("🚀 Scanner starten", type="primary") or auto_refresh:
    symbols = [WKN_MAP.get(s.strip().upper(), s.strip().upper()) for s in ticker_text.split(",") if s.strip()]
    scan_results = []
    
    prog_bar = st.progress(0)
    for i, sym in enumerate(symbols):
        try:
            stock = yf.Ticker(sym)
            history = stock.history(period="250d")
            
            if not history.empty and len(history) > 30:
                delta = history['Close'].diff()
                gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
                loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                
                if rsi_val <= st.session_state.rsi_limit:
                    info = stock.info
                    price = info.get('currentPrice') or history['Close'].iloc[-1]
                    bid = info.get('bid', '-')
                    ask = info.get('ask', '-')
                    prev_c = info.get('previousClose', price)
                    day_change = ((price - prev_c) / prev_c) * 100
                    
                    target = info.get('targetMeanPrice')
                    potential = ((target - price) / price) * 100 if target else 0
                    
                    scan_results.append({
                        "Name": info.get('shortName', sym),
                        "Symbol": sym,
                        "Kurs": round(price, 2),
                        "Bid": round(bid, 2) if isinstance(bid, (int, float)) else bid,
                        "Ask": round(ask, 2) if isinstance(ask, (int, float)) else ask,
                        "Heute %": round(day_change, 2),
                        "RSI": round(rsi_val, 1),
                        "Potential %": round(potential, 1) if target else 0,
                        "Rating": info.get('recommendationKey', '-').replace('_', ' ').capitalize()
                    })
        except: pass
        prog_bar.progress((i + 1) / len(symbols))
    
    st.session_state.scan_results = scan_results
    st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

# --- 5. ANZEIGE ---
if st.session_state.scan_results:
    st.caption(f"Letzte Aktualisierung: {st.session_state.get('last_update', 'Gerade eben')}")
    df_results = pd.DataFrame(st.session_state.scan_results)
    
    def color_val(val):
        try:
            v = float(str(val).replace('%', ''))
            return 'color: green' if v > 0 else 'color: red' if v < 0 else ''
        except: return ''

    st.dataframe(df_results.style.applymap(color_val, subset=['Heute %', 'Potential %']), use_container_width=True, hide_index=True)
    
    st.divider()
    st.subheader("📉 Detail-Analyse")
    selected_name = st.selectbox("Aktie wählen:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.scan_results])
    active_sym = selected_name.split("(")[-1].replace(")", "")
    
    if active_sym:
        detail_stock = yf.Ticker(active_sym)
        det_info = detail_stock.info
        
        tab1, tab2 = st.tabs(["📊 Chart", "🔮 Profil"])
        with tab1:
            c_hist = detail_stock.history(period="1y")
            fig = go.Figure(data=[go.Candlestick(x=c_hist.index, open=c_hist['Open'], high=c_hist['High'], low=c_hist['Low'], close=c_hist['Close'], name="Kurs")])
            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_white", height=500)
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            st.write(det_info.get('longBusinessSummary', "Keine Beschreibung verfügbar."))

if show_briefing:
    st.divider()
    col_l, col_r = st.columns(2)
    with col_l:
        st.info("📊 **Stefan Waldhauser**")
        for n in get_rss_news("https://hightechinvesting.substack.com/feed"):
            st.markdown(f"• [{n['title']}]({n['link']})")
    with col_r:
        st.info("🐻 **Simon Weishar**")
        for n in get_rss_news("https://szew.substack.com/feed"):
            st.markdown(f"• [{n['title']}]({n['link']})")

if auto_refresh:
    time.sleep(60)
    st.rerun()
