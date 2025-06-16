import yfinance as yf
import pandas as pd
import ta
import streamlit as st
from datetime import datetime, timedelta

st.title("📈 Stock Options Analyzer")

symbol = st.text_input("Enter a stock symbol (e.g., NIO):", value="NIO").upper()

if symbol:
    stock = yf.Ticker(symbol)
    hist = stock.history(period="3mo")

    if not hist.empty:
        hist['RSI'] = ta.momentum.RSIIndicator(close=hist['Close']).rsi()
        hist['MA_20'] = hist['Close'].rolling(window=20).mean()
        hist['MA_50'] = hist['Close'].rolling(window=50).mean()
        latest = hist.iloc[-1]

        st.subheader("📊 Technical Indicators")
        st.metric("Current Price", f"${latest['Close']:.2f}")
        st.metric("RSI", f"{latest['RSI']:.2f}")
        st.metric("20-Day MA", f"${latest['MA_20']:.2f}")
        st.metric("50-Day MA", f"${latest['MA_50']:.2f}")

        today = datetime.now().date()
        cutoff = today + timedelta(weeks=4)
        expirations = [date for date in stock.options if datetime.strptime(date, "%Y-%m-%d").date() <= cutoff]

        if expirations:
            for opt_date in expirations:
                st.subheader(f"📅 Options Expiring: {opt_date}")
                options_chain = stock.option_chain(opt_date)

                for label, options in [("Calls", options_chain.calls), ("Puts", options_chain.puts)]:
                    st.markdown(f"**{label}**")
                    subset = options[['contractSymbol', 'strike', 'lastPrice', 'impliedVolatility', 'volume', 'openInterest']]
                    if 'delta' in options.columns:
                        subset['delta'] = options['delta']
                    else:
                        subset['delta'] = 'N/A'
                    st.dataframe(subset.sort_values(by='volume', ascending=False).head(10))
        else:
            st.warning("No options expiring within 4 weeks.")
    else:
        st.error("Invalid stock symbol or no data available.")
