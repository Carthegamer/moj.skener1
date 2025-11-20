import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Batch Screener", layout="wide")

st.title("🔍 Batch Screener (Popravljeni)")
st.markdown("Analiza 10 Pillara koristeći najnovije TTM podatke.")

# --- INPUT ---
col_in1, col_in2 = st.columns([3, 1])
with col_in1:
    tickers_input = st.text_area(
        "Upiši simbole (odvojene zarezom):", 
        "CRM, AMZN, AAPL, MSFT, GOOG, TSLA, NVDA, META, AMD, NFLX", 
        height=70
    )

with col_in2:
    st.markdown("<br>", unsafe_allow_html=True)
    scan_btn = st.button("🚀 Pokreni Skener", type="primary", use_container_width=True)

# --- POMOĆNA FUNKCIJA ZA SIGURNO DOHVAĆANJE REDAKA ---
def get_row_val(df, keys, col_idx):
    """Traži redak po imenu (ključu) i vraća vrijednost iz stupca col_idx."""
    for k in keys:
        if k in df.index:
            try:
                val = df.loc[k].iloc[col_idx]
                return val
            except:
                return None
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
                
                # Ako nema cijene, preskoči
                if not info or 'currentPrice' not in info:
                    raise Exception("No Data")

                # Dohvati tablice
                fin = stock.financials
                bal = stock.balance_sheet
                cf = stock.cashflow
                
                if not fin.empty and not bal.empty:
                    p = {} 
                    
                    # PODACI IZ INFO (TTM - Najsvježiji)
                    rev_ttm = info.get('totalRevenue')
                    net_inc_ttm = info.get('netIncomeToCommon')
                    cash_ttm = info.get('totalCash')
                    debt_ttm = info.get('totalDebt')
                    mkt_cap = info.get('marketCap', 0)
                    pe = info.get('trailingPE', 0)
                    if pe is None: pe = 0
                    
                    # POVIJESNI PODACI (Zadnja dostupna godina, skroz desno)
                    old_idx = -1 
                    
                    # 1. REVENUE GROWTH (TTM vs 4-5 godina prije)
                    rev_old = get_row_val(fin, ['Total Revenue', 'Revenue'], old_idx)
                    if rev_ttm and rev_old:
                        p['Rev Growth'] = (rev_ttm > rev_old)
                    else:
                        p['Rev Growth'] = False

                    # 2. NET INCOME GROWTH
                    ni_old = get_row_val(fin, ['Net Income', 'Net Income Common Stockholders'], old_idx)
                    if net_inc_ttm is not None and ni_old is not None:
                        # Provjera rasta (pazimo na negativne brojeve)
                        p['Net Inc Growth'] = (net_inc_ttm > ni_old)
                    else:
                        p['Net Inc Growth'] = False

                    # 3. CASH GROWTH
                    cash_old = get_row_val(bal, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'], old_idx)
                    if cash_ttm is not None and cash_old is not None:
                        p['Cash Growth'] = (cash_ttm > cash_old)
                    else:
                        p['Cash Growth'] = False

                    # 4. REPAY DEBT (Cash > Long Term Debt)
                    # Za strogi Rule #1 gledamo Total Debt, ali ti si tražio LT Debt
                    lt_debt = get_row_val(bal, ['Long Term Debt', 'Long Term Debt And Capital Lease Obligation'], 0)
                    # Ako nema LT debt u bilanci, uzmi 0
                    if lt_debt is None: lt_debt = 0
                    
                    if cash_ttm is not None:
                        p['Cash > Debt'] = (cash_ttm >= lt_debt)
                    else:
                        p['Cash > Debt'] = False
                    
                    # 5. REPAY LIABILITIES
                    liab_rows = ['Total Non Current Liabilities Net Minority Interest', 'Total Non Current Liabilities']
                    liab_old = get_row_val(bal, liab_rows, 0) # Trenutna bilanca
                    if cash_ttm is not None and liab_old is not None:
                        p['Cash > Liab'] = (cash_ttm >= liab_old)
                    else:
                        p['Cash > Liab'] = False
                    
                    # 6. PE RATIO
                    p['PE < 22.5'] = (0 < pe < 22.5)
                    
                    # 7. ROIC > 9%
                    # Pokušavamo izračunati prosjek, ako ne uspije, FAIL
                    try:
                        roic_sum = 0
                        cnt = 0
                        years = min(5, len(fin.columns))
                        for y in range(years):
                            ebit = get_row_val(fin, ['EBIT', 'Pretax Income'], y)
                            equity = get_row_val(bal, ['Stockholders Equity'], y)
                            debt_y = get_row_val(bal, ['Total Debt', 'Long Term Debt'], y)
                            if debt_y is None: debt_y = 0
                            
                            if ebit and equity:
                                invested_cap = equity + debt_y
                                if invested_cap != 0:
                                    roic_sum += (ebit / invested_cap)
                                    cnt += 1
                        
                        if cnt > 0:
                            avg_roic = (roic_sum / cnt) * 100
                            p['ROIC > 9%'] = (avg_roic > 9)
                        else:
                            p['ROIC > 9%'] = False
                    except:
                        p['ROIC > 9%'] = False
                    
                    # 8. SHARE BUYBACK (Shares Outstanding)
                    shares_now = info.get('sharesOutstanding')
                    shares_old = get_row_val(bal, ['Ordinary Shares Number', 'Share Issued'], old_idx)
                    
                    if shares_now and shares_old:
                        p['Buyback'] = (shares_now <= shares_old)
                    else:
                        p['Buyback'] = False
                    
                    # 9. VALUATION (FCF * 20 > Market Cap)
                    fcf_ttm = info.get('freeCashflow')
                    # Ako info nema FCF, probaj izračunati iz CF statementa (Op Cash - CapEx)
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
                    # Ako nema dividende -> Sigurno. Ako ima -> Cash mora biti veci od isplate.
                    if div_rate == 0:
                        p['Div Safety'] = True
                    else:
                        # Aproksimacija isplate: shares * rate
                        total_payout = (shares_now * div_rate) if shares_now else 0
                        p['Div Safety'] = (cash_ttm > total_payout) if cash_ttm else False

                    # --- KRAJ ---
                    score = sum([1 for v in p.values() if v])
                    
                    # Ime kompanije
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
                # Za debugging (možeš maknuti kasnije)
                # st.write(f"Error {ticker}: {e}")
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
            
            # LEGENDA
            st.markdown("---")
            st.subheader("📖 Legenda (Rule #1)")
            c1, c2 = st.columns(2)
            with c1:
                st.info("**Rev/NetInc/Cash Growth:** Usporedba TTM (danas) s podacima od prije 4-5 godina.")
                st.info("**Cash > Debt:** Ukupan Keš veći od Dugoročnog Duga (Long Term Debt).")
                st.info("**Buyback:** Broj dionica danas manji ili jednak onom prije 5 godina.")
            with c2:
                st.info("**ROIC > 9%:** Prosječni povrat na kapital u zadnjih 5 godina.")
                st.info("**Undervalued:** (Free Cash Flow * 20) > Market Cap.")
                st.info("**Div Safety:** Keš pokriva isplatu dividende (ili nema dividende).")
        else:
            st.error("Nije pronađen niti jedan valjani podatak.")
