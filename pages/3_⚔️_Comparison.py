import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Usporedba Dionica", layout="wide")

st.title("⚔️ Usporedba Konkurencije")
st.markdown("Usporedi ključne metrike različitih kompanija jedne pored drugih.")

# --- INPUT ---
tickers_input = st.text_input("Upiši simbole za usporedbu (odvojene zarezom):", "CRM, MSFT, ORCL, SAP, ADBE")

if st.button("Usporedi"):
    tickers = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    
    data = []
    
    progress = st.progress(0)
    
    for i, t in enumerate(tickers):
        try:
            stock = yf.Ticker(t)
            info = stock.info
            
            # Dohvat metrika
            row = {
                "Simbol": t,
                "Cijena": info.get('currentPrice', 0),
                "Market Cap": info.get('marketCap', 0),
                "P/E (TTM)": info.get('trailingPE', 0),
                "Forward P/E": info.get('forwardPE', 0),
                "PEG Ratio": info.get('pegRatio', 0),
                "P/S (Sales)": info.get('priceToSalesTrailing12Months', 0),
                "P/B (Book)": info.get('priceToBook', 0),
                "ROIC %": "N/A", # Teško dobiti direktno, koristimo ROE kao zamjenu za brzi pregled
                "ROE %": info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
                "Profit Margin %": info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0,
                "Debt/Equity": info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0,
                "Div Yield %": info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
            }
            data.append(row)
        except:
            pass
        progress.progress((i + 1) / len(tickers))
    
    progress.empty()
    
    if data:
        df = pd.DataFrame(data)
        
        # Postavi Simbol kao index (prvi stupac)
        df.set_index("Simbol", inplace=True)
        
        # Transponiraj tablicu (da su dionice gore, a metrike lijevo - preglednije je)
        df_t = df.transpose()
        
        st.success("Usporedba završena!")
        st.dataframe(df_t, use_container_width=True)
        
        # Highlight pobjednika (Najjeftiniji po PE)
        try:
            best_pe = df.loc[df['P/E (TTM)'] > 0, 'P/E (TTM)'].idxmin()
            st.info(f"💡 Najniži P/E omjer ima: **{best_pe}**")
        except: pass
        
    else:
        st.error("Nema podataka.")
