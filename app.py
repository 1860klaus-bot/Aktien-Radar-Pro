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
                project_id = config.get('project_id')
                firebase_admin.initialize_app(cred, {
                    'projectId': project_id,
                })
                return firestore.client(project=project_id)
            else:
                # Lokale Fallback-Initialisierung
                firebase_admin.initialize_app()
                return firestore.client()
        except Exception as e:
            st.sidebar.error(f"Datenbank-Fehler: {e}")
            return None
    else:
        try:
            config_str = globals().get("__firebase_config")
            if config_str:
                config = json.loads(config_str)
                return firestore.client(project=config.get('project_id'))
            return firestore.client()
        except:
            return None

db = get_db_connection()
app_id = globals().get("__app_id", "default-app-id")
user_id = "default_user"

# --- 2. PERSISTENZ-FUNKTIONEN ---
def save_favorites_to_db(ticker_string):
    if not db: 
        st.sidebar.warning("Cloud-Speicher nicht verfügbar.")
        return
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc_ref.set({"list": ticker_string, "updated_at": datetime.now()})
        st.sidebar.success("✅ Favoriten gespeichert!")
    except Exception as e:
        st.sidebar.error(f"Fehler: {e}")

def load_favorites_from_db():
    default_favs = "NVDA, TSLA, ANGI, PLTR, COIN, AMD, RHM.DE, TUI1.DE"
    if not db: return default_favs
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("list", default_favs)
    except: pass
    return default_favs

# --- 3. DATEN-LISTEN (VORGABEN) ---
HGI_TICKERS = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP"
SZEW_TICKERS = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"

DAX_LISTE = "SAP.DE, SIE.DE, ALV.DE, MBG.DE, VOW3.DE, DTE.DE, BAS.DE, BAYN.DE, BMW.DE, ADS.DE, IFX.DE, RHM.DE, TUI1.DE, LHA.DE, DHL.DE, BEI.DE, CON.DE, CBK.DE, DBK.DE, RWE.DE, AIR.DE"
MDAX_LISTE = "PUM.DE, HNR1.DE, LEG.DE, EVK.DE, KES.DE, KGX.DE, AFX.DE, FPE3.DE, HEI.DE, JUN3.DE"
NASDAQ_100 = "AAPL, MSFT, AMZN, NVDA, GOOGL, META, TSLA, AVGO, PEP, COST, ADBE, AMD, NFLX, PLTR, COIN"
GLOBAL_TOP = "AAPL, MSFT, NVDA, SAP.DE, SIE.DE, ALV.DE, KO, MCD, V, JPM, NOVO-B.CO, ASML.AS, MC.PA"

# --- 4. APP SETUP ---
st.set_page_config(page_title="Aktien-Radar Pro", page_icon="🌍", layout="wide")

if 'ticker_input' not in st.session_state:
    st.session_state.ticker_input = load_favorites_from_db()
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None

# Styling
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

def format_curr(val):
    if val is None or pd.isna(val): return "-"
    if abs(val) >= 1e9: return f"{val/1e9:.2f} Mrd"
    if abs(val) >= 1e6: return f"{val/1e6:.2f} Mio"
    return str(round(val, 2))

# --- 5. SIDEBAR ---
st.sidebar.header("⚙️ Menü")

with st.sidebar.expander("📊 Indizes laden", expanded=False):
    if st.button("DAX 40", use_container_width=True): st.session_state.ticker_input = DAX_LISTE
    if st.button("MDAX", use_container_width=True): st.session_state.ticker_input = MDAX_LISTE
    if st.button("Nasdaq 100", use_container_width=True): st.session_state.ticker_input = NASDAQ_100

with st.sidebar.expander("🧠 Experten", expanded=True):
    col1, col2 = st.columns(2)
    if col1.button("HGI", use_container_width=True): st.session_state.ticker_input = HGI_TICKERS
    if col2.button("Szew", use_container_width=True): st.session_state.ticker_input = SZEW_TICKERS
    if st.button("🌍 Global Top", use_container_width=True): st.session_state.ticker_input = GLOBAL_TOP

st.sidebar.divider()
ticker_text = st.sidebar.text_area("⭐ Favoriten-Liste:", value=st.session_state.ticker_input, height=120)
st.session_state.ticker_input = ticker_text

if st.sidebar.button("💾 Liste speichern", use_container_width=True):
    save_favorites_to_db(ticker_text)

st.sidebar.divider()
st.sidebar.link_button("🔍 aktien.guide", "https://aktien.guide", use_container_width=True)

st.sidebar.divider()
rsi_max = st.sidebar.slider("RSI-Filter", 10, 100, 85)
auto_refresh = st.sidebar.toggle("⏱️ Auto-Update", value=False)
interval = st.sidebar.slider("Intervall (Sek)", 10, 300, 60)

# --- 6. SCANNER ---
st.title("💎 Aktien-Radar Pro")

@st.cache_data(ttl=300)
def scan_tickers(symbols_tuple, rsi_limit):
    results = []
    symbols = [s.strip().upper() for s in list(symbols_tuple) if s.strip()]
    
    status = st.empty()
    progress = st.progress(0)
    
    for i, sym in enumerate(symbols):
        status.text(f"Scanne {sym}... ({i+1}/{len(symbols)})")
        try:
            t = yf.Ticker(sym)
            h = t.history(period="60d")
            if h.empty or len(h) < 20: continue
            
            # RSI
            delta = h['Close'].diff()
            up = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            down = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rsi = 100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1])))
            
            if rsi <= rsi_limit:
                info = t.info
                p = info.get('currentPrice') or h['Close'].iloc[-1]
                prev = info.get('previousClose', p)
                
                # Kennzahlen
                peg = info.get('pegRatio') or info.get('trailingPegRatio') or "-"
                fcf = info.get('freeCashflow')
                mcap = info.get('marketCap')
                fcf_y = (fcf/mcap*100) if fcf and mcap else 0
                
                cash = info.get('totalCash')
                debt = info.get('totalDebt')
                net_debt = (debt - cash) if (debt is not None and cash is not None) else info.get('netDebt')
                
                target = info.get('targetMeanPrice')
                potential = ((target - p) / p * 100) if target else 0
                
                # Bewertung Logik
                bewertung = "Neutral"
                if isinstance(peg, (int, float)):
                    if peg < 1.0 and potential > 15: bewertung = "Unterbewertet"
                    elif (peg < 1.5 or fcf_y > 5) and rsi < 45: bewertung = "Günstig"
                    elif peg > 2.2 or rsi > 75: bewertung = "Überbewertet"
                elif potential > 30 and rsi < 40:
                    bewertung = "Unterbewertet"
                
                results.append({
                    "Name": info.get('shortName', sym),
                    "Symbol": sym,
                    "Kurs": round(p, 2),
                    "Bid": info.get('bid', '-'),
                    "Ask": info.get('ask', '-'),
                    "Heute %": round(((p-prev)/prev)*100, 2),
                    "RSI": round(rsi, 1),
                    "Umsatz-W. %": round(info.get('revenueGrowth', 0)*100, 1),
                    "PEG": peg if peg == "-" else round(float(peg), 2),
                    "FCF Yield %": round(fcf_y, 1),
                    "Netto-Schuld": net_debt,
                    "Rating": info.get('recommendationKey', '-').replace('_',' ').capitalize(),
                    "Potential %": round(potential, 1),
                    "Bewertung": bewertung
                })
        except: continue
        progress.progress((i + 1) / len(symbols))
        
    status.empty()
    progress.empty()
    return results

if st.button("🚀 Jetzt scannen", type="primary") or auto_refresh:
    data = scan_tickers(tuple(ticker_text.split(",")), rsi_max)
    st.session_state.scan_results = data
    st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

# --- 7. ANZEIGE ---
if st.session_state.scan_results:
    st.write(f"Zuletzt aktualisiert: **{st.session_state.last_update}**")
    df = pd.DataFrame(st.session_state.scan_results)
    
    st.dataframe(
        df.style.applymap(color_metric, subset=['Heute %', 'Potential %', 'FCF Yield %', 'Umsatz-W. %'])
        .applymap(color_rsi, subset=['RSI'])
        .applymap(color_debt, subset=['Netto-Schuld'])
        .applymap(color_valuation, subset=['Bewertung'])
        .format({
            "Heute %": "{:+.2f}%", "Potential %": "{:+.1f}%", "Umsatz-W. %": "{:+.1f}%", "FCF Yield %": "{:.1f}%",
            "Netto-Schuld": lambda x: format_curr(x)
        }),
        use_container_width=True, hide_index=True
    )
    
    st.divider()
    
    # Detail Analyse
    selected = st.selectbox("Wähle Aktie für Chart:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.scan_results])
    active_sym = selected.split("(")[-1].replace(")", "")
    
    if active_sym:
        st.subheader(f"Analyse: {selected}")
        c_left, c_right = st.columns([2, 1])
        with c_left:
            hist_d = yf.Ticker(active_sym).history(period="1y")
            
            show_ind = st.multiselect("Indikatoren:", ["SMA 50", "SMA 200", "Bollinger"], default=["SMA 50", "SMA 200"])
            
            fig = go.Figure(data=[go.Candlestick(x=hist_d.index, open=hist_d['Open'], high=hist_d['High'], low=hist_d['Low'], close=hist_d['Close'], name="Kurs")])
            
            if "SMA 50" in show_ind:
                fig.add_trace(go.Scatter(x=hist_d.index, y=hist_d['Close'].rolling(50).mean(), line=dict(color='cyan', width=1), name="SMA 50"))
            if "SMA 200" in show_ind:
                fig.add_trace(go.Scatter(x=hist_d.index, y=hist_d['Close'].rolling(200).mean(), line=dict(color='red', width=1.5), name="SMA 200"))
            if "Bollinger" in show_ind:
                ma = hist_d['Close'].rolling(20).mean()
                sd = hist_d['Close'].rolling(20).std()
                fig.add_trace(go.Scatter(x=hist_d.index, y=ma+2*sd, line=dict(color='rgba(173,216,230,0.3)'), name="Boll Oben"))
                fig.add_trace(go.Scatter(x=hist_d.index, y=ma-2*sd, line=dict(color='rgba(173,216,230,0.3)'), fill='tonexty', name="Boll Unten"))

            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=450, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
        with c_right:
            i = yf.Ticker(active_sym).info
            st.metric("Forward KGV", i.get('forwardPE', '-'))
            st.metric("EBITDA Marge", f"{i.get('ebitdaMargins', 0)*100:.1f}%")
            st.write("**Profil:**")
            st.caption(i.get('longBusinessSummary', "N/A")[:500] + "...")

# --- 8. EXPERTEN FEEDS ---
st.divider()
cl, cr = st.columns(2)
with cl:
    st.info("📊 **Stefan Waldhauser (HGI)**")
    st.link_button("📈 Wikifolio HGI", "https://www.wikifolio.com/de/de/w/wf0stwtech", use_container_width=True)
    f = feedparser.parse("https://hightechinvesting.substack.com/feed")
    for e in f.entries[:3]: st.markdown(f"• [{e.title}]({e.link})")
with cr:
    st.info("🐻 **Simon Weishar (Szew)**")
    st.link_button("📈 Wikifolio Szew", "https://www.wikifolio.com/de/de/w/wf00szew01", use_container_width=True)
    f = feedparser.parse("https://szew.substack.com/feed")
    for e in f.entries[:3]: st.markdown(f"• [{e.title}]({e.link})")

if auto_refresh:
    time.sleep(interval)
    st.rerun()
