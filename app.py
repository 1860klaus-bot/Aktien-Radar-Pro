import streamlit as st
import yfinance as yf
import pandas as pd
import time
import feedparser
import plotly.graph_objects as go
from datetime import datetime
import json
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. ROBUSTE FIREBASE INITIALISIERUNG ---
def initialize_db():
    """Initialisiert Firebase und gibt den Firestore-Client mit expliziter Projekt-ID zurück."""
    try:
        # Falls bereits eine Instanz läuft, versuchen wir den Client zu holen
        if firebase_admin._apps:
            try:
                config_str = globals().get("__firebase_config")
                if config_str:
                    config = json.loads(config_str)
                    pid = config.get('project_id') or config.get('projectId')
                    return firestore.client(project=pid)
                return firestore.client()
            except:
                pass

        # Neue Initialisierung
        config = None
        if "__firebase_config" in globals():
            raw_cfg = globals()["__firebase_config"]
            config = json.loads(raw_cfg) if isinstance(raw_cfg, str) else raw_cfg
        
        if config:
            project_id = config.get('project_id') or config.get('projectId')
            if not project_id:
                return None
            
            cred = credentials.Certificate(config)
            firebase_admin.initialize_app(cred, {'projectId': project_id})
            return firestore.client(project=project_id)
    except Exception:
        pass
    return None

# Initialer Verbindungsaufbau
if 'db' not in st.session_state:
    st.session_state.db = initialize_db()

app_id = globals().get("__app_id", "default-app-id")
user_id = "default_user_radar"

# --- 2. VERBESSERTE SPEICHER-FUNKTIONEN ---
def save_favorites_to_cloud(ticker_string):
    """Speichert Favoriten mit Reconnect-Versuch bei Fehlern."""
    # Falls DB nicht bereit, versuche Reconnect
    if not st.session_state.db:
        st.session_state.db = initialize_db()
        
    if not st.session_state.db: 
        st.sidebar.error("❌ Cloud-Speicher nicht verfügbar. (Verbindung fehlgeschlagen)")
        return
    
    try:
        # Pfad-Regel: /artifacts/{appId}/users/{userId}/{collectionName}/{docId}
        doc_ref = st.session_state.db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc_ref.set({
            "list": ticker_string,
            "updated_at": datetime.now()
        }, merge=True)
        st.sidebar.success("✅ Favoriten sicher in der Cloud gespeichert!")
    except Exception as e:
        st.sidebar.error(f"❌ Fehler beim Speichern: {str(e)}")

def load_favorites_from_cloud():
    """Lädt Favoriten aus der Cloud oder nutzt Standard-Werte."""
    default_favs = "NVDA, TSLA, ANGI, PLTR, COIN, AMD, RHM.DE, TUI1.DE"
    if not st.session_state.db:
        st.session_state.db = initialize_db()
    if not st.session_state.db: 
        return default_favs
    try:
        doc_ref = st.session_state.db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("list", default_favs)
    except:
        pass
    return default_favs

# --- 3. APP SETUP & SIDEBAR ---
st.set_page_config(page_title="Aktien-Radar Pro", page_icon="🌍", layout="wide")

# Listen-Vorgaben
HGI_TICKERS = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP"
SZEW_TICKERS = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"
DAX_LISTE = "SAP.DE, SIE.DE, ALV.DE, MBG.DE, VOW3.DE, DTE.DE, BAS.DE, BAYN.DE, BMW.DE, ADS.DE, IFX.DE, RHM.DE, TUI1.DE, LHA.DE, DHL.DE"
NASDAQ_100 = "AAPL, MSFT, AMZN, NVDA, GOOGL, META, TSLA, AVGO, PEP, COST, ADBE, AMD, NFLX, PLTR, COIN"

if 'ticker_input' not in st.session_state:
    st.session_state.ticker_input = load_favorites_from_cloud()

st.sidebar.header("⚙️ Konfiguration")

# Cloud Status Anzeige
if st.session_state.db:
    st.sidebar.success("🟢 Cloud verbunden")
else:
    st.sidebar.warning("🔴 Cloud offline")
    if st.sidebar.button("🔄 Verbindung testen"):
        st.session_state.db = initialize_db()
        st.rerun()

with st.sidebar.expander("📊 Indizes laden", expanded=False):
    if st.button("DAX 40", use_container_width=True): st.session_state.ticker_input = DAX_LISTE
    if st.button("Nasdaq 100", use_container_width=True): st.session_state.ticker_input = NASDAQ_100

with st.sidebar.expander("🧠 Experten", expanded=True):
    c1, c2 = st.columns(2)
    if c1.button("HGI", use_container_width=True): st.session_state.ticker_input = HGI_TICKERS
    if c2.button("Szew", use_container_width=True): st.session_state.ticker_input = SZEW_TICKERS
    if st.button("📂 Cloud-Favoriten laden", use_container_width=True):
        st.session_state.ticker_input = load_favorites_from_cloud()
        st.rerun()

st.sidebar.divider()
ticker_text = st.sidebar.text_area("⭐ Meine Ticker-Liste:", value=st.session_state.ticker_input, height=120)
st.session_state.ticker_input = ticker_text

if st.sidebar.button("💾 Liste dauerhaft speichern", use_container_width=True, type="primary"):
    save_favorites_to_cloud(ticker_text)

st.sidebar.divider()
rsi_max = st.sidebar.slider("RSI-Filter", 10, 100, 85)
auto_refresh = st.sidebar.toggle("⏱️ Auto-Scan", value=False)
interval = st.sidebar.slider("Sekunden", 10, 300, 60)

# --- 4. SCANNER LOGIK ---
st.title("💎 Aktien-Radar Pro")

@st.cache_data(ttl=300)
def scan_tickers_robust(symbols_tuple, rsi_limit):
    results = []
    symbols = [s.strip().upper() for s in list(symbols_tuple) if s.strip()]
    status = st.empty()
    bar = st.progress(0)
    
    for i, sym in enumerate(symbols):
        status.info(f"Scanne **{sym}**... ({i+1}/{len(symbols)})")
        try:
            t = yf.Ticker(sym)
            h = t.history(period="60d")
            if h.empty or len(h) < 20: continue
            
            # RSI & Kurs
            last_p = h['Close'].iloc[-1]
            prev_p = h['Close'].iloc[-2]
            delta = h['Close'].diff()
            up = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            down = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rsi = 100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1])))
            
            if rsi <= rsi_limit:
                try:
                    info = t.info
                except:
                    info = {}
                
                p = info.get('currentPrice') or last_p
                prev = info.get('previousClose') or prev_p
                peg = info.get('pegRatio') or info.get('trailingPegRatio') or "-"
                fcf_yield = (info.get('freeCashflow', 0) / info.get('marketCap', 1) * 100) if info.get('freeCashflow') else 0
                
                results.append({
                    "Name": info.get('shortName', sym), "Symbol": sym, "Kurs": round(p, 2),
                    "Heute %": round(((p-prev)/prev)*100, 2), "RSI": round(rsi, 1),
                    "PEG": round(float(peg), 2) if isinstance(peg, (int, float)) else "-",
                    "FCF Yield %": round(fcf_yield, 1),
                    "Netto-Schuld": (info.get('totalDebt', 0) - info.get('totalCash', 0)),
                    "Potential %": round(((info.get('targetMeanPrice', p)-p)/p*100), 1) if info.get('targetMeanPrice') else 0
                })
        except: continue
        bar.progress((i + 1) / len(symbols))
    status.empty(); bar.empty()
    return results

if st.button("🚀 Scanner starten", type="primary") or auto_refresh:
    syms = tuple(ticker_text.split(","))
    if syms:
        st.session_state.scan_results = scan_tickers_robust(syms, rsi_max)
        st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

# --- 5. ANZEIGE ---
if st.session_state.get('scan_results'):
    st.write(f"Update: **{st.session_state.get('last_update')}**")
    df = pd.DataFrame(st.session_state.scan_results)
    
    def color_growth(val):
        try:
            v = float(str(val).replace('%', ''))
            return 'color: #00ff00' if v > 0 else 'color: #ff4b4b' if v < 0 else ''
        except: return ''

    st.dataframe(
        df.style.applymap(color_growth, subset=['Heute %', 'Potential %', 'FCF Yield %'])
        .format({"Heute %": "{:+.2f}%", "Potential %": "{:+.1f}%", "FCF Yield %": "{:.1f}%", 
                 "Netto-Schuld": lambda x: f"{x/1e6:.1f} Mio" if abs(x) < 1e9 else f"{x/1e9:.2f} Mrd"}),
        use_container_width=True, hide_index=True
    )
    
    selected = st.selectbox("Chart:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.scan_results])
    active_sym = selected.split("(")[-1].replace(")", "")
    if active_sym:
        hist = yf.Ticker(active_sym).history(period="1y")
        fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'])])
        fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)

# --- 6. FEEDS ---
st.divider()
cl, cr = st.columns(2)
with cl:
    st.info("📊 **Stefan Waldhauser (HGI)**")
    st.link_button("📈 Wikifolio", "https://www.wikifolio.com/de/de/w/wf0stwtech", use_container_width=True)
    f = feedparser.parse("https://hightechinvesting.substack.com/feed")
    for e in f.entries[:3]: st.markdown(f"• [{e.title}]({e.link})")
with cr:
    st.info("🐻 **Simon Weishar (Szew)**")
    st.link_button("📈 Wikifolio", "https://www.wikifolio.com/de/de/w/wf00szew01", use_container_width=True)
    f = feedparser.parse("https://szew.substack.com/feed")
    for e in f.entries[:3]: st.markdown(f"• [{e.title}]({e.link})")

if auto_refresh:
    time.sleep(interval)
    st.rerun()
