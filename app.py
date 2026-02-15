import streamlit as st
import yfinance as yf
import pandas as pd

# Seitentitel
st.set_page_config(page_title="Aktien Scanner Pro", layout="wide")
st.title("📈 Aktien Scanner: RSI & Fundamentalanalyse")

# Sidebar für Eingaben
st.sidebar.header("Einstellungen")
tickers_input = st.sidebar.text_area("Aktien-Symbole (kommagetrennt)", "AAPL, MSFT, TSLA, NVDA, GOOGL, AMZN, META, AMD, INTC, PYPL")
rsi_window = st.sidebar.slider("RSI Zeitraum", 10, 30, 14)

# Funktion zur RSI Berechnung
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# Daten abrufen und analysieren
if st.sidebar.button("Analyse starten"):
    tickers = [x.strip() for x in tickers_input.split(',')]
    analysis_data = []

    progress_bar = st.progress(0)
    
    for i, ticker in enumerate(tickers):
        try:
            # 1. Historische Daten für RSI laden (letzte 3 Monate reichen)
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            
            if len(hist) > rsi_window:
                # RSI Berechnen
                hist['RSI'] = calculate_rsi(hist, rsi_window)
                current_rsi = hist['RSI'].iloc[-1]
                
                # 2. Fundamentaldaten laden
                info = stock.info
                
                # Relevante Kennzahlen extrahieren
                current_price = info.get('currentPrice', 0)
                forward_pe = info.get('forwardPE', None) # Erwartetes KGV
                rev_growth = info.get('revenueGrowth', 0) # Umsatzwachstum
                target_price = info.get('targetMeanPrice', 0) # Kursziel der Analysten
                
                # Bewertung Logik (Vereinfacht)
                valuation_status = "Neutral"
                if forward_pe:
                    if forward_pe < 15: valuation_status = "Unterbewertet (Günstig)"
                    elif forward_pe > 35: valuation_status = "Überbewertet (Teuer)"
                
                # Potenzial berechnen
                upside = 0
                if target_price and current_price:
                    upside = ((target_price - current_price) / current_price) * 100

                analysis_data.append({
                    "Symbol": ticker,
                    "Preis ($)": round(current_price, 2),
                    "RSI (14)": round(current_rsi, 2),
                    "Bewertung (KGV fwd)": round(forward_pe, 2) if forward_pe else "N/A",
                    "Status": valuation_status,
                    "Umsatzwachstum (%)": round(rev_growth * 100, 2) if rev_growth else "N/A",
                    "Analysten Ziel ($)": target_price,
                    "Potenzial (%)": round(upside, 2)
                })
        except Exception as e:
            st.error(f"Fehler bei {ticker}: {e}")
        
        # Fortschrittsbalken updaten
        progress_bar.progress((i + 1) / len(tickers))

    # Ergebnisse anzeigen
    if analysis_data:
        df = pd.DataFrame(analysis_data)
        
        # Styling des Dataframes
        def highlight_opportunities(row):
            colors = [''] * len(row)
            # RSI Logik: Grün wenn überverkauft (<30), Rot wenn überkauft (>70)
            if row['RSI (14)'] < 30:
                colors[2] = 'background-color: #90EE90; color: black' # Hellgrün
            elif row['RSI (14)'] > 70:
                colors[2] = 'background-color: #FF7F7F; color: black' # Rot
            
            # Potenzial Logik: Grün wenn > 20% Potenzial
            if row['Potenzial (%)'] > 20:
                 colors[7] = 'background-color: #90EE90; color: black'
            
            return colors

        st.subheader("Analyse Ergebnisse")
        st.dataframe(df.style.apply(highlight_opportunities, axis=1), use_container_width=True)
        
        st.markdown("""
        **Legende:**
        * **RSI < 30:** Aktie ist technisch "überverkauft" (könnte steigen).
        * **RSI > 70:** Aktie ist technisch "überkauft" (könnte fallen).
        * **Potenzial:** Basierend auf dem durchschnittlichen Kursziel der Analysten.
        """)
    else:
        st.warning("Keine Daten gefunden.")
