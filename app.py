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

def format_currency(val):
    if val is None or pd.isna(val): return "-"
    abs_val = abs(val)
    suffix = ""
    if abs_val >= 1_000_000_000:
        res = val / 1_000_000_000
        suffix = " Mrd"
    elif abs_val >= 1_000_000:
        res = val / 1_000_000
        suffix = " Mio"
    else:
        res = val
    return f"{res:.2f}{suffix}"

def color_negative_red_positive_green(val):
    try:
        if isinstance(val, str):
            if 'Mrd' in val or 'Mio' in val: return ''
            val = float(val.replace('%', '').replace('+', ''))
        color = 'green' if val > 0 else 'red' if val < 0 else 'white'
        return f'color: {color}'
    except:
        return ''

def color_net_debt(val):
    try:
        if val is None or pd.isna(val): return ''
        if val < 0: return 'background-color: #d4edda; color: #155724'
        if val > 0: return 'background-color: #f8d7da; color: #721c24'
    except: pass
    return ''

def color_rsi(val):
    try:
        color = 'lightgreen' if val <= 35 else 'tomato' if val >= 70 else 'white'
        return f'background-color: {color}; color: black' if color != 'white' else ''
    except: return ''

def color_valuation(val):
    if val == "Unterbewertet": return 'background-color: #006400; color: white'
    if val == "Günstig": return 'background-color: #90EE90; color: black'
    if val == "Überbewertet": return 'background-color: #8B0000; color: white'
    return ''

def color_rating(val):
    rating_colors = {
        "Starker Kauf": 'background-color: #004d00; color: white',
        "Kauf": 'background-color: #008000; color: white',
        "Halten": 'background-color: #cca300; color: black',
        "Verkauf": 'background-color: #e65c00; color: white',
        "Starker Verkauf": 'background-color: #990000; color: white'
    }
    return rating_colors.get(val, '')

# --- 4. SEITENLEISTE (UI & LOGIK) ---
st.sidebar.header("📂 Portfolios & Listen")

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

ticker_text = st.sidebar.text_area("Aktien-Symbole (Kürzel):", value=st.session_state.ticker_input, height=120)
st.session_state.ticker_input = ticker_text

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
                delta = history['Close'].diff()
                gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
                loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                
                if rsi_val <= st.session_state.rsi_limit:
                    info = stock.info
                    price = info.get('currentPrice') or history['Close'].iloc[-1]
                    prev_c = info.get('previousClose', price)
                    day_change = ((price - prev_c) / prev_c) * 100
                    
                    # Zukunftsaussichten & Fundamentals
                    f_pe = info.get('forwardPE', '-')
                    rev_growth = info.get('revenueGrowth', 0)
                    total_cash = info.get('totalCash')
                    total_debt = info.get('totalDebt')
                    net_debt = (total_debt - total_cash) if (total_debt is not None and total_cash is not None) else info.get('netDebt')
                    
                    fcf = info.get('freeCashflow')
                    m_cap = info.get('marketCap')
                    fcf_yield = (fcf / m_cap) * 100 if fcf and m_cap else 0
                    
                    peg = info.get('pegRatio') or info.get('trailingPegRatio') or info.get('priceToEarningsGrowth')
                    target = info.get('targetMeanPrice')
                    potential = ((target - price) / price) * 100 if target else 0
                    
                    raw_rating = info.get('recommendationKey', '-')
                    rating_map = {'strong_buy': 'Starker Kauf', 'buy': 'Kauf', 'hold': 'Halten', 'underperform': 'Verkauf', 'sell': 'Starker Verkauf'}
                    display_rating = rating_map.get(raw_rating, raw_rating.capitalize())
                    
                    bewertung = "Neutral"
                    if peg and isinstance(peg, (int, float)):
                        if peg < 1.0 and potential > 15: bewertung = "Unterbewertet"
                        elif (peg < 1.5 or fcf_yield > 5) and rsi_val < 45: bewertung = "Günstig"
                        elif peg > 2.2 or rsi_val > 75: bewertung = "Überbewertet"
                    
                    scan_results.append({
                        "Name": info.get('shortName', sym),
                        "Symbol": sym,
                        "Kurs": round(price, 2),
                        "Heute %": round(day_change, 2),
                        "RSI": round(rsi_val, 1),
                        "Umsatz-Wachst. %": round(rev_growth * 100, 1) if rev_growth else 0,
                        "Forward KGV": f_pe,
                        "Netto-Schulden": net_debt,
                        "FCF Yield %": round(fcf_yield, 1),
                        "PEG": round(peg, 2) if peg is not None and isinstance(peg, (int,float)) else "-",
                        "Potential %": round(potential, 1) if target else 0,
                        "Rating": display_rating,
                        "Bewertung": bewertung
                    })
        except: pass
        prog_bar.progress((i + 1) / len(symbols))
    
    st.session_state.scan_results = scan_results
    st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

# --- 6. ANZEIGE DER ERGEBNISSE ---
if st.session_state.scan_results:
    st.caption(f"Letztes Update: {st.session_state.get('last_update', 'Gerade eben')}")
    df_results = pd.DataFrame(st.session_state.scan_results)
    
    styled_df = df_results.style.applymap(
        color_negative_red_positive_green, 
        subset=['Heute %', 'Umsatz-Wachst. %', 'FCF Yield %', 'Potential %']
    ).applymap(color_net_debt, subset=['Netto-Schulden']).applymap(color_rsi, subset=['RSI']).applymap(color_valuation, subset=['Bewertung']).applymap(color_rating, subset=['Rating']).format({
        "Heute %": "{:+.2f}%", "Umsatz-Wachst. %": "{:+.1f}%", "FCF Yield %": "{:.1f}%", "Potential %": "{:+.1f}%",
        "Netto-Schulden": lambda x: format_currency(x),
        "Forward KGV": lambda x: f"{x:.1f}" if isinstance(x, (int, float)) else "-"
    })
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # --- DETAIL ANALYSE SEKTION ---
    st.subheader("📉 Detail-Analyse & Zukunftsausblick")
    selected_name = st.selectbox("Aktie für Detail-Analyse wählen:", [f"{r['Name']} ({r['Symbol']})" for r in st.session_state.scan_results])
    active_sym = selected_name.split("(")[-1].replace(")", "")
    
    if active_sym:
        detail_stock = yf.Ticker(active_sym)
        det_info = detail_stock.info
        
        tab1, tab2 = st.tabs(["📊 Technischer Chart", "🔮 Zukunft & Profil"])
        
        with tab1:
            c_hist = detail_stock.history(period="1y")
            tools = st.multiselect("Indikatoren umschalten:", ["Bollinger Bänder", "SMA 50", "SMA 200"], default=["Bollinger Bänder", "SMA 200"])
            fig = go.Figure(data=[go.Candlestick(x=c_hist.index, open=c_hist['Open'], high=c_hist['High'], low=c_hist['Low'], close=c_hist['Close'], name="Kurs")])
            if "Bollinger Bänder" in tools:
                ma = c_hist['Close'].rolling(20).mean(); sd = c_hist['Close'].rolling(20).std()
                fig.add_trace(go.Scatter(x=c_hist.index, y=ma+2*sd, line=dict(color='rgba(173,216,230,0.5)', width=1), name="Boll Oben"))
                fig.add_trace(go.Scatter(x=c_hist.index, y=ma-2*sd, line=dict(color='rgba(173,216,230,0.5)', width=1), fill='tonexty', name="Boll Unten"))
            if "SMA 50" in tools: fig.add_trace(go.Scatter(x=c_hist.index, y=c_hist['Close'].rolling(50).mean(), line=dict(color='blue', width=1), name="SMA 50"))
            if "SMA 200" in tools: fig.add_trace(go.Scatter(x=c_hist.index, y=c_hist['Close'].rolling(200).mean(), line=dict(color='red', width=2), name="SMA 200"))
            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_white", height=500, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            col_inf1, col_inf2 = st.columns([2, 1])
            with col_inf1:
                st.write("### 📖 Unternehmensprofil & Strategie")
                summary = det_info.get('longBusinessSummary', "Keine Beschreibung verfügbar.")
                st.write(summary)
            with col_inf2:
                st.write("### 🚀 Wachstumsprognosen")
                st.metric("Forward KGV (Next Year)", det_info.get('forwardPE', '-'))
                st.metric("Gewinnwachstum (proj.)", f"{det_info.get('earningsGrowth', 0)*100:.1f}%" if det_info.get('earningsGrowth') else "N/A")
                st.metric("Kursziel (High)", format_currency(det_info.get('targetHighPrice')))
                st.metric("Kursziel (Low)", format_currency(det_info.get('targetLowPrice')))

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
