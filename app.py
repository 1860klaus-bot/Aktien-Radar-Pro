import streamlit as st
import yfinance as yf
import pandas as pd
import time
import feedparser
import urllib.parse
import plotly.graph_objects as go
from datetime import datetime

# --- Konfiguration der Seite ---
st.set_page_config(page_title="Aktien-Radar Pro", page_icon="🌍", layout="wide")

# --- 1. DATEN-LISTEN (KONSTANTEN) ---
HGI_TICKERS = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP"
SZEW_TICKERS = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"

DAX_LISTE = "716460, 723610, 840400, 710000, 766403, 555750, BASF11, BAY001, 519000, 514000, 623100, ENAG99, ADS.DE, HEN3.DE, IFX.DE, MUV2.DE, RWE.DE, AIR.DE"
US_TECH_LISTE = "AAPL, MSFT, AMZN, TSLA, NVDA, GOOGL, META, NFLX, PYPL, AMD, INTC, CSCO"
GLOBAL_TOP = "AAPL, MSFT, NVDA, SAP.DE, SIE.DE, ALV.DE, KO, MCD, V, JPM"
FAVORITEN = "NVDA, TSLA, ANGI, PLTR, COIN, AMD, RHM.DE, TUI1.DE"

WKN_MAP = {
    "716460": "SAP.DE", "723610": "SIE.DE", "840400": "ALV.DE", 
    "710000": "MBG.DE", "766403": "VOW3.DE", "555750": "DTE.DE",
    "BASF11": "BAS.DE", "BAY001": "BAYN.DE", "519000": "BMW.DE",
    "623100": "IFX.DE", "ENAG99": "EOAN.DE", "ADS.DE": "ADS.DE"
}

# --- 2. SESSION STATE INITIALISIERUNG ---
# Verhindert das "Verschwinden" der Daten beim Rerun
if 'ticker_input' not in st.session_state:
    st.session_state.ticker_input = FAVORITEN
if 'rsi_limit' not in st.session_state:
    st.session_state.rsi_limit = 85
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None

# --- 3. HILFSFUNKTIONEN ---
def get_rss_news(url):
    try:
        feed = feedparser.parse(url)
        return [{'title': e.title, 'link': e.link} for e in feed.entries[:3]]
    except Exception:
        return []

def load_list_callback(text):
    st.session_state.ticker_input = text

# --- 4. SEITENLEISTE (UI & LOGIK) ---
st.sidebar.header("📂 Portfolios & Listen")

# Standard-Listen laden
col1, col2 = st.sidebar.columns(2)
with col1:
    st.button("🇩🇪 DAX", on_click=load_list_callback, args=(DAX_LISTE,))
    st.button("🌍 Global", on_click=load_list_callback, args=(GLOBAL_TOP,))
with col2:
    st.button("🇺🇸 US Tech", on_click=load_list_callback, args=(US_TECH_LISTE,))
    st.button("⭐ Favoriten", on_click=load_list_callback, args=(FAVORITEN,))

st.sidebar.divider()
st.sidebar.subheader("🧠 Experten-Portfolios")
cexp1, cexp2 = st.sidebar.columns(2)
with cexp1:
    st.button("📥 HGI", on_click=load_list_callback, args=(HGI_TICKERS,))
with cexp2:
    st.button("📥 Szew", on_click=load_list_callback, args=(SZEW_TICKERS,))

# Ticker Eingabefeld
ticker_text = st.sidebar.text_area("Aktien-Symbole (Kürzel):", value=st.session_state.ticker_input, height=120)
st.session_state.ticker_input = ticker_text # Update state

# Einstellungen
st.sidebar.divider()
st.session_state.rsi_limit = st.sidebar.slider("RSI-Limit (Maximalwert)", 10, 100, st.session_state.rsi_limit)
auto_refresh = st.sidebar.toggle("⏱️ Automatischer Scan", value=False)
show_briefing = st.sidebar.checkbox("🧠 Experten-Briefing anzeigen", value=True)

# --- 5. HAUPTPROGRAMM: SCANNER ---
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
                # RSI 14 Tage
                delta = history['Close'].diff()
                gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
                loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                
                if rsi_val <= st.session_state.rsi_limit:
                    info = stock.info
                    price = info.get('currentPrice') or history['Close'].iloc[-1]
                    prev_c = info.get('previousClose', price)
                    day_change = ((price - prev_c) / prev_c) * 100
                    
                    scan_results.append({
                        "Name": info.get('shortName', sym),
                        "Symbol": sym,
                        "Kurs": f"{price:.2f}",
                        "Heute %": f"{day_change:+.2f}%",
                        "RSI": round(rsi_val, 1),
                        "PEG": info.get('pegRatio', '-'),
                        "Potential %": f"{((info.get('targetMeanPrice', price) - price) / price) * 100:.1f}%" if info.get('targetMeanPrice') else "-"
                    })
        except: pass
        prog_bar.progress((i + 1) / len(symbols))
    
    st.session_state.scan_results = scan_results
    st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

# --- 6. ANZEIGE DER ERGEBNISSE ---
if st.session_state.scan_results:
    st.caption(f"Letztes Update: {st.session_state.get('last_update', 'Gerade eben')}")
    df_results = pd.DataFrame(st.session_state.scan_results)
    st.dataframe(df_results, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # --- PROFI-CHART ---
    st.subheader("📉 Detail-Analyse & Charts")
    selected_name = st.selectbox("Aktie für Chart wählen:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.scan_results])
    active_sym = selected_name.split("(")[-1].replace(")", "")
    
    if active_sym:
        c_hist = yf.Ticker(active_sym).history(period="1y")
        tools = st.multiselect("Indikatoren umschalten:", ["Bollinger Bänder", "SMA 50", "SMA 200"], default=["Bollinger Bänder", "SMA 200"])
        
        fig = go.Figure(data=[go.Candlestick(x=c_hist.index, open=c_hist['Open'], high=c_hist['High'], low=c_hist['Low'], close=c_hist['Close'], name="Kurs")])
        
        if "Bollinger Bänder" in tools:
            ma = c_hist['Close'].rolling(20).mean(); sd = c_hist['Close'].rolling(20).std()
            fig.add_trace(go.Scatter(x=c_hist.index, y=ma+2*sd, line=dict(color='rgba(173,216,230,0.5)', width=1), name="Boll Oben"))
            fig.add_trace(go.Scatter(x=c_hist.index, y=ma-2*sd, line=dict(color='rgba(173,216,230,0.5)', width=1), fill='tonexty', name="Boll Unten"))
        if "SMA 50" in tools:
            fig.add_trace(go.Scatter(x=c_hist.index, y=c_hist['Close'].rolling(50).mean(), line=dict(color='blue', width=1), name="SMA 50"))
        if "SMA 200" in tools:
            fig.add_trace(go.Scatter(x=c_hist.index, y=c_hist['Close'].rolling(200).mean(), line=dict(color='red', width=2), name="SMA 200"))
            
        fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_white", height=500, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, use_container_width=True)

# --- 7. EXPERTEN BRIEFING ---
if show_briefing:
    st.divider()
    col_l, col_r = st.columns(2)
    with col_l:
        st.info("📊 **Stefan Waldhauser (HGI)**")
        st.link_button("📈 Wikifolio", "https://www.wikifolio.com/de/de/w/wf0stwtech")
        st.link_button("📝 Substack", "https://hightechinvesting.substack.com")
        for n in get_rss_news("https://hightechinvesting.substack.com/feed"):
            st.markdown(f"• [{n['title']}]({n['link']})")
    with col_r:
        st.info("🐻 **Simon Weishar (Szew)**")
        st.link_button("📈 Wikifolio", "https://www.wikifolio.com/de/de/w/wf00szew01")
        st.link_button("📝 Substack", "https://szew.substack.com")
        for n in get_rss_news("https://szew.substack.com/feed"):
            st.markdown(f"• [{n['title']}]({n['link']})")

if auto_refresh:
    time.sleep(60)
    st.rerun()
