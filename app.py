import streamlit as st
import yfinance as yf
import pandas as pd

# Konfiguration
st.set_page_config(page_title="Aktien-Radar Pro", page_icon="💎", layout="wide")
st.title("💎 Aktien-Radar Pro")
st.markdown("Technische Analyse (RSI) & Fundamentaldaten (Umsatz & Gewinn)")

# Seitenleiste
st.sidebar.header("Filter-Einstellungen")
ticker_input = st.sidebar.text_area("Aktien-Liste (Kürzel mit Komma)", "NVDA,TSLA,AMD,AAPL,ANGI,MSFT")
rsi_limit = st.sidebar.slider("Max. RSI (14 Tage)", 10, 100, 60)
min_growth = st.sidebar.slider("Min. Umsatzwachstum (%)", -50, 100, 5)

if st.sidebar.button("🚀 Scanner starten"):
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    results = []
    status_text = st.empty()
    
    for ticker in tickers:
        status_text.text(f"Analysiere {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            # 1. Profi-RSI (Wilder's Smoothing) mit 200 Tagen Historie
            df = stock.history(period="200d")
            if len(df) > 14:
                delta = df['Close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                
                # alpha=1/14 entspricht der offiziellen RSI-Glättung
                avg_gain = gain.ewm(alpha=1/14, min_periods=14).mean()
                avg_loss = loss.ewm(alpha=1/14, min_periods=14).mean()
                
                rs = avg_gain / avg_loss
                rsi_val = 100 - (100 / (1 + rs)).iloc[-1]
                
                # 2. Fundamentaldaten abrufen
                info = stock.info
                rev_growth = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0
                fwd_pe = info.get('forwardPE', 0) # Erwartetes KGV (Gewinnausblick)
                
                # Filter anwenden
                if rsi_val <= rsi_limit and rev_growth >= min_growth:
                    results.append({
                        "Ticker": ticker,
                        "Kurs ($)": round(df['Close'].iloc[-1], 2),
                        "RSI (14)": round(float(rsi_val), 2),
                        "Umsatzwachstum (%)": f"{round(rev_growth, 2)}%",
                        "KGV (fwd)": round(fwd_pe, 2) if fwd_pe > 0 else "N/A"
                    })
        except:
            continue
            
    status_text.empty()
    if results:
        st.success(f"Analyse abgeschlossen: {len(results)} Treffer")
        st.table(pd.DataFrame(results))
    else:
        st.warning("Keine Aktien mit diesen Kriterien gefunden.")
