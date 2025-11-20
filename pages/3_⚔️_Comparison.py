import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Usporedba Dionica", layout="wide")

st.title("⚔️ Usporedba Konkurencije")
st.markdown("Tablica s označenim financijskim zdravljem (Boje prema Rule #1 kriterijima).")

# --- INPUT ---
tickers_input = st.text_input("Upiši simbole za usporedbu (odvojene zarezom):", "CRM, MSFT, ORCL, ADBE, SAP, NOW")

if st.button("🚀 Usporedi", type="primary"):
    tickers = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    
    if not tickers:
        st.warning("Upiši barem jedan simbol.")
    else:
        data = []
        progress_bar = st.progress(0)
        
        for i, t in enumerate(tickers):
            try:
                stock = yf.Ticker(t)
                info = stock.info
                
                # Priprema podataka (Čuvamo ih kao BROJEVE radi bojanja)
                
                # Debt to Equity (Yahoo daje u postotku, npr. 150, dijelimo sa 100)
                de_ratio = info.get('debtToEquity')
                if de_ratio is not None: de_ratio = de_ratio / 100
                
                # Dividenda
                div_yield = info.get('dividendYield')
                if div_yield is None: div_yield = info.get('trailingAnnualDividendYield')
                if div_yield is not None: div_yield = div_yield * 100 # U postotak

                row = {
                    "Ticker": t,
                    "Market Cap": info.get('marketCap'),
                    "P/E": info.get('trailingPE'),
                    "P/B": info.get('priceToBook'),
                    "P/S": info.get('priceToSalesTrailing12Months'),
                    "PEG": info.get('pegRatio'),
                    
                    # Stupci za bojanje (Zdravlje)
                    "Debt/Eq": de_ratio,
                    "Quick": info.get('quickRatio'),
                    "Current": info.get('currentRatio'),
                    "ROE": info.get('returnOnEquity') * 100 if info.get('returnOnEquity') else None,
                    "ROA": info.get('returnOnAssets') * 100 if info.get('returnOnAssets') else None,
                    
                    # Margine
                    "Gross M": info.get('grossMargins') * 100 if info.get('grossMargins') else None,
                    "Oper M": info.get('operatingMargins') * 100 if info.get('operatingMargins') else None,
                    "Profit M": info.get('profitMargins') * 100 if info.get('profitMargins') else None,
                    
                    # Ostalo
                    "Div Yield": div_yield,
                    "Payout": info.get('payoutRatio') * 100 if info.get('payoutRatio') else None,
                    "An. Rec": info.get('recommendationKey', '-').replace('_', ' ').title()
                }
                data.append(row)
            except:
                pass 
            
            progress_bar.progress((i + 1) / len(tickers))
        
        progress_bar.empty()
        
        if data:
            df = pd.DataFrame(data)
            
            # --- DEFINIRANJE BOJA (STYLING) ---
            def color_liquidity(val): # Quick, Current
                if pd.isna(val): return None
                if val > 1.2: return 'color: #4CAF50; font-weight: bold' # Green
                elif val >= 0.9: return 'color: #FFC107; font-weight: bold' # Yellow
                return 'color: #FF5252; font-weight: bold' # Red

            def color_debt(val): # Debt/Eq
                if pd.isna(val): return None
                if val < 1: return 'color: #4CAF50; font-weight: bold'
                elif val <= 2: return 'color: #FFC107; font-weight: bold'
                return 'color: #FF5252; font-weight: bold'

            def color_returns(val): # ROE, ROA
                if pd.isna(val): return None
                if val >= 12: return 'color: #00C853; font-weight: bold' # Dark Green
                elif val >= 9: return 'color: #69F0AE; font-weight: bold' # Light Green
                elif val >= 6: return 'color: #FFC107; font-weight: bold' # Yellow
                return 'color: #FF5252; font-weight: bold' # Red
            
            # --- PRIMJENA STILOVA ---
            # Koristimo Pandas Styler
            styler = df.style.format({
                "Market Cap": lambda x: f"{x/1e9:.2f}B" if pd.notnull(x) else "-",
                "P/E": "{:.2f}", "P/B": "{:.2f}", "P/S": "{:.2f}", "PEG": "{:.2f}",
                "Debt/Eq": "{:.2f}", "Quick": "{:.2f}", "Current": "{:.2f}",
                "ROE": "{:.2f}%", "ROA": "{:.2f}%", 
                "Gross M": "{:.2f}%", "Oper M": "{:.2f}%", "Profit M": "{:.2f}%",
                "Div Yield": "{:.2f}%", "Payout": "{:.2f}%"
            }, na_rep="-")
            
            # Bojanje specifičnih stupaca (koristimo map umjesto applymap za novije verzije, ali applymap je sigurniji za starije)
            # Streamlit koristi novije verzije, 'map' je standard.
            try:
                styler.map(color_liquidity, subset=["Quick", "Current"])
                styler.map(color_debt, subset=["Debt/Eq"])
                styler.map(color_returns, subset=["ROE", "ROA"])
            except:
                # Fallback za starije verzije pandasa
                styler.applymap(color_liquidity, subset=["Quick", "Current"])
                styler.applymap(color_debt, subset=["Debt/Eq"])
                styler.applymap(color_returns, subset=["ROE", "ROA"])

            # Prikaz tablice
            st.dataframe(styler, use_container_width=True, hide_index=True)
            
            # Legenda
            st.caption("""
            **Legenda Boja:** 🟢 **Zeleno:** Odlično (Liquid > 1.2, Debt < 1, ROE > 9%) 
            🟡 **Žuto:** Srednje 
            🔴 **Crveno:** Oprez
            """)
            
        else:
            st.error("Nema podataka za odabrane simbole.")
