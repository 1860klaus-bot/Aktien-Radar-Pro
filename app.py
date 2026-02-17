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

# --- 1. FIREBASE INITIALISIERUNG (Stabilisierte Version) ---
@st.cache_resource
def get_db_connection():
    """Initialisiert Firebase stabil mit expliziter Projekt-ID."""
    if not firebase_admin._apps:
        try:
            config_str = globals().get("__firebase_config")
            if config_str:
                config = json.loads(config_str)
                cred = credentials.Certificate(config)
                project_id = config.get('project_id') or config.get('projectId')
                firebase_admin.initialize_app(cred, {'projectId': project_id})
                return firestore.client(project=project_id)
            else:
                # Lokale Entwicklung
                firebase_admin.initialize_app()
                return firestore.client()
        except Exception as e:
            st.sidebar.error(f"DB-Fehler: {e}")
            return None
    else:
        try:
            config_str = globals().get("__firebase_config")
            if config_str:
                config = json.loads(config_str)
                pid = config.get('project_id') or config.get('projectId')
                return firestore.client(project=pid)
            return firestore.client()
        except: return None

db = get_db_connection()
app_id = globals().get("__app_id", "default-app-id")
user_id = "default_user_radar"

# --- 2. PERSISTENZ ---
def save_favorites_to_db(ticker_string):
    if not db: return
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc_ref.set({"list": ticker_string, "updated_at": datetime.now()})
        st.sidebar.success("✅ Cloud-Favoriten gespeichert!")
    except: pass

def load_favorites_from_db():
    default_favs = "NVDA, TSLA, ANGI, PLTR, COIN, AMD, RHM.DE, TUI1.DE"
    if not db: return default_favs
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc = doc_ref.get()
        if doc.exists: return doc.to_dict().get("list", default_favs)
    except: pass
    return default_favs

# --- 3. DATEN-LISTEN (BÖRSEN & INDIZES) ---
# DEUTSCHLAND
DAX_LISTE = "SAP.DE, SIE.DE, ALV.DE, MBG.DE, VOW3.DE, DTE.DE, BAS.DE, BAYN.DE, BMW.DE, ADS.DE, IFX.DE, RHM.DE, TUI1.DE, LHA.DE, DHL.DE, BEI.DE, CON.DE, CBK.DE, DBK.DE, RWE.DE, AIR.DE, P911.DE, SY1.DE, SRT3.DE, MRK.DE, HEI.DE, MTX.DE, HEN3.DE, EON.DE, VNA.DE"
MDAX_LISTE = "PUM.DE, HNR1.DE, LEG.DE, EVK.DE, KES.DE, KGX.DE, AFX.DE, FPE3.DE, HEI.DE, JUN3.DE, GXI.DE, TAG.DE, WCH.DE, NEM.DE, AIXA.DE, FRA.DE, JEN.DE, LPK.DE, RTL.DE, GFG.DE, BC8.DE"
SDAX_LISTE = "SDF.DE, GFG.DE, BC8.DE, MOR.DE, ADV.DE, HDD.DE, HHFA.DE, EUZ.DE, BYW6.DE, S92.DE, JEN.DE, AT1.DE, 1COV.DE"
TECDAX_LISTE = "SAP.DE, IFX.DE, DTE.DE, AFX.DE, AIXA.DE, JEN.DE, NEM.DE, O2D.DE, MOR.DE, SRT3.DE, ADV.DE, EVT.DE, VAR1.DE"

# USA
SP500_LISTE = "AAPL, MSFT, AMZN, NVDA, GOOGL, META, BRK-B, LLY, AVGO, JPM, UNH, V, XOM, MA, PG, COST, JNJ, HD, ABBV, MRK, CRM, CVX, BAC, WMT, PEP"
NASDAQ_LISTE = "AAPL, MSFT, AMZN, NVDA, GOOGL, META, TSLA, AVGO, PEP, COST, AZN, CSCO, TMUS, ADBE, AMD, NFLX, INTC, TXN, AMAT, QCOM, PLTR, COIN"
DOW_LISTE = "UNH, GS, HD, MSFT, CRM, AMGN, V, CAT, MCD, BA, VZ, DIS, KO, JPM, JNJ, PG, AAPL, MMM, IBM, AXP"

# EXPERTEN & GLOBAL
HGI_TICKERS = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP"
SZEW_TICKERS = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"
GLOBAL_TOP = "AAPL, MSFT, NVDA, SAP.DE, SIE.DE, ALV.DE, KO, MCD, V, JPM, NOVO-B.CO, ASML.AS, MC.PA, OR.PA, RMS.PA"
FAVORITEN_INIT = "NVDA, TSLA, ANGI, PLTR, COIN, AMD, RHM.DE, TUI1.DE"

# --- 4. APP KONFIGURATION ---
st.set_page_config(page_title="Aktien-Radar Pro", page_icon="🌍", layout="wide")

if 'ticker_input' not in st.session_state:
    st.session_state.ticker_input = load_favorites_from_db()
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None

# --- STYLING FUNKTIONEN ---
def color_metric(val):
    try:
        v = float(str(val).replace('%', '').replace('+', ''))
        return 'color: #00ff00' if v > 0 else 'color: #ff4b4b' if v < 0 else ''
    except: return ''

def color_rsi(val):
    try:
        color = 'lightgreen' if val <= 35 else 'tomato' if val >= 70 else 'white'
        return f'background-color: {color}; color: black' if color != 'white' else ''
    except: return ''

def color_debt(val):
    try:
        if val < 0: return 'background-color: rgba(0, 255, 0, 0.1); color: #00ff00'
        if val > 0: return 'background-color: rgba(255, 75, 75, 0.1); color: #ff4b4b'
    except: pass
    return ''

def color_valuation(val):
    if val == "Unterbewertet": return 'background-color: #006400; color: white'
    if val == "Günstig": return 'background-color: #90EE90; color: black'
    if val == "Überbewertet": return 'background-color: #8B0000; color: white'
    return ''

def format_currency(val):
    if val is None or pd.isna(val): return "-"
    abs_val = abs(val)
    if abs_val >= 1e9: return f"{val / 1e9:.2f} Mrd"
    elif abs_val >= 1e6: return f"{val / 1e6:.2f} Mio"
    return str(round(val, 2))

# --- 5. SIDEBAR ---
st.sidebar.header("⚙️ Konfiguration")

if db: st.sidebar.success("🟢 Cloud aktiv")
else: st.sidebar.warning("🔴 Cloud offline")

# DEUTSCHLAND MENÜ
with st.sidebar.expander("🇩🇪 Deutsche Börse", expanded=False):
    if st.button("DAX 40 laden", use_container_width=True): st.session_state.ticker_input = DAX_LISTE
    if st.button("MDAX laden", use_container_width=True): st.session_state.ticker_input = MDAX_LISTE
    if st.button("SDAX laden", use_container_width=True): st.session_state.ticker_input = SDAX_LISTE
    if st.button("TecDAX laden", use_container_width=True): st.session_state.ticker_input = TECDAX_LISTE

# USA MENÜ
with st.sidebar.expander("🇺🇸 US-Börsen", expanded=False):
    if st.button("S&P 500 (Top) laden", use_container_width=True): st.session_state.ticker_input = SP500_LISTE
    if st.button("Nasdaq 100 laden", use_container_width=True): st.session_state.ticker_input = NASDAQ_LISTE
    if st.button("Dow Jones 30 laden", use_container_width=True): st.session_state.ticker_input = DOW_LISTE

# EXPERTEN & CLOUD
with st.sidebar.expander("🧠 Experten & Favoriten", expanded=True):
    col_e1, col_e2 = st.columns(2)
    if col_e1.button("HGI", use_container_width=True): st.session_state.ticker_input = HGI_TICKERS
    if col_e2.button("Szew", use_container_width=True): st.session_state.ticker_input = SZEW_TICKERS
    if st.button("🌍 Global Top laden", use_container_width=True): st.session_state.ticker_input = GLOBAL_TOP
    if st.button("📂 Cloud-Favoriten laden", use_container_width=True):
        st.session_state.ticker_input = load_favorites_from_db()
        st.rerun()

st.sidebar.divider()
ticker_text = st.sidebar.text_area("Ticker-Liste (Editierbar):", value=st.session_state.ticker_input, height=120)
st.session_state.ticker_input = ticker_text

if st.sidebar.button("💾 Liste dauerhaft speichern", use_container_width=True, type="primary"):
    save_favorites_to_db(ticker_text)

# DER WIEDEREINGEFÜGTE LINK
st.sidebar.link_button("🔍 aktien.guide öffnen", "https://aktien.guide", use_container_width=True)

st.sidebar.divider()
rsi_limit = st.sidebar.slider("RSI-Filter (Maximalwert)", 10, 100, 85)
auto_refresh = st.sidebar.toggle("⏱️ Auto-Update", value=False)
refresh_interval = st.sidebar.slider("Intervall (Sekunden)", 10, 300, 60)

# --- 6. CORE SCANNER ---
st.title("💎 Aktien-Radar Pro")

@st.cache_data(ttl=60)
def fetch_stock_data_robust(symbols_tuple, rsi_max, force_key=0):
    results = []
    symbols = [s.strip().upper() for s in list(symbols_tuple) if s.strip()]
    status_msg = st.empty()
    bar = st.progress(0)
    
    for i, sym in enumerate(symbols):
        status_msg.info(f"Aktualisiere: **{sym}** ({i+1}/{len(symbols)})")
        try:
            t = yf.Ticker(sym)
            h = t.history(period="60d")
            if h.empty or len(h) < 2: continue
            
            # RSI 14
            delta = h['Close'].diff()
            up = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            down = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rsi = 100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1])))
            
            if rsi <= rsi_max:
                info = {}
                try:
                    info = t.info
                    time.sleep(0.15) # Schutz gegen Rate Limits
                except: info = {}
                
                p = info.get('currentPrice') or h['Close'].iloc[-1]
                prev = info.get('previousClose') or h['Close'].iloc[-2]
                
                peg = info.get('pegRatio') or info.get('trailingPegRatio') or "-"
                fcf = info.get('freeCashflow', 0)
                mcap = info.get('marketCap', 1)
                fcf_yield = (fcf/mcap*100) if fcf and mcap else 0
                
                cash = info.get('totalCash', 0)
                debt = info.get('totalDebt', 0)
                net_debt = (debt - cash) if (debt and cash) else info.get('netDebt', 0)
                
                target = info.get('targetMeanPrice')
                potential = ((target - p) / p * 100) if target else 0
                
                # Bewertung Logik
                bewertung = "Neutral"
                if isinstance(peg, (int, float)):
                    if peg < 1.0 and potential > 15: bewertung = "Unterbewertet"
                    elif (peg < 1.5 or fcf_yield > 5) and rsi < 45: bewertung = "Günstig"
                    elif peg > 2.5: bewertung = "Überbewertet"
                
                results.append({
                    "Name": info.get('shortName', sym),
                    "Symbol": sym,
                    "Kurs": round(p, 2),
                    "Bid": info.get('bid', '-'),
                    "Ask": info.get('ask', '-'),
                    "Heute %": round(((p-prev)/prev)*100, 2),
                    "RSI": round(rsi, 1),
                    "Umsatz-Wachst. %": round(info.get('revenueGrowth', 0) * 100, 1),
                    "PEG": round(peg, 2) if isinstance(peg, (int, float)) else "-",
                    "FCF Yield %": round(fcf_yield, 1),
                    "Netto-Schuld": net_debt,
                    "Rating": str(info.get('recommendationKey', '-')).replace('_', ' ').capitalize(),
                    "Potential %": round(potential, 1),
                    "Bewertung": bewertung,
                    "Summary": info.get('longBusinessSummary', "N/A"),
                    "ForwardPE": info.get('forwardPE', '-'),
                    "EbitdaMarge": info.get('ebitdaMargins', 0)
                })
        except: continue
        bar.progress((i + 1) / len(symbols))
    
    status_msg.empty()
    bar.empty()
    return results

if st.button("🚀 Scanner starten", type="primary"):
    st.cache_data.clear()
    sym_list = tuple(ticker_text.split(","))
    if sym_list:
        st.session_state.scan_results = fetch_stock_data_robust(sym_list, rsi_limit, force_key=time.time())
        st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

# --- 7. ANZEIGE ---
if st.session_state.scan_results:
    st.write(f"Zuletzt aktualisiert: **{st.session_state.last_update}**")
    df_all = pd.DataFrame(st.session_state.scan_results)
    
    display_cols = ["Name", "Symbol", "Kurs", "Bid", "Ask", "Heute %", "RSI", 
                    "Umsatz-Wachst. %", "PEG", "FCF Yield %", "Netto-Schuld", 
                    "Rating", "Potential %", "Bewertung"]
    
    styled_df = df_all[display_cols].style.applymap(color_metric, subset=['Heute %', 'Potential %', 'FCF Yield %', 'Umsatz-Wachst. %'])\
                        .applymap(color_rsi, subset=['RSI'])\
                        .applymap(color_debt, subset=['Netto-Schuld'])\
                        .applymap(color_valuation, subset=['Bewertung'])\
                        .format({
                            "Heute %": "{:+.2f}%", "Potential %": "{:+.1f}%", "Umsatz-Wachst. %": "{:+.1f}%", "FCF Yield %": "{:.1f}%",
                            "Netto-Schuld": lambda x: format_currency(x)
                        })
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # DETAIL ANALYSE
    selected = st.selectbox("Aktie für Detail-Analyse wählen:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.scan_results])
    active_sym = selected.split("(")[-1].replace(")", "")
    active_data = next((item for item in st.session_state.scan_results if item["Symbol"] == active_sym), None)
    
    if active_sym and active_data:
        c1, c2 = st.columns([2, 1])
        with c1:
            hist_d = yf.Ticker(active_sym).history(period="1y")
            show_ind = st.multiselect("Indikatoren:", ["Bollinger", "SMA 50", "SMA 200"], default=["SMA 50", "SMA 200"])
            fig = go.Figure(data=[go.Candlestick(x=hist_d.index, open=hist_d['Open'], high=hist_d['High'], low=hist_d['Low'], close=hist_d['Close'], name="Kurs")])
            if "SMA 50" in show_ind: fig.add_trace(go.Scatter(x=hist_d.index, y=hist_d['Close'].rolling(50).mean(), line=dict(color='cyan', width=1), name="SMA 50"))
            if "SMA 200" in show_ind: fig.add_trace(go.Scatter(x=hist_d.index, y=hist_d['Close'].rolling(200).mean(), line=dict(color='red', width=1.5), name="SMA 200"))
            if "Bollinger" in show_ind:
                ma = hist_d['Close'].rolling(20).mean(); sd = hist_d['Close'].rolling(20).std()
                fig.add_trace(go.Scatter(x=hist_d.index, y=ma+2*sd, line=dict(color='rgba(173,216,230,0.3)'), name="Boll Oben"))
                fig.add_trace(go.Scatter(x=hist_d.index, y=ma-2*sd, line=dict(color='rgba(173,216,230,0.3)'), fill='tonexty', name="Boll Unten"))
            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=400, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.metric("Forward KGV", active_data.get('ForwardPE', '-'))
            st.metric("EBITDA Marge", f"{active_data.get('EbitdaMarge', 0)*100:.1f}%")
            st.write("**Profil:**")
            st.caption(active_data.get('Summary', "N/A")[:600] + "...")

# --- 8. RSS & WIKIFOLIO ---
st.divider()
cl, cr = st.columns(2)
with cl:
    st.info("📊 Stefan Waldhauser (HGI)")
    st.link_button("📈 Wikifolio HGI", "https://www.wikifolio.com/de/de/w/wf0stwtech", use_container_width=True)
    f = feedparser.parse("https://hightechinvesting.substack.com/feed")
    for e in f.entries[:3]: st.markdown(f"• [{e.title}]({e.link})")
with cr:
    st.info("🐻 Simon Weishar (Szew)")
    st.link_button("📈 Wikifolio Szew", "https://www.wikifolio.com/de/de/w/wf00szew01", use_container_width=True)
    f = feedparser.parse("https://szew.substack.com/feed")
    for e in f.entries[:3]: st.markdown(f"• [{e.title}]({e.link})")

if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
