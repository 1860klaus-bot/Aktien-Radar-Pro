import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Aktien-Radar Global", page_icon="🌍", layout="wide")
st.title("💎 Aktien-Radar: Global (WKN & Ticker)")

# --- WKN DATENBANK (Erweitert: DAX 40 & US Top-Werte) ---
WKN_MAP = {
    # --- DEUTSCHLAND (DAX 40 Auszug) ---
    "A1EWWW": "ADS.DE",   "ADIDAS": "ADS.DE",
    "840400": "ALV.DE",   "ALLIANZ": "ALV.DE",
    "BASF11": "BAS.DE",   "BASF": "BAS.DE",
    "BAY001": "BAYN.DE",  "BAYER": "BAYN.DE",
    "520000": "BEI.DE",   "BEIERSDORF": "BEI.DE",
    "519000": "BMW.DE",   "BMW": "BMW.DE",
    "543900": "CON.DE",   "CONTINENTAL": "CON.DE",
    "CBK100": "CBK.DE",   "COMMERZBANK": "CBK.DE",
    "514000": "DBK.DE",   "DEUTSCHE BANK": "DBK.DE",
    "581005": "DB1.DE",   "DEUTSCHE BOERSE": "DB1.DE",
    "555750": "DTE.DE",   "TELEKOM": "DTE.DE",
    "DTR0CK": "DTG.DE",   "DAIMLER TRUCK": "DTG.DE",
    "ENAG99": "EOAN.DE",  "EON": "EOAN.DE",
    "604843": "HEN3.DE",  "HENKEL": "HEN3.DE",
    "623100": "IFX.DE",   "INFINEON": "IFX.DE",
    "710000": "MBG.DE",   "MERCEDES": "MBG.DE",
    "843002": "MUV2.DE",  "MUENCHENER RUECK": "MUV2.DE",
    "PAG911": "P911.DE",  "PORSCHE": "P911.DE",
    "703712": "RWE.DE",   "RWE": "RWE.DE",
    "716460": "SAP.DE",   "SAP": "SAP.DE",
    "723610": "SIE.DE",   "SIEMENS": "SIE.DE",
    "SHL100": "SHL.DE",   "SIEMENS HEALTHINEERS": "SHL.DE",
    "766403": "VOW3.DE",  "VW": "VOW3.DE",
    "A1ML7J": "VNA.DE",   "VONOVIA": "VNA.DE",
    "938914": "AIR.DE",   "AIRBUS": "AIR.DE", # Oft in DE gehandelt

    # --- USA (Tech & Blue Chips - WKN zu US-Ticker) ---
    "865985": "AAPL",     "APPLE": "AAPL",
    "870747": "MSFT",     "MICROSOFT": "MSFT",
    "906866": "AMZN",     "AMAZON": "AMZN",
    "A1CX3T": "TSLA",     "TESLA": "TSLA",
    "918422": "NVDA",     "NVIDIA": "NVDA",
    "A14Y6F": "GOOGL",    "ALPHABET A": "GOOGL",
    "A14Y6H": "GOOG",     "ALPHABET C": "GOOG",
    "A1JWVX": "META",     "META": "META",
    "552484": "NFLX",     "NETFLIX": "NFLX",
    "A14R7U": "PYPL",     "PAYPAL": "PYPL",
    "A1J5X3": "ANGI",     "ANGI": "ANGI",
    "850663": "KO",       "COCA COLA": "KO",
    "856958": "MCD",      "MCDONALDS": "MCD",
    "A0M240": "V",        "VISA": "V",
    "851399": "IBM",      "IBM": "IBM",
    "860853": "DIS",      "DISNEY": "DIS",
    "850517": "JPM",      "JP MORGAN": "JPM",
    "A0YJQ2": "BRK-B",    "BERKSHIRE": "BRK-B"
}

# Seitenleiste
st.sidebar.header("Filter-Einstellungen")
st.sidebar.info("💡 **Erweiterte WKN Suche!**\nUnterstützt jetzt fast alle DAX-Konzerne und die großen US-Tech-Werte.")

# Standard-Liste (Mix aus DE & US)
default_inputs = "716460, 723610, 840400, 865985, 918422, A1CX3T, A1J5X3, 906866"
ticker_input = st.sidebar.text_area("Aktien-Liste (WKN oder Kürzel)", default_inputs, height=150)
rsi_limit = st.sidebar.slider("Max. RSI (14 Tage)", 10, 100, 87)

# Button zum Aktualisieren
if st.sidebar.button("🔄 Kurse prüfen"):
    # Eingabe verarbeiten und WKNs übersetzen
    raw_inputs = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    tickers = []
    
    # Übersetzungsschleife
    for item in raw_inputs:
        if item in WKN_MAP:
            tickers.append(WKN_MAP[item])
        else:
            tickers.append(item) # Wenn nicht in WKN Liste, versuchen wir es als Ticker
            
    results = []
    news_data = {}
    status_text = st.empty()
    
    for ticker in tickers:
        status_text.text(f"Lade Daten: {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            
            # 1. Historie laden
            df_hist = stock.history(period="300d")
            
            if not df_hist.empty and len(df_hist) > 14:
                # RSI Berechnung (Wilder's Smoothing)
                delta = df_hist['Close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
                rsi_val = 100 - (100 / (1 + (avg_gain / avg_loss))).iloc[-1]
                
                # 2. Fundamentaldaten & Währung
                info = stock.info
                currency = info.get('currency', '???')
                name = info.get('shortName', ticker)
                
                # Preise
                current_price = info.get('currentPrice') or info.get('regularMarketPrice') or df_hist['Close'].iloc[-1]
                previous_close = info.get('previousClose') or df_hist['Close'].iloc[-2]
                change_pct = ((current_price - previous_close) / previous_close) * 100 if current_price and previous_close else 0
                
                # Kursziele
                target = info.get('targetMeanPrice', 0)
                upside = 0
                if target and current_price:
                    upside = ((target - current_price) / current_price) * 100
                
                # Umsatz & Wachstum
                rev_growth = info.get('revenueGrowth', 0) 
                
                # PEG Ratio
                peg_ratio = info.get('pegRatio')
                if peg_ratio is None:
                    peg_ratio = info.get('trailingPegRatio')
                
                # Gewinn (letztes Quartal)
                try:
                    last_q_profit = stock.quarterly_financials.loc['Net Income'].iloc[0] / 1_000_000
                except:
                    last_q_profit = None

                # Bewertung-Status
                status = "Unterbewertet" if (upside > 15 and rsi_val < 45) else "Neutral"
                if upside < 0: status = "Überbewertet"

                # Filter anwenden
                if rsi_val <= rsi_limit:
                    # Formatierung
                    peg_display = round(peg_ratio, 2) if peg_ratio else "N/A"
                    if peg_ratio is None:
                         fwd_pe = info.get('forwardPE')
                         if fwd_pe is None or fwd_pe < 0: peg_display = "Verlust"

                    growth_display = f"{round(rev_growth * 100, 2)}%" if rev_growth else "N/A"
                    
                    results.append({
                        "Name": name, 
                        "Kürzel": ticker,
                        "Kurs": round(current_price, 2),
                        "Währung": currency,
                        "Trend": f"{round(change_pct, 2)}%",
                        "RSI (14)": round(float(rsi_val), 1),
                        "Umsatz-Wachst.": growth_display, 
                        "PEG": peg_display,
                        "Erw. Gewinn (%)": round(upside, 1), 
                        "Bewertung": status
                    })
                    
                    # News-Abruf
                    try:
                        ticker_news = stock.news
                        if ticker_news:
                            news_data[ticker] = ticker_news[:3]
                        else:
                            news_data[ticker] = []
                    except:
                        news_data[ticker] = []
        except Exception as e:
            continue
            
    status_text.empty()
    
    if results:
        st.subheader("🌍 Globale Marktübersicht")
        df_res = pd.DataFrame(results)
        
        # Styling
        def style_change(val):
            if isinstance(val, str) and "%" in val:
                num = float(val.strip('%'))
                return 'color: green' if num > 0 else 'color: red'
            return ''
            
        def highlight_valuation(val):
            return 'background-color: #90EE90; color: black' if val == "Unterbewertet" else ''

        def style_rsi(val):
            try:
                if float(val) < 30: return 'color: green; font-weight: bold'
                elif float(val) > 70: return 'color: red'
            except: pass
            return ''

        def style_peg(val):
            try:
                if val == "Verlust": return 'color: red'
                num = float(val)
                if num > 1: return 'color: red'
                elif num > 0: return 'color: green'
            except: pass
            return ''

        st.dataframe(df_res.style
                     .applymap(style_change, subset=['Trend'])
                     .applymap(highlight_valuation, subset=['Bewertung'])
                     .applymap(style_rsi, subset=['RSI (14)'])
                     .applymap(style_peg, subset=['PEG']), 
                     use_container_width=True)
        
        st.divider()
        st.subheader("📰 Nachrichten-Ticker")
        for ticker in news_data:
            display_name = ticker
            # Versuche den echten Namen aus der WKN Map zu finden für die Anzeige
            for wkn, t in WKN_MAP.items():
                if t == ticker:
                    display_name = f"{wkn} ({ticker})"
                    break
            
            with st.expander(f"Infos zu {display_name}"):
                articles = news_data[ticker]
                if articles:
                    for item in articles:
                        t = item.get('title') or item.get('headline') or "News"
                        l = item.get('link') or item.get('url') or f"https://de.finance.yahoo.com/quote/{ticker}"
                        pub = item.get('publisher') or "Yahoo"
                        st.markdown(f"**[{t}]({l})**")
                        st.caption(f"Quelle: {pub}")
                else:
                    st.info(f"Keine direkten News. [Hier klicken für Yahoo Finanzen](https://de.finance.yahoo.com/quote/{ticker})")
    else:
        st.warning("Keine Treffer. Falls du eine WKN eingegeben hast, prüfe ob sie in der Liste ist oder nutze das Kürzel.")
