import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import csv
import io

# ... Keep score_option and get_days_to_expiration functions as previously defined (not repeated here for brevity) ...

# Include the score_option and get_days_to_expiration functions above this line


def main():
    st.title("Short-Term Option Analyzer")

    st.markdown("---")
    st.header("Upload Unusual Options Activity CSV")

    uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])
    if uploaded_file:
        try:
            content = uploaded_file.read().decode('utf-8-sig')
            uploaded_file.seek(0)
            delimiter = csv.Sniffer().sniff(content.splitlines()[0]).delimiter
            df = pd.read_csv(uploaded_file, delimiter=delimiter)
            df.columns = df.columns.str.strip()

            price_col = next((col for col in df.columns if "price" in col.lower()), None)
            if not price_col:
                st.warning("\u2757 No column containing 'Price' found.")
                return

            df_sorted = df.sort_values(by=price_col).head(10)

            st.markdown("---")
            st.header("Analyze Top 10 Parsed Options")
            purchase_date = st.date_input("Select Purchase Date", datetime.today())

            for i, row in df_sorted.iterrows():
                symbol = row['Symbol']
                option_type = row['Type'].lower()
                strike = float(row['Strike'])
                moneyness_pct = float(row['Moneyness'].replace('%', '').strip())
                iv = float(str(row['Imp Vol']).replace('%', '').strip())
                delta = float(row['Delta'])
                premium = st.number_input(f"Premium for {symbol} {option_type.upper()} {strike}", key=f"premium_{i}", format="%.2f")

                expiration_str = str(row['Exp Date'])
                try:
                    expiration_date = datetime.strptime(expiration_str, "%Y-%m-%d")
                except ValueError:
                    st.error(f"Invalid date format in row {i}: {expiration_str}")
                    continue

                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="60d")
                    if hist.empty:
                        st.warning(f"No price history for {symbol}.")
                        continue

                    current_price = hist['Close'][-1]
                    ma20 = hist['Close'].rolling(window=20).mean()[-1]
                    ma50 = hist['Close'].rolling(window=50).mean()[-1]

                    delta_price = hist['Close'].diff()
                    gain = delta_price.where(delta_price > 0, 0)
                    loss = -delta_price.where(delta_price < 0, 0)
                    avg_gain = gain.rolling(window=14).mean()[-1]
                    avg_loss = loss.rolling(window=14).mean()[-1]
                    rs = avg_gain / avg_loss if avg_loss != 0 else 0
                    rsi = 100 - (100 / (1 + rs)) if avg_loss != 0 else 100

                    option_chain = ticker.option_chain(expiration_str)
                    chain_df = option_chain.calls if option_type == 'call' else option_chain.puts
                    match = chain_df[chain_df['strike'] == strike]
                    volume = int(match['volume'].values[0]) if not match.empty else 0
                    oi = int(match['openInterest'].values[0]) if not match.empty else 0

                    days_to_exp = get_days_to_expiration(expiration_date, purchase_date)
                    moneyness_ratio = 1 + (moneyness_pct / 100)

                    verdict, reasons = score_option(
                        current_price, ma20, ma50, rsi, delta, iv, volume, oi,
                        days_to_exp, option_type, moneyness_pct, moneyness_ratio, premium
                    )

                    with st.expander(f"{symbol} {option_type.upper()} {strike} Analysis"):
                        st.write(f"**Current Price:** ${current_price:.2f}")
                        st.write(f"**MA20 / MA50:** {ma20:.2f} / {ma50:.2f}")
                        st.write(f"**RSI:** {rsi:.2f}")
                        st.write(f"**Delta / IV:** {delta:.2f} / {iv:.2f}%")
                        st.write(f"**Volume / OI:** {volume} / {oi}")
                        st.write(f"**Days to Expiration:** {days_to_exp}")
                        st.write(f"**Moneyness % / Ratio:** {moneyness_pct:.2f}% / {moneyness_ratio:.2f}")
                        st.write(f"**Premium Entered:** ${premium:.2f}")
                        st.subheader(f"Verdict: {verdict}")
                        st.write("**Reasons:**")
                        for reason in reasons:
                            st.write("- " + reason)

                except Exception as e:
                    st.error(f"Error analyzing row {i}: {e}")

        except Exception as e:
            st.error(f"Failed to process uploaded file: {e}")


if __name__ == "__main__":
    main()
