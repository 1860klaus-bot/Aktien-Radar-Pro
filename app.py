import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Aktien-Radar Global", page_icon="🌍", layout="wide")
st.title("💎 Aktien-Radar: Global (DE & US)")

# Seitenleiste mit Tipps für deutsche Aktien
st.sidebar.header("Filter-Einstellungen")
st.sidebar.info("🇩🇪 **Tipp für deutsche Aktien:**\nNutze die Endung **.DE** für Xetra.\nBeispiele: `SAP.DE`, `SIE.DE`, `ALV.DE`, `VOW3.DE`")

# Gemischte Standard-Liste (Deutschland & USA)
default_tickers = "SAP.DE, SIE.DE, ALV.DE, MBG.DE, VOW3.DE, NVDA, TSLA, ANGI"
ticker_input = st.sidebar.text_area("Aktien-Liste (Kürzel mit Komma)", default_tickers)
rsi_limit = st.sidebar.slider("Max. RSI (14 Tage)", 10, 100, 87)

# Button zum Aktualisieren
if st.sidebar.button("🔄 Weltweite Kurse prüfen"):
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    results = []
    news_data = {}
    status_text = st.empty()
    
    for ticker in tickers:
        status_text.text(f"Lade Daten (Global): {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            
            # 1. Historie laden
            df_hist = stock.history(period="300d")
            
            if not df_hist.empty and len(df_hist) > 14:
                # RSI Berechnung
                delta = df_hist['Close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
                rsi_val = 100 - (100 / (1 + (avg_gain / avg_loss))).iloc[-1]
                
                # 2. Fundamentaldaten & Währung
                info = stock.info
                currency = info.get('currency', '???') # Währung (EUR/USD)
                
                # Preise
                current_price = info.get('currentPrice') or info.get('regularMarketPrice') or df_hist['Close'].iloc[-1]
                previous_close = info.get('previousClose') or df_hist['Close'].iloc[-2]
                change_pct = ((current_price - previous_close) / previous_close) * 100 if current_price and previous_close else 0
                
                # Kursziele (Achtung: Bei deutschen Aktien manchmal weniger Daten)
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
                        "Ticker": ticker, 
                        "Kurs": round(current_price, 2),
                        "Währung": currency, # Wichtig für DE-Aktien
                        "Trend": f"{round(change_pct, 2)}%",
                        "RSI (14)": round(float(rsi_val), 1),
                        "Umsatz-Wachst.": growth_display, 
                        "PEG": peg_display,
                        "Erw. Gewinn (%)": round(upside, 1), 
                        "Bewertung": status,
                        "Q-Gewinn (Mio)": round(last_q_profit, 2) if last_q_profit is not None else "N/A",
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
    
    wenn Ergebnisse:
 st.Unterüberschrift(„🌍 Globaler Marktüberblick“)
 df_res = pd.DataFrame(Erbnisse)
        
        # Styling
        def Stil_Änderung(val):
 wenn isinstance(val, str) und "%" in Wert:
 num = Schweben(Wert.Streifen('%'))
 Zurückgeben 'Farbe: grün' wenn Nummer > 0 sonst 'Farbe: rot'
 Zurückgeben ''
            
 def highlight_bewährung(val):
 Rückgeben 'Hintergrundfarbe: #90EE90; Farbe: schwarz' wenn val == "Unterbewortet" sonst ''

 def Stil_rsi(val):
 versuchen:
 wenn schweben(val) < 30: zurückgeben „Farbe: grün; Schriftstücke: fett“
 Elif schweben(val) > 70: zurückgeben 'Farbe: rot'
 außer: passieren
 Zurückgeben ''

 def Stil_peg(val):
 versuchen:
 num = schweben(val)
 wenn Nummer > 1: kurzgeben 'Farbe: rot'
 Elif Nummer > 0: zurückgeben 'Farbe: grün'
 außer: passieren
 Zurückgeben ''

 st.Datenrahmen(df_res.Stil
 .Applikemap (style_change, Teilmenge=['Trend'])
 .Applikemap (highlight_valuation, Teilmenge=['Bewährung'])
 .Applikemap (style_rsi, Teilmenge=['RSI (14)'])
 .Applikemap (style_peg, Teilmenge=['PEG']), 
 use_container_width=Wahr)
        
 st.Teiler ()
 st.Unterüberschrift("📰 Nachrichten-Ticker")
 für Ticker in news_data:
 mit st.Expander(f"Infos zu {Ticker}"):
 Artikel = Nachrichten_Daten[Ticker]
 wenn Artikel:
 für Artikel in Artikel:
 t = Artikel.bekommen('Titel') oder Artikel.bekommen('Überschrift') oder "Neuigkeiten"
 l = Artikel.bekommen('Link') oder Artikel.bekommen('URL') oder f"https://de.finance.yahoo.com/quote/{Ticker}"
 Kneipe = Artikel.bekommen('Verlag') oder "Yahoo"
 st.Markdown(f"**[{t}]({l})**")
 st.Untertitel(f"Quelle: {Kneipe}")
 sonst:
 # Link zur deutschen Yahoo Seite
 st.Info(f"Keine direkten Nachrichten. [Hier klicken für Yahoo Finanzen DE](https://de.finance.yahoo.com/quote/{Ticker})")
 sonst:
 st.Warnung(„Keine Treffer unter dem Limit“)
