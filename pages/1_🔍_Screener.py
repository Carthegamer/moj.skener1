import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Batch Screener", layout="wide")

st.title("🔍 Batch Screener (Smart Data)")
st.markdown("Napredna provjera 10 Pillara s pametnim dohvaćanjem podataka.")

# --- INPUT ---
col_in1, col_in2 = st.columns([3, 1])
with col_in1:
    tickers_input = st.text_area(
        "Upiši simbole (odvojene zarezom):", 
        "AMZN, CRM, AAPL, MSFT, GOOG, TSLA, NVDA, META, AMD, NFLX", 
        height=70
    )

with col_in2:
    st.markdown("<br>", unsafe_allow_html=True)
    scan_btn = st.button("🚀 Pokreni Skener", type="primary", use_container_width=True)

# --- PAMETNA FUNKCIJA ZA TRAŽENJE VRIJEDNOSTI ---
def get_historical_value(df, keys_list, col_idx=-1):
    """
    Traži vrijednost u df. Ako ne nađe u zadnjem stupcu (najstarijem),
    pokušava stupac prije njega.
    keys_list: lista mogućih naziva redaka.
    """
    if df.empty: return None
    
    # Iteriraj kroz stupce od najstarijeg (-1) prema novijem
    # Da izbjegnemo situaciju gdje je zadnja godina prazna (NaN)
    num_cols = len(df.columns)
    check_cols = range(num_cols - 1, -1, -1) # npr. 4, 3, 2, 1, 0
    
    # Prvo probaj naći redak
    found_row = None
    for k in keys_list:
        # Case insensitive match
        matches = df.index[df.index.str.contains(k, case=False, regex=False)]
        if len(matches) > 0:
            found_row = matches[0]
            break
    
    if found_row:
        # Sada traži prvu valjanu vrijednost u tom retku (odostraga)
        row_data = df.loc[found_row]
        for i in range(1, len(row_data)+1):
            val = row_data.iloc[-i]
            if pd.notna(val) and val != 0:
                return val
    return None

def get_total_cash_history(bal):
    """Zbraja Cash + Short Term Investments za povijest"""
    c1 = get_historical_value(bal, ['Cash And Cash Equivalents', 'Cash'])
    c2 = get_historical_value(bal, ['Short Term Investments', 'Other Short Term Investments'])
    
    total = 0
    if c1: total += c1
    if c2: total += c2
    return total if total > 0 else None

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
                
                # Provjera podataka
                if not info or 'currentPrice' not in info:
                    raise Exception("No Data")

                fin = stock.financials
                bal = stock.balance_sheet
                cf = stock.cashflow
                
                if not fin.empty:
                    p = {} 
                    
                    # --- TRENUTNI PODACI (TTM/MRQ) ---
                    rev_ttm = info.get('totalRevenue')
                    # Fallback za Net Income (ako nema u info, uzmi iz fin)
                    net_inc_ttm = info.get('netIncomeToCommon')
                    if net_inc_ttm is None: 
                        net_inc_ttm = get_historical_value(fin, ['Net Income'], 0) # 0 = najnovije

                    cash_ttm = info.get('totalCash')
                    debt_ttm = info.get('totalDebt')
                    mkt_cap = info.get('marketCap', 0)
                    pe = info.get('trailingPE', 0)
                    if pe is None: pe = 0
                    
                    # --- POVIJESNI PODACI ---
                    rev_old = get_historical_value(fin, ['Total Revenue', 'Operating Revenue'])
                    ni_old = get_historical_value(fin, ['Net Income', 'Net Income Common'])
                    
                    # Total Cash History (Sumirano)
                    cash_old = get_total_cash_history(bal)
                    
                    # Shares History (Iz Income Statementa je najsigurnije)
                    shares_old = get_historical_value(fin, ['Basic Average Shares', 'Diluted Average Shares'])

                    # --- IZRAČUN PILLARA ---

                    # 1. REVENUE GROWTH
                    if rev_ttm and rev_old:
                        p['Rev Growth'] = (rev_ttm >= rev_old)
                    else: p['Rev Growth'] = False

                    # 2. NET INCOME GROWTH
                    if net_inc_ttm is not None and ni_old is not None:
                         # Pazimo na minus
                         if ni_old < 0 and net_inc_ttm > ni_old: p['Net Inc Growth'] = True
                         else: p['Net Inc Growth'] = (net_inc_ttm >= ni_old)
                    else: p['Net Inc Growth'] = False

                    # 3. CASH GROWTH
                    if cash_ttm is not None and cash_old is not None:
                        p['Cash Growth'] = (cash_ttm >= cash_old)
                    else: p['Cash Growth'] = False

                    # 4. REPAY DEBT (Cash > LT Debt)
                    lt_debt = get_historical_value(bal, ['Long Term Debt'], 0)
                    if lt_debt is None: lt_debt = 0
                    
                    if cash_ttm is not None:
                        p['Cash > Debt'] = (cash_ttm >= lt_debt)
                    else: p['Cash > Debt'] = False
                    
                    # 5. REPAY LIABILITIES
                    liab_old = get_historical_value(bal, ['Total Non Current Liabilities'], 0)
                    if cash_ttm is not None and liab_old is not None:
                        p['Cash > Liab'] = (cash_ttm >= liab_old)
                    else: p['Cash > Liab'] = False
                    
                    # 6. PE RATIO
                    p['PE < 22.5'] = (0 < pe < 22.5)
                    
                    # 7. ROIC > 9% (AVG)
                    try:
                        roic_sum = 0
                        cnt = 0
                        years = min(5, len(fin.columns))
                        for y in range(years):
                            # Koristimo iloc direktno za brzinu
                            ebit = fin.loc['EBIT'].iloc[y] if 'EBIT' in fin.index else fin.loc['Pretax Income'].iloc[y]
                            equity = bal.loc['Stockholders Equity'].iloc[y] if 'Stockholders Equity' in bal.index else 0
                            
                            d_val = 0
                            if 'Total Debt' in bal.index: d_val = bal.loc['Total Debt'].iloc[y]
                            
                            if equity != 0:
                                roic_sum += (ebit / (equity + d_val))
                                cnt += 1
                        
                        if cnt > 0:
                            p['ROIC > 9%'] = ((roic_sum / cnt) * 100 > 9)
                        else:
                            # Fallback na ROE
                            p['ROIC > 9%'] = (info.get('returnOnEquity', 0) > 0.09)
                    except:
                        p['ROIC > 9%'] = False
                    
                    # 8. SHARE BUYBACK
                    shares_now = info.get('sharesOutstanding')
                    # AMZN: 2021 (~10B split adj) -> 2024 (~10.5B). Povećali su broj dionica.
                    # Dakle, za AMZN ovo MORA biti Crveno (False).
                    # Ako želimo biti blagi (npr. rast manji od 1%), možemo dodati buffer.
                    # Ali Rule #1 je strog.
                    if shares_now and shares_old:
                        p['Buyback'] = (shares_now <= shares_old * 1.01) # Dozvoli 1% rasta (SBC)
                    else:
                        p['Buyback'] = False
                    
                    # 9. VALUATION
                    fcf_ttm = info.get('freeCashflow')
                    if fcf_ttm is None and not cf.empty:
                         # Calc manual
                         op = cf.loc['Operating Cash Flow'].iloc[0] if 'Operating Cash Flow' in cf.index else 0
                         cap = cf.loc['Capital Expenditure'].iloc[0] if 'Capital Expenditure' in cf.index else 0
                         fcf_ttm = op + cap
                    
                    if fcf_ttm and mkt_cap:
                        p['Undervalued'] = ((fcf_ttm * 20) > mkt_cap)
                    else: p['Undervalued'] = False
                    
                    # 10. DIVIDEND
                    div_rate = info.get('dividendRate', 0)
                    if div_rate is None or div_rate == 0:
                        p['Div Safety'] = True
                    else:
                        payout = info.get('payoutRatio', 0)
                        p['Div Safety'] = (payout is not None and payout < 0.90)

                    # --- FINISH ---
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
                # st.write(e) # Debug
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
            st.caption("Napomena: Cash Growth sada zbraja (Cash + Short Term Investments). Buyback gleda Basic Average Shares iz Income Statementa.")
        else:
            st.error("Nije pronađen niti jedan valjani podatak.")
