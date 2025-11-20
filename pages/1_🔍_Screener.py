import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Batch Screener", layout="wide")

st.title("🔍 Batch Screener (Popravljeni)")
st.markdown("Napredna provjera 10 Pillara s boljim prepoznavanjem podataka.")

# --- INPUT ---
col_in1, col_in2 = st.columns([3, 1])
with col_in1:
    tickers_input = st.text_area(
        "Upiši simbole (odvojene zarezom):", 
        "CRM, AMZN, AAPL, MSFT, GOOG, TSLA, NVDA, META, AMD, NFLX, KO", 
        height=70
    )

with col_in2:
    st.markdown("<br>", unsafe_allow_html=True)
    scan_btn = st.button("🚀 Pokreni Skener", type="primary", use_container_width=True)

# --- PAMETNA FUNKCIJA ZA TRAŽENJE REDAKA ---
def get_row_val(df, keys, col_idx):
    """
    Traži vrijednost u DataFrameu provjeravajući više mogućih naziva (ključeva).
    Vraća prvi koji pronađe.
    """
    if df.empty: return None
    
    # 1. Pokušaj točno podudaranje
    for k in keys:
        if k in df.index:
            try: return df.loc[k].iloc[col_idx]
            except: pass
            
    # 2. Ako ne nađe, pokušaj "sadrži" (case insensitive) za nuždu
    # Ovo pomaže ako Yahoo promijeni ime u "Cash & Equivalents" umjesto "Cash And..."
    # index_str = df.index.astype(str)
    # for k in keys:
    #     matches = df[index_str.str.contains(k, case=False, regex=False)]
    #     if not matches.empty:
    #         return matches.iloc[0].iloc[col_idx]
            
    return None

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
                info = stock.info
                
                if not info or 'currentPrice' not in info:
                    raise Exception("No Data")

                # Dohvati tablice
                fin = stock.financials
                bal = stock.balance_sheet
                cf = stock.cashflow
                
                if not fin.empty:
                    p = {} 
                    
                    # --- PODACI (Current & Old) ---
                    old_idx = -1 # Zadnji stupac (najstarija godina)
                    
                    # INFO TTM PODACI
                    rev_ttm = info.get('totalRevenue')
                    net_inc_ttm = info.get('netIncomeToCommon')
                    cash_ttm = info.get('totalCash')
                    debt_ttm = info.get('totalDebt') # Total Debt za strogi Rule #1
                    mkt_cap = info.get('marketCap', 0)
                    pe = info.get('trailingPE', 0)
                    
                    # 1. REVENUE GROWTH
                    rev_keys = ['Total Revenue', 'Revenue', 'Operating Revenue']
                    rev_old = get_row_val(fin, rev_keys, old_idx)
                    
                    if rev_ttm and rev_old: p['Rev Growth'] = (rev_ttm > rev_old)
                    else: p['Rev Growth'] = False

                    # 2. NET INCOME GROWTH
                    ni_keys = ['Net Income', 'Net Income Common Stockholders', 'Net Income From Continuing And Discontinued Operation']
                    ni_old = get_row_val(fin, ni_keys, old_idx)
                    
                    if net_inc_ttm is not None and ni_old is not None:
                        # Provjera smjera (ako je stari bio minus, a novi plus, to je rast)
                        if ni_old < 0 and net_inc_ttm > ni_old: p['Net Inc Growth'] = True
                        else: p['Net Inc Growth'] = (net_inc_ttm > ni_old)
                    else:
                        p['Net Inc Growth'] = False

                    # 3. CASH GROWTH
                    # Proširena lista ključeva za Cash
                    cash_keys = [
                        'Cash And Cash Equivalents', 
                        'Cash Cash Equivalents And Short Term Investments',
                        'Cash And Short Term Investments',
                        'Cash'
                    ]
                    cash_old = get_row_val(bal, cash_keys, old_idx)
                    
                    # Fallback: Ako nema u balanci, probaj izračunati iz Info (ako ima cashPerShare * shares)
                    # Ali bolje je vjerovati balanci. Ako cash_old fali, probamo stariji stupac.
                    
                    if cash_ttm is not None and cash_old is not None:
                        p['Cash Growth'] = (cash_ttm >= cash_old)
                    else:
                        # Ako nemamo povijesni podatak, pretpostavi False da ne bude lažno zeleno
                        p['Cash Growth'] = False

                    # 4. REPAY DEBT (Cash > LT Debt)
                    # Za ovaj Pillar koristimo LT Debt iz balance sheeta
                    ltd_keys = ['Long Term Debt', 'Long Term Debt And Capital Lease Obligation']
                    lt_debt = get_row_val(bal, ltd_keys, 0) # Trenutno stanje u bilanci
                    if lt_debt is None: lt_debt = 0
                    
                    if cash_ttm is not None:
                        p['Cash > Debt'] = (cash_ttm >= lt_debt)
                    else:
                        p['Cash > Debt'] = False
                    
                    # 5. REPAY LIABILITIES
                    liab_keys = ['Total Non Current Liabilities Net Minority Interest', 'Total Non Current Liabilities']
                    liab_old = get_row_val(bal, liab_keys, 0)
                    if cash_ttm is not None and liab_old is not None:
                        p['Cash > Liab'] = (cash_ttm >= liab_old)
                    else:
                        p['Cash > Liab'] = False
                    
                    # 6. PE RATIO
                    if pe is None: pe = 0
                    p['PE < 22.5'] = (0 < pe < 22.5)
                    
                    # 7. ROIC > 9%
                    try:
                        roic_sum = 0
                        cnt = 0
                        years = min(5, len(fin.columns))
                        for y in range(years):
                            ebit = get_row_val(fin, ['EBIT', 'Pretax Income', 'Operating Income'], y)
                            equity = get_row_val(bal, ['Stockholders Equity', 'Total Equity Gross Minority Interest'], y)
                            d_y = get_row_val(bal, ['Total Debt', 'Long Term Debt'], y)
                            if d_y is None: d_y = 0
                            
                            if ebit and equity:
                                ic = equity + d_y
                                if ic != 0:
                                    roic_sum += (ebit / ic)
                                    cnt += 1
                        
                        if cnt > 0:
                            avg_roic = (roic_sum / cnt) * 100
                            p['ROIC > 9%'] = (avg_roic > 9)
                        else:
                            # Fallback na ROE ako nema podataka za ROIC
                            roe = info.get('returnOnEquity', 0)
                            p['ROIC > 9%'] = (roe > 0.09)
                    except:
                        p['ROIC > 9%'] = False
                    
                    # 8. SHARE BUYBACK
                    shares_now = info.get('sharesOutstanding')
                    
                    # Prvo probaj Bilancu
                    shares_old = get_row_val(bal, ['Ordinary Shares Number', 'Share Issued', 'Common Stock'], old_idx)
                    
                    # Ako nema u Bilanci, probaj Income Statement (Basic Average Shares) - ovo je često točnije!
                    if shares_old is None:
                        shares_old = get_row_val(fin, ['Basic Average Shares', 'Diluted Average Shares'], old_idx)
                    
                    if shares_now and shares_old:
                        # Dopustimo malu marginu greške (npr. 1% rasta nije strašno), ali Rule #1 je strog.
                        # Strogo pravilo: shares_now <= shares_old
                        p['Buyback'] = (shares_now <= shares_old)
                    else:
                        p['Buyback'] = False
                    
                    # 9. VALUATION (FCF * 20 > Market Cap)
                    fcf_ttm = info.get('freeCashflow')
                    if fcf_ttm is None and not cf.empty:
                         op_cash = get_row_val(cf, ['Operating Cash Flow'], 0)
                         capex = get_row_val(cf, ['Capital Expenditure'], 0)
                         if op_cash and capex: fcf_ttm = op_cash + capex
                    
                    if fcf_ttm and mkt_cap:
                        p['Undervalued'] = ((fcf_ttm * 20) > mkt_cap)
                    else:
                        p['Undervalued'] = False
                    
                    # 10. DIVIDEND SAFETY
                    div_rate = info.get('dividendRate', 0)
                    if div_rate is None: div_rate = 0
                    
                    if div_rate == 0:
                        p['Div Safety'] = True # Nema dividende = Sigurno
                    else:
                        # Payout ratio iz info je najtočniji
                        payout = info.get('payoutRatio', 0)
                        if payout is not None:
                            p['Div Safety'] = (payout < 1.0) # Isplaćuju manje od zarade
                        else:
                            p['Div Safety'] = False

                    # --- KRAJ ---
                    score = sum([1 for v in p.values() if v])
                    comp_name = info.get('shortName', ticker)
                    
                    row_data = {
                        "Ticker": ticker,
                        "Name": comp_name,
                        "Score (Max 10)": score,
                    }
                    for k, v in p.items():
                        row_data[k] = "✅" if v else "❌"
                    
                    results.append(row_data)

            except Exception as e:
                # st.error(f"Error {ticker}: {e}") # Uncomment for debug
                pass
            
            progress_bar.progress((i + 1) / len(tickers_list))
        
        status_text.empty()
        progress_bar.empty()
        
        if results:
            df = pd.DataFrame(results)
            df = df.sort_values(by="Score (Max 10)", ascending=False)
            
            st.success(f"Analizirano {len(results)} dionica.")
            
            st.dataframe(
                df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Score (Max 10)": st.column_config.ProgressColumn(
                        "Score", format="%d", min_value=0, max_value=10
                    ),
                }
            )
            
            st.markdown("---")
            st.subheader("📖 Legenda (Rule #1)")
            c1, c2 = st.columns(2)
            with c1:
                st.info("**Rev/NetInc/Cash Growth:** TTM (danas) veći od podataka prije 4-5 god.")
                st.info("**Cash > Debt:** Keš veći od Long Term Debt.")
                st.info("**Buyback:** Broj dionica smanjen ili isti (u odnosu na prije 4-5 god).")
            with c2:
                st.info("**ROIC > 9%:** Avg 5y ROIC.")
                st.info("**Undervalued:** FCF*20 > Market Cap.")
                st.info("**Div Safety:** Payout Ratio < 100% (ili nema dividende).")
        else:
            st.error("Nije pronađen niti jedan valjani podatak.")
