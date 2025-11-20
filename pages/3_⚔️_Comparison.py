import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Usporedba Dionica", layout="wide")

st.title("⚔️ Usporedba Konkurencije")
st.markdown("Tablica usporedbe prema ključnim financijskim pokazateljima.")

# --- POMOĆNE FUNKCIJE ZA FORMATIRANJE ---
def fmt_num(val):
    """Zaokružuje na 2 decimale, vraća '-' ako nema podataka"""
    if val is None: return "-"
    return f"{val:.2f}"

def fmt_pct(val):
    """Pretvara decimalni broj (0.05) u postotak (5.00%), vraća '-' ako nema podataka"""
    if val is None: return "-"
    return f"{val * 100:.2f}%"

def fmt_large(num):
    """Formatira velike brojeve (B/T)"""
    if num is None: return "-"
    if abs(num) >= 1_000_000_000_000: return f"{num / 1_000_000_000_000:.2f}T"
    if abs(num) >= 1_000_000_000: return f"{num / 1_000_000_000:.2f}B"
    elif abs(num) >= 1_000_000: return f"{num / 1_000_000:.2f}M"
    else: return f"{num:.2f}"

# --- INPUT ---
tickers_input = st.text_input("Upiši simbole za usporedbu (odvojene zarezom):", "CRM, MSFT, ORCL, ADBE, SAP, NOW, SNOW")

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
                
                # Provjera dividende (ako je None, probaj drugu varijablu)
                div_yield = info.get('dividendYield')
                if div_yield is None:
                     # Ponekad je u trailingAnnualDividendYield
                     div_yield = info.get('trailingAnnualDividendYield')

                # Debt to Equity u YF je često u postotcima (npr. 80 za 0.8). 
                # Dijelimo sa 100 da dobijemo ratio kao na slici.
                de_ratio = info.get('debtToEquity')
                if de_ratio is not None:
                    de_ratio = de_ratio / 100

                # Priprema reda (Točno stupci sa slike)
                row = {
                    "Ticker": t,
                    "Market Cap": fmt_large(info.get('marketCap')),
                    "P/E": fmt_num(info.get('trailingPE')),
                    "P/B": fmt_num(info.get('priceToBook')),
                    "P/S": fmt_num(info.get('priceToSalesTrailing12Months')),
                    "PEG": fmt_num(info.get('pegRatio')),
                    "Debt/Eq": fmt_num(de_ratio),
                    "Quick": fmt_num(info.get('quickRatio')),
                    "Current": fmt_num(info.get('currentRatio')),
                    "ROE": fmt_pct(info.get('returnOnEquity')),
                    "ROA": fmt_pct(info.get('returnOnAssets')),
                    "Gross M": fmt_pct(info.get('grossMargins')),
                    "Oper M": fmt_pct(info.get('operatingMargins')),
                    "Profit M": fmt_pct(info.get('profitMargins')),
                    "Div Yield": fmt_pct(div_yield),
                    "Payout": fmt_pct(info.get('payoutRatio')),
                    "An. Rec": info.get('recommendationKey', '-').replace('_', ' ').title()
                }
                data.append(row)
            except:
                pass # Preskoči ako greška
            
            progress_bar.progress((i + 1) / len(tickers))
        
        progress_bar.empty()
        
        if data:
            # Kreiranje tablice
            df = pd.DataFrame(data)
            
            # Prikaz tablice
            st.success(f"Uspoređeno {len(df)} kompanija.")
            st.dataframe(
                df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Ticker": st.column_config.TextColumn("Ticker", width="small", help="Simbol dionice"),
                    "Market Cap": st.column_config.TextColumn("Mkt Cap", width="medium"),
                    "An. Rec": st.column_config.TextColumn("Analyst Rec", width="medium"),
                }
            )
            
            # Kratka legenda ispod
            st.caption("""
            **Legenda:** **P/E**: Price to Earnings, **P/B**: Price to Book, **P/S**: Price to Sales, **PEG**: PE to Growth.
            **Debt/Eq**: Debt to Equity Ratio. **ROE**: Return on Equity. **ROA**: Return on Assets.
            **Oper M**: Operating Margin. **An. Rec**: Preporuka analitičara (Buy, Hold, Sell).
            """)
            
        else:
            st.error("Nema podataka za odabrane simbole.")
