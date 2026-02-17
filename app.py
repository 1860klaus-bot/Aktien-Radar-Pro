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

# --- 1. FIREBASE INITIALISIERUNG (Fix für ValueError) ---
@st.cache_resource
def get_db_connection():
    """Initialisiert Firebase stabil mit expliziter Projekt-ID."""
    if not firebase_admin._apps:
        try:
            config_str = globals().get("__firebase_config")
            if config_str:
                config = json.loads(config_str)
                cred = credentials.Certificate(config)
                # Projekt-ID explizit aus der Config auslesen
                project_id = config.get('project_id')
                firebase_admin.initialize_app(cred, {
                    'projectId': project_id,
                })
                # Client explizit mit der Projekt-ID anfordern
                return firestore.client(project=project_id)
            else:
                # Lokale Entwicklung
                firebase_admin.initialize_app()
                return firestore.client()
        except Exception as e:
            st.sidebar.error(f"Datenbank-Initialisierung fehlgeschlagen: {e}")
            return None
    else:
        # Wenn App bereits da, Client mit Projekt-ID holen
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
        st.sidebar.warning("Speichern nicht möglich: Keine Datenbankverbindung.")
        return
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc_ref.set({"list": ticker_string, "updated_at": datetime.now()})
        st.sidebar.success("✅ Favoriten gespeichert!")
    except Exception as e:
        st.sidebar.error(f"Speichern fehlgeschlagen: {e}")

def load_favorites_from_db():
    if not db: return "NVDA, TSLA, AAPL, SAP.DE"
    try:
        doc_ref = db.collection("artifacts").document(app_id).collection("users").document(user_id).collection("settings").document("favorites")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("list", "NVDA, TSLA, AAPL, SAP.DE")
    except: pass
    return "NVDA, TSLA, AAPL, SAP.DE"

# --- 3. DATEN-LISTEN (INDIZES) ---
HGI_TICKERS = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP"
SZEW_TICKERS = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"

DAX_LISTE = "SAP.DE, SIE.DE, ALV.DE, MBG.DE, VOW3.DE, DTE.DE, BAS.DE, BAYN.DE, BMW.DE, ADS.DE, IFX.DE, RHM.DE, TUI1.DE, LHA.DE, DHL.DE, BEI.DE, CON.DE, CBK.DE, DBK.DE, RWE.DE"
MDAX_LISTE = "PUM.DE, HNR1.DE, LEG.DE, EVK.DE, KES.DE, KGX.DE, AFX.DE, FPE3.DE, HEI.DE, JUN3.DE"
SDAX_LISTE = "SDF.DE, GFG.DE, BC8.DE, MOR.DE, ADV.DE, HDD.DE, HHFA.DE, EUZ.DE"

SP500_TOP = "AAPL, MSFT, AMZN, NVDA, GOOGL, META, BRK-B, LLY, AVGO, JPM, UNH, V, XOM, MA, PG, COST"
NASDAQ_100 = "AAPL, MSFT, AMZN, NVDA, GOOGL, META, TSLA, AVGO, PEP, COST, ADBE, AMD, NFLX, PLTR, COIN"
DOW_JONES = "UNH, GS, HD, MSFT, CRM, AMGN, V, CAT, MCD, BA, VZ, DIS, KO, JPM"
GLOBAL_TOP = "AAPL, MSFT, NVDA, SAP.DE, SIE.DE, ALV.DE, KO, MCD, V, JPM, NOVO-B.CO, ASML.AS"

# --- 4. APP KONFIGURATION ---
st.set_page_config(page_title="Aktien-Radar Pro", page_icon="🌍", layout="wide")

if 'ticker_input' not in st.session_state:
    st.session_state.ticker_input = load_favorites_from_db()
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None

# --- STYLING FUNKTIONEN ---
def color_growth(val):
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
    if abs_val >= 1_000_000_000: return f"{val / 1_000_000_000:.2f} Mrd"
    elif abs_val >= 1_000_000: return f"{val / 1_000_000:.2f} Mio"
    return str(round(val, 2))

# --- 5. SEITENLEISTE ---
st.sidebar.header("⚙️ Konfiguration")

with st.sidebar.expander("🇩🇪 Deutsche Indizes", expanded=False):
    if st.button("DAX 40", use_container_width=True): st.session_state.ticker_input = DAX_LISTE
    if st.button("MDAX", use_container_width=True): st.session_state.ticker_input = MDAX_LISTE
    if st.button("SDAX", use_container_width=True): st.session_state.ticker_input = SDAX_LISTE

with st.sidebar.expander("🇺🇸 US Indizes", expanded=False):
    if st.button("S&P 500 (Top)", use_container_width=True): st.session_state.ticker_input = SP500_TOP
    if st.button("Nasdaq 100", use_container_width=True): st.session_state.ticker_input = NASDAQ_100
    if st.button("Dow Jones 30", use_container_width=True): st.session_state.ticker_input = DOW_JONES

with st.sidebar.expander("🧠 Experten & Favoriten", expanded=True):
    col_e1, col_e2 = st.columns(2)
    if col_e1.button("HGI", use_container_width=True): st.session_state.ticker_input = HGI_TICKERS
    if col_e2.button("Szew", use_container_width=True): st.session_state.ticker_input = SZEW_TICKERS
    if st.button("🌍 Global Top", use_container_width=True): st.session_state.ticker_input = GLOBAL_TOP

st.sidebar.divider()
st.sidebar.subheader("⭐ Meine Favoriten")
ticker_text = st.sidebar.text_area("Ticker-Liste:", value=st.session_state.ticker_input, height=120)
st.session_state.ticker_input = ticker_text

if st.sidebar.button("💾 Liste dauerhaft speichern", use_container_width=True):
    save_favorites_to_db(ticker_text)

st.sidebar.divider()
st.sidebar.link_button("🔍 aktien.guide öffnen", "https://aktien.guide", use_container_width=True)

st.sidebar.divider()
rsi_limit = st.sidebar.slider("RSI-Filter (Maximalwert)", 10, 100, 85)
auto_refresh = st.sidebar.toggle("⏱️ Automatischer Scan (60s)", value=False)

# --- 6. CORE SCANNER ---
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
            
            # RSI 14
            delta = h['Close'].diff()
            up = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            down = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rsi = 100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1])))
            
            if rsi <= rsi_max:
                info = t.info
                p = info.get('currentPrice') or h['Close'].iloc[-1]
                prev = info.get('previousClose', p)
                
                rev_growth = info.get('revenueGrowth', 0)
                earn_growth = info.get('earningsGrowth', 0)
                
                peg = info.get('pegRatio') or info.get('trailingPegRatio') or "-"
                fcf = info.get('freeCashflow')
                mcap = info.get('marketCap')
                fcf_yield = (fcf/mcap*100) if fcf and mcap else 0
                
                cash = info.get('totalCash')
                debt = info.get('totalDebt')
                net_debt = (debt - cash) if (debt is not None and cash is not None) else info.get('netDebt')
                
                target = info.get('targetMeanPrice')
                potential = ((target - p) / p * 100) if target else 0
                
                bewertung = "Neutral"
                if peg and isinstance(peg, (int, float)):
                    if peg < 1.0 and potential > 15: bewertung = "Unterbewertet"
                    elif (peg < 1.5 or fcf_yield > 5) and rsi < 45: bewertung = "Günstig"
                    elif peg > 2.2 or rsi > 75: bewertung = "Überbewertet"
                
                results.append({
                    "Name": info.get('shortName', sym),
                    "Symbol": sym,
                    "Kurs": round(p, 2),
                    "Bid": info.get('bid', '-'),
                    "Ask": info.get('ask', '-'),
                    "Heute %": round(((p-prev)/prev)*100, 2),
                    "RSI": round(rsi, 1),
                    "Umsatz-Wachst. %": round(rev_growth * 100, 1) if rev_growth else 0,
                    "Gewinn-Wachst. %": round(earn_growth * 100, 1) if earn_growth else 0,
                    "PEG": round(peg, 2) if isinstance(peg, (int, float)) else "-",
                    "FCF Yield %": round(fcf_yield, 1),
                    "Netto-Schuld": net_debt,
                    "Rating": info.get('recommendationKey', '-').replace('_', ' ').capitalize(),
                    "Potential %": round(potential, 1),
                    "Bewertung": bewertung
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

# --- 7. ANZEIGE ---
if st.session_state.scan_results:
    st.write(f"Zuletzt aktualisiert: **{st.session_state.last_update}**")
    df = pd.DataFrame(st.session_state.scan_results)
    
    styled_df = df.style.applymap(color_growth, subset=['Heute %', 'Potential %', 'FCF Yield %', 'Umsatz-Wachst. %', 'Gewinn-Wachst. %'])\
                        .applymap(color_rsi, subset=['RSI'])\
                        .applymap(color_debt, subset=['Netto-Schuld'])\
                        .applymap(color_valuation, subset=['Bewertung'])\
                        .format({
                            "Heute %": "{:+.2f}%", "Potential %": "{:+.1f}%", "Umsatz-Wachst. %": "{:+.1f}%", 
                            "Gewinn-Wachst. %": "{:+.1f}%", "FCF Yield %": "{:.1f}%",
                            "Netto-Schuld": lambda x: format_currency(x)
                        })
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.subheader("📉 Detail-Analyse & Zukunftsausblick")
    selected = st.selectbox("Aktie wählen:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.scan_results])
    active_sym = selected.split("(")[-1].replace(")", "")
    
    if active_sym:
        st.subheader(f"Analyse: {selected}")
        c1, c2 = st.columns([2, 1])
        with c1:
            hist_obj = yf.Ticker(active_sym)
            hist_d = hist_obj.history(period="1y")
            
            # Indikatoren-Auswahl
            selected_indicators = st.multiselect(
                "Technische Indikatoren wählen:",
                ["Bollinger Bänder", "SMA 20", "SMA 50", "SMA 200"],
                default=["SMA 50", "SMA 200"]
            )
            
            fig = go.Figure(data=[go.Candlestick(
                x=hist_d.index, open=hist_d['Open'], high=hist_d['High'], low=hist_d['Low'], close=hist_d['Close'],
                name="Kurs"
            )])
            
            # SMA 20
            if "SMA 20" in selected_indicators:
                sma20 = hist_d['Close'].rolling(window=20).mean()
                fig.add_trace(go.Scatter(x=hist_d.index, y=sma20, line=dict(color='yellow', width=1), name="SMA 20"))
            
            # SMA 50
            if "SMA 50" in selected_indicators:
                sma50 = hist_d['Close'].rolling(window=50).mean()
                fig.add_trace(go.Scatter(x=hist_d.index, y=sma50, line=dict(color='cyan', width=1.5), name="SMA 50"))
                
            # SMA 200
            if "SMA 200" in selected_indicators:
                sma200 = hist_d['Close'].rolling(window=200).mean()
                fig.add_trace(go.Scatter(x=hist_d.index, y=sma200, line=dict(color='red', width=2), name="SMA 200"))
                
            # Bollinger Bänder
            if "Bollinger Bänder" in selected_indicators:
                sma_bb = hist_d['Close'].rolling(window=20).mean()
                std_bb = hist_d['Close'].rolling(window=20).std()
                upper_bb = sma_bb + (std_bb * 2)
                lower_bb = sma_bb - (std_bb * 2)
                
                fig.add_trace(go.Scatter(x=hist_d.index, y=upper_bb, line=dict(color='rgba(173, 216, 230, 0.4)', width=1), name="BB Oben"))
                fig.add_trace(go.Scatter(x=hist_d.index, y=lower_bb, line=dict(color='rgba(173, 216, 230, 0.4)', width=1), fill='tonexty', fillcolor='rgba(173, 216, 230, 0.1)', name="BB Unten"))

            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=500, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            detail_i = yf.Ticker(active_sym).info
            st.metric("Forward KGV", detail_i.get('forwardPE', '-'))
            st.metric("EBITDA Marge", f"{detail_i.get('ebitdaMargins', 0)*100:.1f}%" if detail_i.get('ebitdaMargins') else "-")
            st.write("**Unternehmensprofil:**")
            st.caption(detail_i.get('longBusinessSummary', "Keine Info verfügbar.")[:600] + "...")

# RSS FEEDS
st.divider()
col_l, col_r = st.columns(2)
with col_l:
    st.info("📊 **Stefan Waldhauser (HGI)**")
    feed_hgi = feedparser.parse("https://hightechinvesting.substack.com/feed")
    for entry in feed_hgi.entries[:3]: st.markdown(f"• [{entry.title}]({entry.link})")
with col_r:
    st.info("🐻 **Simon Weishar (Szew)**")
    feed_szew = feedparser.parse("https://szew.substack.com/feed")
    for entry in feed_szew.entries[:3]: st.markdown(f"• [{entry.title}]({entry.link})")

if auto_refresh:
    time.sleep(60)
    st.rerun()
