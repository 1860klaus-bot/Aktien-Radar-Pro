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

# Experten-Daten (HGI - Waldhauser & Szew - Weishar)
HGI_TICKERS = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP"
SZEW_TICKERS = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"

# WKN zu Ticker Mapping für deutsche Werte
WKN_MAP = {
    "716460": "SAP.DE", "723610": "SIE.DE", "840400": "ALV.DE", 
    "710000": "MBG.DE", "766403": "VOW3.DE", "555750": "DTE.DE"
}

# --- Hilfsfunktionen ---
def get_rss_news(url):
    """Lädt aktuelle Artikel von einem RSS-Feed."""
    try:
        feed = feedparser.parse(url)
        return [{'title': e.title, 'link': e.link} for e in feed.entries[:3]]
    except Exception:
        return []

def update_ticker_state(text):
    """Aktualisiert den Zustand der Ticker-Eingabe."""
    st.session_state.ticker_text_area = text

# --- Seitenleiste ---
st.sidebar.header("📂 Portfolios & Filter")

# Initialisierung des Session States
if 'ticker_text_area' not in st.session_state:
    st.session_state.ticker_text_area = "NVDA, TSLA, AAPL"

# Buttons zum Laden der Experten-Listen
col1, col2 = st.sidebar.columns(2)
with col1:
    st.button("📥 HGI (Waldhauser)", on_click=update_ticker_state, args=(HGI_TICKERS,))
with col2:
    st.button("📥 Szew (Weishar)", on_click=update_ticker_state, args=(SZEW_TICKERS,))

# Texteingabe für Ticker
tickers_input = st.sidebar.text_area("Aktien-Symbole (kommagetrennt):", key="ticker_text_area", height=150)

# Filter-Einstellungen
rsi_threshold = st.sidebar.slider("RSI-Limit (Filter)", 10, 100, 85)
is_live = st.sidebar.toggle("⏱️ Automatischer Scan", value=False)
show_briefing = st.sidebar.checkbox("🧠 Experten-News anzeigen", value=True)

# --- Hauptprogramm: Scanner ---
st.title("💎 Aktien-Radar Pro")

# Scan-Logik auslösen
if st.button("🚀 Scanner starten", type="primary") or is_live:
    symbols = [WKN_MAP.get(s.strip().upper(), s.strip().upper()) for s in tickers_input.split(",") if s.strip()]
    scan_results = []
    
    prog_bar = st.progress(0)
    for i, sym in enumerate(symbols):
        try:
            stock_data = yf.Ticker(sym)
            history = stock_data.history(period="250d")
            
            if not history.empty and len(history) > 30:
                # RSI 14 Tage Berechnung
                delta = history['Close'].diff()
                gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
                loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                
                # Filterung nach RSI
                if rsi_val <= rsi_threshold:
                    info = stock_data.info
                    price = info.get('currentPrice') or history['Close'].iloc[-1]
                    prev_close = info.get('previousClose', price)
                    day_change = ((price - prev_close) / prev_close) * 100
                    
                    scan_results.append({
                        "Name": info.get('shortName', sym),
                        "Symbol": sym,
                        "Kurs": f"{price:.2f}",
                        "Heute %": f"{day_change:+.2f}%",
                        "RSI (14)": round(rsi_val, 1),
                        "PEG": info.get('pegRatio', '-'),
                        "Potential %": f"{((info.get('targetMeanPrice', price) - price) / price) * 100:.1f}%" if info.get('targetMeanPrice') else "-"
                    })
        except Exception:
            pass
        prog_bar.progress((i + 1) / len(symbols))
    
    st.session_state.current_results = scan_results
    st.session_state.last_sync = datetime.now().strftime("%H:%M:%S")

# --- Anzeige der Ergebnisse ---
if 'current_results' in st.session_state:
    st.caption(f"Letzte Aktualisierung: {st.session_state.last_sync}")
    st.dataframe(pd.DataFrame(st.session_state.current_results), use_container_width=True, hide_index=True)
    
    st.divider()
    
    # --- Interaktiver Profichart ---
    st.subheader("📉 Interaktiver Kerzenchart (Candlestick)")
    if st.session_state.current_results:
        chart_choice = st.selectbox("Wähle eine Aktie für den Chart:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.current_results])
        active_symbol = chart_choice.split("(")[-1].replace(")", "")
        
        if active_symbol:
            df_chart = yf.Ticker(active_symbol).history(period="1y")
            chart_tools = st.multiselect("Indikatoren umschalten:", ["Bollinger Bänder", "SMA 50", "SMA 200"], default=["Bollinger Bänder", "SMA 200"])
            
            # Plotly Candlestick
            fig = go.Figure(data=[go.Candlestick(
                x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name="Kurs"
            )])
            
            # Bollinger Bänder hinzufügen
            if "Bollinger Bänder" in chart_tools:
                ma20 = df_chart['Close'].rolling(20).mean()
                std20 = df_chart['Close'].rolling(20).std()
                fig.add_trace(go.Scatter(x=df_chart.index, y=ma20 + 2*std20, line=dict(color='rgba(173, 216, 230, 0.4)', width=1), name="Boll Oben"))
                fig.add_trace(go.Scatter(x=df_chart.index, y=ma20 - 2*std20, line=dict(color='rgba(173, 216, 230, 0.4)', width=1), fill='tonexty', name="Boll Unten"))
            
            # Gleitende Durchschnitte
            if "SMA 50" in chart_tools:
                fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Close'].rolling(50).mean(), line=dict(color='blue', width=1.2), name="SMA 50"))
            
            if "SMA 200" in chart_tools:
                fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Close'].rolling(200).mean(), line=dict(color='red', width=2), name="SMA 200"))
                
            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_white", height=550, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Keine Ergebnisse gefunden. Bitte passe die Filter an oder starte einen neuen Scan.")

# --- Experten-Bereich ---
if show_briefing:
    st.divider()
    col_left, col_right = st.columns(2)
    with col_left:
        st.info("📊 **Stefan Waldhauser (HGI)**")
        st.link_button("📈 Wikifolio", "https://www.wikifolio.com/de/de/w/wf0stwtech")
        st.link_button("📝 Substack", "https://hightechinvesting.substack.com")
        for news in get_rss_news("https://hightechinvesting.substack.com/feed"):
            st.markdown(f"• [{news['title']}]({news['link']})")
            
    with col_right:
        st.info("🐻 **Simon Weishar (Szew)**")
        st.link_button("📈 Wikifolio", "https://www.wikifolio.com/de/de/w/wf00szew01")
        st.link_button("📝 Substack", "https://szew.substack.com")
        for news in get_rss_news("https://szew.substack.com/feed"):
            st.markdown(f"• [{news['title']}]({news['link']})")

# Auto-Refresh Logik
if is_live:
    time.sleep(60)
    st.rerun()
