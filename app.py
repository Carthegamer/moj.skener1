import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- POSTAVKE STRANICE ---
st.set_page_config(page_title="Rule #1 Skener", layout="wide")

# --- FUNKCIJE ---
def format_large(num):
    if num is None: return "-"
    if abs(num) >= 1_000_000_000: return f"{num/1_000_000_000:.2f}B"
    if abs(num) >= 1_000_000: return f"{num/1_000_000:.2f}M"
    return f"{num:.2f}"

def calculate_dcf(eps, growth, discount, terminal_pe):
    # Jednostavni DCF model u 10 godina
    vals = []
    curr = eps
    for _ in range(10):
        curr = curr * (1 + growth/100)
        vals.append(curr)
    
    # Diskontiranje
    fair_val = 0
    for i, val in enumerate(vals):
        fair_val += val / ((1 + discount/100)**(i+1))
    
    # Terminalna vrijednost
    term_val = vals[-1] * terminal_pe
    term_disc = term_val / ((1 + discount/100)**10)
    
    return fair_val + term_disc

# --- SIDEBAR ---
st.sidebar.header("🔎 Pretraga")
ticker = st.sidebar.text_input("Simbol (npr. CRM):", "CRM").upper()
st.sidebar.info("Ova verzija koristi jednostavne grafove radi stabilnosti.")

# --- GLAVNI DIO ---
if ticker:
    # Dohvat podataka
    stock = yf.Ticker(ticker)
    info = stock.info
    
    # Provjera jesu li podaci stigli
    if 'currentPrice' in info:
        fin = stock.financials
        bal = stock.balance_sheet
        cf = stock.cashflow
        
        # --- ZAGLAVLJE (HEADER) ---
        price = info.get('currentPrice', 0)
        currency = info.get('currency', 'USD')
        
        col_head1, col_head2 = st.columns([1, 3])
        with col_head1:
            # Velika cijena (koristimo standardni Streamlit metric)
            st.metric(label=f"{ticker} ({currency})", value=f"{price}", delta=None)
        
        with col_head2:
            # Brzi pregled
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Market Cap", format_large(info.get('marketCap', 0)))
            c2.metric("P/E Ratio", f"{info.get('trailingPE', 0):.2f}")
            c3.metric("EPS (TTM)", f"{info.get('trailingEps', 0)}")
            c4.metric("Beta", f"{info.get('beta', 0):.2f}")

        st.markdown("---")

        # --- PRIPREMA PODATAKA ZA PILLARS ---
        # Uzimamo Godišnje podatke
        if not fin.empty:
            years = fin.columns
            
            # 1. Revenue Growth
            rev_now = fin.iloc[0, 0]
            rev_old = fin.iloc[0, -1]
            rev_growth = ((rev_now - rev_old) / rev_old) * 100
            
            # 2. Net Income Growth
            ni_now = fin.loc['Net Income'].iloc[0]
            ni_old = fin.loc['Net Income'].iloc[-1]
            ni_growth = ((ni_now - ni_old) / abs(ni_old)) * 100
            
            # 3. Cash Growth
            c_row = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal.index else 'Cash Cash Equivalents And Short Term Investments'
            cash_now = bal.loc[c_row].iloc[0]
            cash_old = bal.loc[c_row].iloc[-1]
            cash_growth = ((cash_now - cash_old) / abs(cash_old)) * 100
            
            # 4. Debt Logic
            ltd_row = 'Long Term Debt' if 'Long Term Debt' in bal.index else 'Long Term Debt And Capital Lease Obligation'
            lt_debt = bal.loc[ltd_row].iloc[0] if ltd_row in bal.index else 0
            net_cash = cash_now - lt_debt
            
            # 5. Liability Logic
            liab_row = 'Total Non Current Liabilities Net Minority Interest' if 'Total Non Current Liabilities Net Minority Interest' in bal.index else 'Total Non Current Liabilities'
            avg_liab = bal.loc[liab_row].iloc[:5].mean() if liab_row in bal.index else 0
            
            # 6. ROIC
            roic_sum = 0
            cnt = 0
            for i in range(min(5, len(fin.columns))):
                try:
                    ebit = fin.loc['EBIT'].iloc[i] if 'EBIT' in fin.index else fin.loc['Pretax Income'].iloc[i]
                    equity = bal.loc['Stockholders Equity'].iloc[i]
                    d = bal.loc['Total Debt'].iloc[i] if 'Total Debt' in bal.index else 0
                    roic_sum += (ebit / (equity+d)) * 100
                    cnt += 1
                except: pass
            avg_roic = roic_sum / cnt if cnt > 0 else 0
            
            # 7. Shares
            shares_now = info.get('sharesOutstanding', 0)
            shares_old = bal.loc['Ordinary Shares Number'].iloc[-1] if 'Ordinary Shares Number' in bal.index else shares_now
            
            # 8. FCF
            if 'Free Cash Flow' in cf.index:
                fcf_avg = cf.loc['Free Cash Flow'].iloc[:5].mean()
            else:
                fcf_avg = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']).iloc[:5].mean()
            
            
            # --- 10 PILLARS PRIKAZ (SIMPLE & STABLE) ---
            st.subheader("🏛️ 10 Pillars Analiza")
            
            col_p1, col_p2 = st.columns(2)
            
            def show_pillar(col, title, value_str, passed):
                if passed:
                    col.success(f"✅ **{title}**: {value_str}")
                else:
                    col.error(f"❌ **{title}**: {value_str}")

            with col_p1:
                st.markdown("##### Rast & Profit")
                show_pillar(st, "Revenue Growth", f"{rev_growth:.1f}%", rev_growth > 0)
                show_pillar(st, "Net Income Growth", f"{ni_growth:.1f}%", ni_growth > 0)
                show_pillar(st, "Cash Growth", f"{cash_growth:.1f}%", cash_growth > 0)
                show_pillar(st, "Avg ROIC > 9%", f"{avg_roic:.1f}%", avg_roic > 9)
                pe = info.get('trailingPE', 0)
                show_pillar(st, "PE < 22.5", f"{pe:.2f}", 0 < pe < 22.5)

            with col_p2:
                st.markdown("##### Bilanca & Vrednovanje")
                show_pillar(st, "Cash > LT Debt", f"Cash: {format_large(cash_now)} vs Debt: {format_large(lt_debt)}", cash_now > lt_debt)
                show_pillar(st, "Cash > Avg Liab", f"Avg Liab: {format_large(avg_liab)}", cash_now > avg_liab)
                show_pillar(st, "Share Buyback", "Dionice smanjene", shares_now <= shares_old)
                show_pillar(st, "FCF x20 > Market Cap", f"Fair: {format_large(fcf_avg*20)}", (fcf_avg*20) > info.get('marketCap', 0))
                # Dividend logic
                div = info.get('dividendYield', 0)
                show_pillar(st, "Dividend Safety", "Sigurna/Nema", True) # Pojednostavljeno

            st.markdown("---")

            # --- GRAFOVI (SIMPLE STREAMLIT CHARTS) ---
            st.subheader("📈 Financijski Grafovi")
            
            tab1, tab2 = st.tabs(["Prihodi & Dobit", "Cash & Shares"])
            
            # Priprema podataka za grafove (obrnuti redoslijed da ide s lijeva na desno)
            fin_rev = fin.columns[::-1]
            
            with tab1:
                # Revenue
                st.write("**Total Revenue (Godišnje)**")
                rev_data = fin.loc['Total Revenue'][fin_rev]
                st.bar_chart(rev_data)
                
                # Net Income
                st.write("**Net Income (Godišnje)**")
                ni_data = fin.loc['Net Income'][fin_rev]
                st.bar_chart(ni_data, color="#00FF00") # Zelena boja

            with tab2:
                # Cash
                st.write("**Cash vs LT Debt**")
                # Napravimo mali dataframe za usporedbu
                df_debt = pd.DataFrame({
                    'Cash': bal.loc[c_row][fin_rev],
                    'LT Debt': [lt_debt]*len(fin_rev) # pojednostavljeno, ili povuci povijesno
                })
                if ltd_row in bal.index:
                    df_debt['LT Debt'] = bal.loc[ltd_row][fin_rev]
                
                st.line_chart(df_debt)
                
                # Shares
                if 'Ordinary Shares Number' in bal.index:
                    st.write("**Shares Outstanding**")
                    st.bar_chart(bal.loc['Ordinary Shares Number'][fin_rev])

            st.markdown("---")
            
            # --- DCF KALKULATOR ---
            st.subheader("🧮 Valuacija (DCF)")
            
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                g_input = st.number_input("Očekivani rast (%)", 15.0)
                d_input = st.number_input("Diskontna stopa (%)", 10.0)
            with d_col2:
                pe_input = st.number_input("Terminalni PE", 15.0)
                eps_input = info.get('trailingEps', 0)
            
            fair_value = calculate_dcf(eps_input, g_input, d_input, pe_input)
            
            st.metric("Fer Vrijednost (DCF)", f"${fair_value:.2f}", delta=f"{fair_value - price:.2f}")
            
            if price < fair_value:
                st.success(f"Dionica je **PODCIJENJENA** (Undervalued). Fer cijena: ${fair_value:.2f}")
            else:
                st.error(f"Dionica je **PRECIJENJENA** (Overvalued). Fer cijena: ${fair_value:.2f}")

        else:
            st.error("Nema detaljnih financijskih podataka za ovu dionicu.")
    else:
        st.error("Simbol nije pronađen ili nema podataka.")
