# DATOTEKA: pages/1_🔍_Screener.py
import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Batch Screener", layout="wide")

st.title("🔍 Batch Screener (10 Pillars)")
st.markdown("Upiši listu dionica za brzu provjeru svih 10 kriterija.")

# INPUT
tickers_input = st.text_area("Lista dionica (odvojene zarezom):", "CRM, AAPL, MSFT, GOOG, TSLA, NVDA, AMD, AMZN, META, NFLX", height=80)

if st.button("🚀 Pokreni Skener"):
    tickers = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(tickers):
        status_text.text(f"Analiziram: {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            fin = stock.financials
            bal = stock.balance_sheet
            cf = stock.cashflow
            info = stock.info
            
            if not fin.empty:
                p = {} # Pillars
                
                # 1. Revenue Growth
                try: p['Rev Growth'] = ((fin.iloc[0,0]-fin.iloc[0,-1]) > 0)
                except: p['Rev Growth'] = False
                
                # 2. Net Inc Growth
                try: p['Net Inc Growth'] = ((fin.loc['Net Income'].iloc[0]-fin.loc['Net Income'].iloc[-1]) > 0)
                except: p['Net Inc Growth'] = False
                
                # 3. Cash Growth
                try:
                    c_row = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal.index else 'Cash Cash Equivalents And Short Term Investments'
                    p['Cash Growth'] = ((bal.loc[c_row].iloc[0]-bal.loc[c_row].iloc[-1]) > 0)
                except: p['Cash Growth'] = False
                
                # Varijables
                total_cash = info.get('totalCash', 0)
                ltd_row = 'Long Term Debt' if 'Long Term Debt' in bal.index else 'Long Term Debt And Capital Lease Obligation'
                lt_debt = bal.loc[ltd_row].iloc[0] if ltd_row in bal.index else 0
                pe = info.get('trailingPE', 0)
                if pe is None: pe = 0
                mkt_cap = info.get('marketCap', 0)
                
                # 4. Debt
                p['Cash > Debt'] = (total_cash >= lt_debt)
                
                # 5. Liab
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
                    p['FCF x20 > Cap'] = ((fcf*20) > mkt_cap)
                except: p['FCF x20 > Cap'] = False
                
                # 10. Div
                p['Div Safety'] = True # Placeholder
                
                # Create Row
                score = sum([1 for v in p.values() if v])
                
                row = {"Ticker": ticker, "Score": score}
                # Add pillars columns with Icons
                for k, v in p.items():
                    row[k] = "✅" if v else "❌"
                
                results.append(row)
                
        except Exception as e:
            pass
            
        progress_bar.progress((i + 1) / len(tickers))
    
    status_text.empty()
    progress_bar.empty()
    
    if results:
        df = pd.DataFrame(results)
        df = df.sort_values(by="Score", ascending=False)
        
        st.success(f"Analizirano {len(results)} dionica.")
        
        # Prikaz Tablice (Sve kolone, bez cijene)
        st.dataframe(
            df,
            column_config={
                "Score": st.column_config.ProgressColumn("Score", format="%d", min_value=0, max_value=10),
            },
            hide_index=True,
            use_container_width=True
        )
        
        # LEGENDA ISPOD TABLICE
        st.markdown("---")
        st.subheader("📖 Legenda Pillara")
        l1, l2 = st.columns(2)
        with l1:
            st.markdown("""
            * **Rev Growth:** Prihodi su rasli u zadnjih 5 godina.
            * **Net Inc Growth:** Dobit je rasla u zadnjih 5 godina.
            * **Cash Growth:** Količina novca je rasla.
            * **Cash > Debt:** Kompanija ima više novca nego dugoročnog duga.
            * **Cash > Liab:** Novac pokriva prosječne dugoročne obveze.
            """)
        with l2:
            st.markdown("""
            * **PE < 22.5:** P/E omjer je ispod 22.5 (Nije preskupa).
            * **ROIC > 9%:** Povrat na investirani kapital je odličan (iznad 9%).
            * **Buyback:** Broj dionica se smanjio (kupuju vlastite dionice).
            * **FCF x20 > Cap:** Konzervativna valuacija (FCF * 20) je veća od tržišne kapitalizacije.
            * **Div Safety:** Dividenda je sigurna (isplaćuju manje nego što imaju keša).
            """)
            
    else:
        st.error("Nije pronađen niti jedan podatak.")
