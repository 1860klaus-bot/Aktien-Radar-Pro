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
@st.cache_resource
def get_db_connection():
    """Stellt die Verbindung zur Cloud-Datenbank (Firestore) her."""
    if not firebase_admin._apps:
        try:
            config_str = globals().get("__firebase_config")
            if config_str:
                config = json.loads(config_str)
                cred = credentials.Certificate(config)
                # Projekt-ID explizit setzen, um Fehler in der Cloud zu vermeiden
                firebase_admin.initialize_app(cred, {
                    'projectId': config.get('project_id'),
                })
            else:
                firebase_admin.initialize_app()
            return firestore.client()
        except Exception as e:
            st.sidebar.error(f"Datenbank-Fehler: {e}")
            return None
    return firestore.client()

db = get_db_connection()
app_id = globals().get("__app_id", "default-app-id")
user_id = "default_user"

# --- 2. PERSISTENZ-FUNKTIONEN ---
def save_favorites_to_db(ticker_string):
    """Speichert die Ticker-Liste dauerhaft in der Cloud."""
    if not db: return
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc_ref.set({"list": ticker_string, "updated_at": datetime.now()})
        st.sidebar.success("✅ Favoriten gespeichert!")
    except Exception as e:
        st.sidebar.error(f"Speichern fehlgeschlagen: {e}")

def load_favorites_from_db():
    """Lädt die gespeicherten Favoriten beim Start."""
    if not db: return "NVDA, TSLA, AAPL, SAP.DE"
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("list", "NVDA, TSLA, AAPL, SAP.DE")
    except: pass
    return "NVDA, TSLA, AAPL, SAP.DE"

# --- 3. DATEN-LISTEN (VORLAGEN) ---
HGI_LIST = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP"
SZEW_LIST = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"
DAX_LIST = "SAP.DE, SIE.DE, ALV.DE, MBG.DE, VOW3.DE, DTE.DE, BAS.DE, BAYN.DE, BMW.DE, ADS.DE, IFX.DE, RHM.DE, TUI1.DE, DHL.DE"

# --- 4. APP KONFIGURATION ---
st.set_page_config(page_title="Aktien-Radar Pro", page_icon="🌍", layout="wide")

if 'ticker_input' not in st.session_state:
    st.session_state.ticker_input = load_favorites_from_db()
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None

# SEITENLEISTE
st.sidebar.header("⚙️ Konfiguration")
if db:
    st.sidebar.caption("🟢 Cloud-Speicher aktiv")
else:
    st.sidebar.caption("🔴 Cloud-Speicher offline")

with st.sidebar.expander("📊 Schnell-Listen laden", expanded=False):
    if st.button("DAX 40", use_container_width=True): st.session_state.ticker_input = DAX_LIST
    if st.button("HGI (Waldhauser)", use_container_width=True): st.session_state.ticker_input = HGI_LIST
    if st.button("Szew (Weishar)", use_container_width=True): st.session_state.ticker_input = SZEW_LIST

st.sidebar.divider()
st.sidebar.subheader("⭐ Meine Favoriten")
ticker_text = st.sidebar.text_area("Ticker (Kürzel mit Komma):", value=st.session_state.ticker_input, height=150)
st.session_state.ticker_input = ticker_text

if st.sidebar.button("💾 Liste dauerhaft speichern", use_container_width=True):
    save_favorites_to_db(ticker_text)

st.sidebar.divider()
st.sidebar.link_button("🔍 aktien.guide öffnen", "https://aktien.guide", use_container_width=True)

st.sidebar.divider()
rsi_limit = st.sidebar.slider("RSI-Filter (Maximalwert)", 10, 100, 85)
auto_refresh = st.sidebar.toggle("⏱️ Automatischer Scan (60s)", value=False)

# --- 5. CORE SCANNER ---
st.title("💎 Aktien-Radar Pro")

@st.cache_data(ttl=300)
def fetch_stock_data(symbols_tuple, rsi_max):
    results = []
    symbols = list(symbols_tuple)
    status_msg = st.empty()
    bar = st.progress(0)
    
    for i, sym in enumerate(symbols):
        status_msg.text(f"Analysiere: {sym} ({i+1}/{len(symbols)})")
        try:
            t = yf.Ticker(sym)
            h = t.history(period="60d")
            if h.empty or len(h) < 20: continue
            
            # RSI Berechnung (14 Tage)
            delta = h['Close'].diff()
            up = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            down = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rsi = 100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1])))
            
            if rsi <= rsi_max:
                info = t.info
                p = info.get('currentPrice') or h['Close'].iloc[-1]
                prev = info.get('previousClose', p)
                
                # Fundamentale Metriken
                peg = info.get('pegRatio') or info.get('trailingPegRatio') or "-"
                fcf = info.get('freeCashflow')
                mcap = info.get('marketCap')
                fcf_yield = (fcf/mcap*100) if fcf and mcap else 0
                
                cash = info.get('totalCash')
                debt = info.get('totalDebt')
                net_debt = (debt - cash) if (debt is not None and cash is not None) else info.get('netDebt')
                
                target = info.get('targetMeanPrice')
                potential = ((target - p) / p * 100) if target else 0
                
                # Mapping der Analysten-Empfehlungen
                raw_rating = info.get('recommendationKey', '-')
                rating_map = {
                    'strong_buy': 'Starker Kauf', 'buy': 'Kauf',
                    'hold': 'Halten', 'underperform': 'Verkauf', 'sell': 'Starker Verkauf'
                }
                display_rating = rating_map.get(raw_rating, raw_rating.capitalize())
                
                results.append({
                    "Name": info.get('shortName', sym),
                    "Symbol": sym,
                    "Kurs": round(p, 2),
                    "Bid": info.get('bid', '-'),
                    "Ask": info.get('ask', '-'),
                    "Heute %": round(((p-prev)/prev)*100, 2),
                    "RSI": round(rsi, 1),
                    "PEG": peg if peg == "-" else round(float(peg), 2),
                    "FCF Yield %": round(fcf_yield, 1),
                    "Netto-Schulden": net_debt,
                    "Rating": display_rating,
                    "Potential %": round(potential, 1)
                })
        except: continue
        bar.progress((i + 1) / len(symbols))
    
    status_msg.empty()
    bar.empty()
    return results

if st.button("🚀 Scanner starten", type="primary") or auto_refresh:
    sym_list = tuple([s.strip().upper() for s in ticker_text.split(",") if s.strip()])
    if sym_list:
        data = fetch_stock_data(sym_list, rsi_limit)
        st.session_state.scan_results = data
        st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

# --- 6. ANZEIGE DER ERGEBNISSE ---
if st.session_state.scan_results:
    st.caption(f"Letztes Update: {st.session_state.last_update}")
    df = pd.DataFrame(st.session_state.scan_results)
    
    # Formatierungsfunktionen
    def color_growth(val):
        try:
            v = float(val)
            return 'color: #00ff00' if v > 0 else 'color: #ff4b4b' if v < 0 else ''
        except: return ''

    def color_debt(val):
        try:
            if val < 0: return 'background-color: rgba(0, 255, 0, 0.1); color: #00ff00'
            if val > 0: return 'background-color: rgba(255, 75, 75, 0.1); color: #ff4b4b'
        except: pass
        return ''

    styled_df = df.style.applymap(color_growth, subset=['Heute %', 'Potential %', 'FCF Yield %'])\
                        .applymap(color_debt, subset=['Netto-Schulden'])
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # DETAIL ANALYSE
    st.subheader("📉 Detail-Analyse & Charts")
    selected = st.selectbox("Wähle eine Aktie aus dem Scan:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.scan_results])
    active_sym = selected.split("(")[-1].replace(")", "")
    
    if active_sym:
        st.subheader(f"Analyse: {selected}")
        c1, c2 = st.columns([2, 1])
        with c1:
            stock_obj = yf.Ticker(active_sym)
            hist_data = stock_obj.history(period="1y")
            fig = go.Figure(data=[go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'])])
            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=450, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            detail_info = stock_obj.info
            st.metric("Forward KGV", detail_info.get('forwardPE', '-'))
            st.metric("EBITDA Marge", f"{detail_info.get('ebitdaMargins', 0)*100:.1f}%" if detail_info.get('ebitdaMargins') else "-")
            st.write("**Unternehmensprofil:**")
            st.caption(detail_info.get('longBusinessSummary', "Keine Info verfügbar.")[:600] + "...")

# RSS NEWS
st.divider()
col_l, col_r = st.columns(2)
with col_l:
    st.info("📊 **Stefan Waldhauser (HGI)**")
    feed_hgi = feedparser.parse("https://hightechinvesting.substack.com/feed")
    for entry in feed_hgi.entries[:3]:
        st.markdown(f"• [{entry.title}]({entry.link})")
with col_r:
    st.info("🐻 **Simon Weishar (Szew)**")
    feed_szew = feedparser.parse("https://szew.substack.com/feed")
    for entry in feed_szew.entries[:3]:
        st.markdown(f"• [{entry.title}]({entry.link})")

if auto_refresh:
    time.sleep(60)
    st.rerun()
