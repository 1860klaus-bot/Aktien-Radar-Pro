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
def initialize_firebase_connection():
    """Initialisiert die Verbindung zur Firestore-Datenbank."""
    if not firebase_admin._apps:
        try:
            if "__firebase_config" in globals():
                config = json.loads(globals()["__firebase_config"])
                cred = credentials.Certificate(config)
                firebase_admin.initialize_app(cred)
            else:
                # Fallback für lokale Tests
                firebase_admin.initialize_app()
            return True
        except Exception as e:
            st.error(f"Datenbank konnte nicht geladen werden: {e}")
            return False
    return True

has_db = initialize_firebase_connection()
db = firestore.client() if has_db else None
app_id = globals().get("__app_id", "default-app-id")
user_id = "default_user"  # In dieser Umgebung nutzen wir eine Standard-ID

# --- 2. SPEICHER-LOGIK ---
def save_favorites_to_db(ticker_string):
    """Speichert die Favoritenliste dauerhaft in der Cloud."""
    if not db: return
    try:
        # Pfad: /artifacts/{appId}/users/{userId}/settings/favorites
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc_ref.set({
            "list": ticker_string,
            "last_saved": datetime.now()
        })
        st.sidebar.success("✅ Favoriten erfolgreich gespeichert!")
    except Exception as e:
        st.sidebar.error(f"Fehler beim Speichern: {e}")

def load_favorites_from_db():
    """Lädt die gespeicherte Favoritenliste aus der Cloud."""
    if not db: return "NVDA, TSLA, AAPL"
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("list", "NVDA, TSLA, AAPL")
    except:
        pass
    return "NVDA, TSLA, AAPL"

# --- 3. DATEN-LISTEN (KONSTANTEN) ---
HGI_TICKERS = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP"
SZEW_TICKERS = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"
DAX_LISTE = "SAP.DE, SIE.DE, ALV.DE, MBG.DE, VOW3.DE, DTE.DE, BAS.DE, BAYN.DE, BMW.DE, ADS.DE, IFX.DE, RHM.DE, TUI1.DE, LHA.DE, DHL.DE"
NASDAQ_LISTE = "AAPL, MSFT, AMZN, NVDA, GOOGL, META, TSLA, AVGO, PEP, COST, ADBE, AMD, NFLX, PLTR, COIN"

# --- 4. APP KONFIGURATION ---
st.set_page_config(page_title="Aktien-Radar Pro", page_icon="🌍", layout="wide")

# Session State für Favoriten
if 'ticker_input' not in st.session_state:
    st.session_state.ticker_input = load_favorites_from_db()
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None

# --- 5. HILFSFUNKTIONEN FÜR ANALYSE ---
def get_rss_briefing(url):
    try:
        feed = feedparser.parse(url)
        return [{'title': e.title, 'link': e.link} for e in feed.entries[:3]]
    except: return []

def format_money(val):
    if val is None or pd.isna(val): return "-"
    if abs(val) >= 1_000_000_000: return f"{val / 1_000_000_000:.2f} Mrd"
    elif abs(val) >= 1_000_000: return f"{val / 1_000_000:.2f} Mio"
    return f"{val:.2f}"

# --- 6. SEITENLEISTE (SIDEBAR) ---
st.sidebar.header("📂 Portfolios & Indizes")

with st.sidebar.expander("📊 Indizes & Experten", expanded=False):
    if st.button("DAX 40 laden", use_container_width=True):
        st.session_state.ticker_input = DAX_LISTE
    if st.button("Nasdaq 100 laden", use_container_width=True):
        st.session_state.ticker_input = NASDAQ_LISTE
    st.divider()
    if st.button("HGI (Waldhauser)", use_container_width=True):
        st.session_state.ticker_input = HGI_TICKERS
    if st.button("Szew (Weishar)", use_container_width=True):
        st.session_state.ticker_input = SZEW_TICKERS

st.sidebar.divider()
st.sidebar.subheader("⭐ Eigene Favoriten")
ticker_text = st.sidebar.text_area("Ticker-Liste (kommagetrennt):", value=st.session_state.ticker_input, height=150)
st.session_state.ticker_input = ticker_text

if st.sidebar.button("💾 Favoriten dauerhaft speichern", use_container_width=True):
    save_favorites_to_db(ticker_text)

st.sidebar.divider()
st.sidebar.link_button("🔍 aktien.guide öffnen", "https://aktien.guide", use_container_width=True)

st.sidebar.divider()
rsi_limit = st.sidebar.slider("RSI-Filter (Maximalwert)", 10, 100, 85)
auto_refresh = st.sidebar.toggle("⏱️ Automatischer Scan (60s)", value=False)

# --- 7. SCANNER LOGIK ---
st.title("💎 Aktien-Radar Pro")

if st.button("🚀 Scanner starten", type="primary") or auto_refresh:
    symbols = [s.strip().upper() for s in ticker_text.split(",") if s.strip()]
    results = []
    
    prog = st.progress(0)
    for idx, sym in enumerate(symbols):
        try:
            t = yf.Ticker(sym)
            h = t.history(period="60d")
            
            if not h.empty and len(h) > 20:
                # RSI 14
                delta = h['Close'].diff()
                up = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
                down = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                rsi_val = 100 - (100 / (1 + (up / down))).iloc[-1]
                
                if rsi_val <= rsi_limit:
                    info = t.info
                    p = info.get('currentPrice') or h['Close'].iloc[-1]
                    
                    # Kennzahlen
                    peg = info.get('pegRatio') or info.get('trailingPegRatio')
                    fcf = info.get('freeCashflow')
                    m_cap = info.get('marketCap')
                    fcf_yield = (fcf / m_cap * 100) if fcf and m_cap else 0
                    
                    cash = info.get('totalCash')
                    debt = info.get('totalDebt')
                    net_debt = (debt - cash) if (debt is not None and cash is not None) else info.get('netDebt')
                    
                    target = info.get('targetMeanPrice')
                    pot = ((target - p) / p * 100) if target else 0
                    
                    # Bewertung Logik
                    bewertung = "Neutral"
                    if peg and isinstance(peg, (int, float)):
                        if peg < 1.0 and pot > 15: bewertung = "Unterbewertet"
                        elif peg > 2.5: bewertung = "Überbewertet"
                    
                    results.append({
                        "Name": info.get('shortName', sym),
                        "Symbol": sym,
                        "Kurs": round(p, 2),
                        "Bid": info.get('bid', '-'),
                        "Ask": info.get('ask', '-'),
                        "Heute %": round(((p - info.get('previousClose', p)) / info.get('previousClose', p)) * 100, 2),
                        "RSI": round(rsi_val, 1),
                        "PEG": round(peg, 2) if isinstance(peg, (int, float)) else "-",
                        "FCF Yield %": round(fcf_yield, 1),
                        "Netto-Schulden": net_debt,
                        "Rating": info.get('recommendationKey', '-').replace('_', ' ').capitalize(),
                        "Potential %": round(pot, 1),
                        "Bewertung": bewertung
                    })
        except: continue
        prog.progress((idx + 1) / len(symbols))
    
    st.session_state.scan_results = results
    st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

# --- 8. ANZEIGE DER ERGEBNISSE ---
if st.session_state.scan_results:
    st.write(f"Zuletzt aktualisiert: **{st.session_state.last_update}**")
    df = pd.DataFrame(st.session_state.scan_results)
    
    # Styling Funktionen
    def color_growth(val):
        try:
            v = float(val)
            return 'color: green' if v > 0 else 'color: red' if v < 0 else ''
        except: return ''

    def color_debt(val):
        try:
            if val < 0: return 'background-color: #d4edda; color: #155724' # Net Cash
            if val > 0: return 'background-color: #f8d7da; color: #721c24' # Schulden
        except: pass
        return ''

    styled_df = df.style.applymap(color_growth, subset=['Heute %', 'Potential %'])\
                        .applymap(color_debt, subset=['Netto-Schulden'])
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # --- DETAIL ANALYSE ---
    st.subheader("📉 Detail-Analyse & Zukunft")
    selected = st.selectbox("Aktie wählen:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.scan_results])
    active_sym = selected.split("(")[-1].replace(")", "")
    
    if active_sym:
        stock_obj = yf.Ticker(active_sym)
        det_info = stock_obj.info
        
        tab_chart, tab_info = st.tabs(["📊 Chart", "🔮 Unternehmensprofil"])
        
        with tab_chart:
            data = stock_obj.history(period="1y")
            fig = go.Figure(data=[go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'])])
            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_white", height=500, title=f"Trend: {active_sym}")
            st.plotly_chart(fig, use_container_width=True)
            
        with tab_info:
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.write("**Profil:**")
                st.write(det_info.get('longBusinessSummary', "Keine Beschreibung verfügbar."))
            with col_b:
                st.metric("Forward KGV", det_info.get('forwardPE', '-'))
                st.metric("Kursziel (Avg)", format_money(det_info.get('targetMeanPrice')))

# --- 9. EXPERTEN BRIEFING ---
st.divider()
col_l, col_r = st.columns(2)
with col_l:
    st.info("📊 **Stefan Waldhauser (HGI)**")
    for n in get_rss_briefing("https://hightechinvesting.substack.com/feed"):
        st.markdown(f"• [{n['title']}]({n['link']})")
with col_r:
    st.info("🐻 **Simon Weishar (Szew)**")
    for n in get_rss_briefing("https://szew.substack.com/feed"):
        st.markdown(f"• [{n['title']}]({n['link']})")

if auto_refresh:
    time.sleep(60)
    st.rerun()
