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

# --- 1. FIREBASE INITIALISIERUNG ---
def get_db_client():
    if firebase_admin._apps:
        try: return firestore.client()
        except: pass
    try:
        config = None
        if "__firebase_config" in globals():
            raw_cfg = globals()["__firebase_config"]
            config = json.loads(raw_cfg) if isinstance(raw_cfg, str) else raw_cfg
        if config:
            project_id = config.get('project_id') or config.get('projectId')
            if not project_id: return None
            cred = credentials.Certificate(config)
            firebase_admin.initialize_app(cred, {'projectId': project_id})
            return firestore.client()
    except: pass
    return None

db = get_db_client()
app_id = globals().get("__app_id", "default-app-id")
user_id = "default_user_radar"

# --- 2. PERSISTENZ-FUNKTIONEN ---
def save_favorites_to_db(ticker_string):
    global db
    if not db: db = get_db_client()
    if not db: 
        st.sidebar.error("❌ Cloud offline")
        return
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc_ref.set({"list": ticker_string, "updated_at": datetime.now()}, merge=True)
        st.sidebar.success("✅ Gespeichert!")
    except Exception as e:
        st.sidebar.error(f"❌ Fehler: {str(e)}")

def load_favorites_from_db():
    default_favs = "NVDA, TSLA, ANGI, PLTR, COIN, AMD, RHM.DE, TUI1.DE"
    global db
    if not db: db = get_db_client()
    if not db: return default_favs
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc = doc_ref.get()
        if doc.exists: return doc.to_dict().get("list", default_favs)
    except: pass
    return default_favs

# --- 3. DATEN-LISTEN ---
HGI_TICKERS = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP"
SZEW_TICKERS = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"
DAX_LISTE = "SAP.DE, SIE.DE, ALV.DE, MBG.DE, VOW3.DE, DTE.DE, BAS.DE, BAYN.DE, BMW.DE, ADS.DE, IFX.DE, RHM.DE, TUI1.DE, LHA.DE, DHL.DE"
NASDAQ_100 = "AAPL, MSFT, AMZN, NVDA, GOOGL, META, TSLA, AVGO, PEP, COST, ADBE, AMD, NFLX, PLTR, COIN"
GLOBAL_TOP = "AAPL, MSFT, NVDA, SAP.DE, SIE.DE, ALV.DE, KO, MCD, V, JPM, NOVO-B.CO, ASML.AS"
FAVORITEN_INIT = "NVDA, TSLA, ANGI, PLTR, COIN, AMD, RHM.DE, TUI1.DE"

# --- 4. APP SETUP ---
st.set_page_config(page_title="Aktien-Radar Pro", page_icon="🌍", layout="wide")

if 'ticker_input' not in st.session_state:
    st.session_state.ticker_input = load_favorites_from_db()
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None

# --- STYLING ---
def color_metric(val):
    try:
        v = float(str(val).replace('%', '').replace('+', ''))
        return 'color: #00ff00' if v > 0 else 'color: #ff4b4b' if v < 0 else ''
    except: return ''

def color_rsi(val):
    try:
        if val <= 35: return 'background-color: #d4edda; color: #155724'
        if val >= 70: return 'background-color: #f8d7da; color: #721c24'
    except: pass
    return ''

def format_curr(val):
    if val is None or pd.isna(val): return "-"
    if abs(val) >= 1e9: return f"{val/1e9:.2f} Mrd"
    if abs(val) >= 1e6: return f"{val/1e6:.2f} Mio"
    return str(round(val, 2))

# --- 5. SIDEBAR ---
st.sidebar.header("⚙️ Konfiguration")

if db: st.sidebar.success("🟢 Cloud verbunden")
else: st.sidebar.error("🔴 Cloud offline")

with st.sidebar.expander("📊 Indizes laden", expanded=False):
    if st.button("DAX 40", use_container_width=True): st.session_state.ticker_input = DAX_LISTE
    if st.button("Nasdaq 100", use_container_width=True): st.session_state.ticker_input = NASDAQ_100

with st.sidebar.expander("🧠 Experten", expanded=True):
    c1, c2 = st.columns(2)
    if c1.button("HGI", use_container_width=True): st.session_state.ticker_input = HGI_TICKERS
    if c2.button("Szew", use_container_width=True): st.session_state.ticker_input = SZEW_TICKERS
    if st.button("🌍 Global Top laden", use_container_width=True): st.session_state.ticker_input = GLOBAL_TOP
    if st.button("📂 Cloud-Favoriten laden", use_container_width=True):
        st.session_state.ticker_input = load_favorites_from_db()
        st.rerun()

st.sidebar.divider()
ticker_text = st.sidebar.text_area("⭐ Meine Ticker-Liste:", value=st.session_state.ticker_input, height=120)
st.session_state.ticker_input = ticker_text

if st.sidebar.button("💾 Liste dauerhaft speichern", use_container_width=True):
    save_favorites_to_db(ticker_text)

if st.sidebar.button("🧹 Cache leeren & Reset", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
rsi_max = st.sidebar.slider("RSI-Filter", 10, 100, 85)
auto_refresh = st.sidebar.toggle("⏱️ Auto-Update", value=False)
interval = st.sidebar.slider("Sekunden", 10, 300, 60)

# --- 6. SCANNER (Robustere Version) ---
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
            if h.empty or len(h) < 20:
                continue
            
            # Preis Fallback falls info() hängt
            last_price = h['Close'].iloc[-1]
            prev_close = h['Close'].iloc[-2]
            
            # RSI Berechnung
            delta = h['Close'].diff()
            up = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            down = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rsi = 100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1])))
            
            if rsi <= rsi_limit:
                # Info-Abfrage (langsam)
                try:
                    info = t.info
                except:
                    info = {}
                
                p = info.get('currentPrice') or last_price
                prev = info.get('previousClose') or prev_close
                
                peg = info.get('pegRatio') or info.get('trailingPegRatio') or "-"
                fcf = info.get('freeCashflow', 0)
                mcap = info.get('marketCap', 1)
                fcf_y = (fcf / mcap * 100) if fcf and mcap else 0
                
                results.append({
                    "Name": info.get('shortName', sym),
                    "Symbol": sym,
                    "Kurs": round(p, 2),
                    "Heute %": round(((p-prev)/prev)*100, 2),
                    "RSI": round(rsi, 1),
                    "PEG": round(float(peg), 2) if isinstance(peg, (int, float)) else "-",
                    "FCF Yield %": round(fcf_y, 1),
                    "Netto-Schuld": (info.get('totalDebt', 0) - info.get('totalCash', 0)),
                    "Rating": str(info.get('recommendationKey', '-')).replace('_',' ').capitalize(),
                    "Potential %": round(((info.get('targetMeanPrice', p)-p)/p*100), 1) if info.get('targetMeanPrice') else 0
                })
        except Exception:
            continue
        bar.progress((i + 1) / len(symbols))
    
    status.empty()
    bar.empty()
    return results

if st.button("🚀 Scanner starten", type="primary") or auto_refresh:
    syms = tuple(ticker_text.split(","))
    if syms:
        st.session_state.scan_results = scan_tickers_robust(syms, rsi_max)
        st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

# --- 7. ANZEIGE ---
if st.session_state.scan_results:
    st.write(f"Update: **{st.session_state.last_update}**")
    df = pd.DataFrame(st.session_state.scan_results)
    
    def color_valuation(row):
        peg = row['PEG']
        pot = row['Potential %']
        color = ''
        if isinstance(peg, (int, float)) and peg < 1.0 and pot > 15:
            color = 'background-color: #006400; color: white'
        return [color if col == 'Name' else '' for col in row.index]

    st.dataframe(
        df.style.applymap(color_metric, subset=['Heute %', 'Potential %', 'FCF Yield %'])
        .applymap(color_rsi, subset=['RSI'])
        .format({"Heute %": "{:+.2f}%", "Potential %": "{:+.1f}%", "FCF Yield %": "{:.1f}%", "Netto-Schuld": lambda x: format_curr(x)}),
        use_container_width=True, hide_index=True
    )
    
    st.divider()
    selected = st.selectbox("Chart wählen:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.scan_results])
    active_sym = selected.split("(")[-1].replace(")", "")
    
    if active_sym:
        hist_d = yf.Ticker(active_sym).history(period="1y")
        fig = go.Figure(data=[go.Candlestick(x=hist_d.index, open=hist_d['Open'], high=hist_d['High'], low=hist_d['Low'], close=hist_d['Close'])])
        fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

# --- 8. FEEDS ---
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
