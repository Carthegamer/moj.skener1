import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Batch Screener", layout="wide")

st.title("🔍 Batch Screener (10 Pillars)")
st.markdown("Upiši listu dionica za brzu provjeru svih 10 kriterija.")

# --- FUNKCIJA ZA SKRAĆIVANJE IMENA ---
def clean_name(name):
    if not name: return ""
    # Mičemo nepotrebne dodatke da stane u tablicu
    replacements = [', Inc.', ' Inc.', ' Corporation', ', Corp.', ' Corp.', ' Limited', ' Ltd.', ' plc', ' PLC']
    for r in replacements:
        name = name.replace(r, '')
    return name

# --- INPUT ---
col_in1, col_in2 = st.columns([3, 1])
with col_in1:
    tickers_input = st.text_area("Upiši simbole (odvojene zarezom):", "CRM, AAPL, MSFT, GOOG, AMZN, TSLA, NVDA, META, AMD, NFLX, KO, PEP, MCD", height=70)

with col_in2:
    st.markdown("<br>", unsafe_allow_html=True)
    scan_btn = st.button("🚀 Pokreni Skener", type="primary", use_container_width=True)

# --- LOGIKA SKENERA ---
if scan_btn:
    tickers_list = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    
    if not tickers_list:
        st.warning("Upiši barem jedan simbol.")
    else:
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, ticker in enumerate(tickers_list):
            status_text.text(f"Analiziram: {ticker} ({i+1}/{len(tickers_list)})...")
            
            try:
                stock = yf.Ticker(ticker)
                # Trik: dohvaćamo info da provjerimo jel dionica postoji
                info = stock.info
                
                if info and 'currentPrice' in info:
                    fin = stock.financials
                    bal = stock.balance_sheet
                    cf = stock.cashflow
                    
                    if not fin.empty:
                        # --- 10 PILLARS IZRAČUN ---
                        p = {} 
                        years_cnt = min(5, len(fin.columns))
                        
                        # Varijable
                        total_cash = info.get('totalCash', 0)
                        mkt_cap = info.get('marketCap', 0)
                        pe = info.get('trailingPE', 0)
                        if pe is None: pe = 0
                        
                        ltd_row = 'Long Term Debt' if 'Long Term Debt' in bal.index else 'Long Term Debt And Capital Lease Obligation'
                        lt_debt = bal.loc[ltd_row].iloc[0] if ltd_row in bal.index else 0
                        
                        c_row = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal.index else 'Cash Cash Equivalents And Short Term Investments'
                        
                        # 1. Rev Growth
                        try: p['Rev Growth'] = ((fin.iloc[0,0]-fin.iloc[0,-1]) > 0)
                        except: p['Rev Growth'] = False
                        
                        # 2. Net Inc Growth
                        try: p['Net Inc Growth'] = ((fin.loc['Net Income'].iloc[0]-fin.loc['Net Income'].iloc[-1]) > 0)
                        except: p['Net Inc Growth'] = False
                        
                        # 3. Cash Growth
                        try: p['Cash Growth'] = ((bal.loc[c_row].iloc[0]-bal.loc[c_row].iloc[-1]) > 0)
                        except: p['Cash Growth'] = False
                        
                        # 4. Repay Debt
                        p['Cash > Debt'] = (total_cash >= lt_debt)
                        
                        # 5. Repay Liab
                        try:
                            l_row = 'Total Non Current Liabilities Net Minority Interest' if 'Total Non Current Liabilities Net Minority Interest' in bal.index else 'Total Non Current Liabilities'
                            avg_liab = bal.loc[l_row].iloc[:5].mean() if l_row in bal.index else 0
                            p['Cash > Liab'] = (total_cash >= avg_liab)
                        except: p['Cash > Liab'] = False
                        
                        # 6. PE
                        p['PE < 22.5'] = (0 < pe < 22.5)
                        
                        # 7. ROIC
                        try:
                            roic_sum = 0
                            cnt = min(5, len(fin.columns))
                            for y in range(cnt):
                                e = fin.loc['EBIT'].iloc[y] if 'EBIT' in fin.index else fin.loc['Pretax Income'].iloc[y]
                                ic = bal.loc['Stockholders Equity'].iloc[y] + lt_debt
                                roic_sum += (e/ic)
                            p['ROIC > 9%'] = ((roic_sum/cnt)*100 > 9)
                        except: p['ROIC > 9%'] = False
                        
                        # 8. Buyback
                        try:
                            sh_now = info.get('sharesOutstanding', 0)
                            sh_old = bal.loc['Ordinary Shares Number'].iloc[-1] if 'Ordinary Shares Number' in bal.index else sh_now
                            p['Buyback'] = (sh_now <= sh_old)
                        except: p['Buyback'] = False
                        
                        # 9. Valuation
                        try:
                            if 'Free Cash Flow' in cf.index: fcf = cf.loc['Free Cash Flow'].iloc[:5].mean()
                            else: fcf = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']).iloc[:5].mean()
                            p['Undervalued'] = ((fcf*20) > mkt_cap)
                        except: p['Undervalued'] = False
                        
                        # 10. Div Safety
                        try:
                            div_paid = abs(cf.loc['Cash Dividends Paid'].iloc[0]) if 'Cash Dividends Paid' in cf.index else 0
                            p['Div Safety'] = (True if div_paid == 0 else total_cash > div_paid)
                        except: p['Div Safety'] = True

                        # ZBROJ BODOVA
                        score = sum([1 for v in p.values() if v])
                        
                        # --- PRIPREMA REDA ZA TABLICU ---
                        company_name = clean_name(info.get('shortName', info.get('longName', '')))
                        
                        row_data = {
                            "Ticker": ticker,
                            "Name": company_name,  # NOVI STUPAC
                            "Score (Max 10)": score,
                        }
                        for k, v in p.items():
                            row_data[k] = "✅" if v else "❌"
                        
                        results.append(row_data)
            
            except Exception as e:
                pass
            
            progress_bar.progress((i + 1) / len(tickers_list))
        
        status_text.empty()
        progress_bar.empty()
        
        # --- PRIKAZ REZULTATA ---
        if results:
            df = pd.DataFrame(results)
            df = df.sort_values(by="Score (Max 10)", ascending=False)
            
            st.success(f"Skeniranje završeno! Pronađeno {len(df)} dionica.")
            
            # TABLICA
            st.dataframe(
                df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Score (Max 10)": st.column_config.ProgressColumn(
                        "Score",
                        format="%d",
                        min_value=0,
                        max_value=10,
                    ),
                    "Name": st.column_config.TextColumn("Kompanija", width="medium"),
                }
            )
        else:
            st.error("Nije pronađen niti jedan valjani podatak.")

# --- LEGENDA NA DNU ---
st.markdown("---")
st.subheader("📖 Legenda 10 Pillara")

c1, c2 = st.columns(2)
with c1:
    st.info("**1. Rev Growth:** Rast prihoda u zadnjih 5 godina.")
    st.info("**2. Net Inc Growth:** Rast neto dobiti u zadnjih 5 godina.")
    st.info("**3. Cash Growth:** Količina novca na računu raste.")
    st.info("**4. Cash > Debt:** Kompanija ima više novca nego dugoročnog duga.")
    st.info("**5. Cash > Liab:** Novac pokriva prosječne dugoročne obveze.")

with c2:
    st.info("**6. PE < 22.5:** P/E omjer je manji od 22.5 (Nije preskupa).")
    st.info("**7. ROIC > 9%:** Povrat na investirani kapital veći od 9% (Avg 5y).")
    st.info("**8. Buyback:** Smanjili su broj dionica (kupuju vlastite dionice).")
    st.info("**9. Undervalued:** Market Cap je manji od (Avg FCF * 20).")
    st.info("**10. Div Safety:** Dividenda je sigurna (isplaćuju manje nego što imaju keša).")
