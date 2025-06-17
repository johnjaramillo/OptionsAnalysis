import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd

def get_days_to_expiration(expiration_date, purchase_date):
    if isinstance(expiration_date, datetime):
        expiration_date = expiration_date.date()
    if isinstance(purchase_date, datetime):
        purchase_date = purchase_date.date()
    return (expiration_date - purchase_date).days

def score_option(stock_price, ma20, ma50, rsi, delta, iv, volume, open_interest,
                 days_to_exp, option_type, moneyness_pct, moneyness_ratio, premium):
    score = 0
    reasons = []

    if option_type == 'call':
        if stock_price > ma20 and stock_price > ma50:
            score += 2
            reasons.append("Strong uptrend (Price > MA20 & MA50)")
        else:
            reasons.append("Weak uptrend or downtrend (Price ≤ MA20 or MA50)")
        if 50 <= rsi <= 70:
            score += 1
            reasons.append("RSI in bullish range (50–70)")
        elif rsi > 70:
            reasons.append("RSI high (>70), possible overbought")
    else:
        if stock_price < ma20 and stock_price < ma50:
            score += 2
            reasons.append("Strong downtrend (Price < MA20 & MA50)")
        else:
            reasons.append("Weak downtrend or uptrend (Price ≥ MA20 or MA50)")
        if 30 <= rsi <= 50:
            score += 1
            reasons.append("RSI in bearish range (30–50)")
        elif rsi < 30:
            reasons.append("RSI low (<30), possible oversold")

    if delta >= 0.7:
        score += 2
        reasons.append("High delta (≥0.7): Good ITM chance short-term")
    elif 0.35 <= delta < 0.7:
        score += 1
        reasons.append("Moderate delta (0.35–0.7): Medium chance")
    else:
        reasons.append(f"Low delta ({delta:.2f}): Lower probability")

    if iv > 150:
        reasons.append(f"Very high IV ({iv:.2f}%): High premium but risky")
    elif 80 <= iv <= 150:
        score += 1
        reasons.append(f"Moderate IV ({iv:.2f}%): Normal volatility")
    else:
        score += 1
        reasons.append(f"Low IV ({iv:.2f}%): Possibly undervalued premium")

    if volume >= 500:
        if open_interest >= 500:
            score += 2
            reasons.append("High liquidity (volume & open interest ≥ 500)")
        else:
            score += 1
            reasons.append("High volume (≥ 500), moderate open interest")
    elif volume >= 100:
        if open_interest >= 100:
            score += 1
            reasons.append("Moderate liquidity (volume & open interest ≥ 100)")
        else:
            reasons.append("Moderate volume, low open interest")
    else:
        reasons.append("Low liquidity: Risk of poor fills")

    if days_to_exp <= 5:
        if delta >= 0.7:
            score += 2
            reasons.append("Very short time to expiration with high delta: good short-term trade")
        else:
            reasons.append("Very short time to expiration with low delta: High risk")
    elif 6 <= days_to_exp <= 14:
        score += 2
        reasons.append("Moderate time to expiration (6–14 days): balanced risk/reward")
    elif 15 <= days_to_exp <= 30:
        score += 1
        reasons.append("Longer time to expiration (15–30 days): slower expected move")
    else:
        reasons.append("Expiration beyond 30 days: more uncertain for short-term")

    if option_type == 'call':
        if moneyness_ratio >= 1.05:
            score += 2
            reasons.append(f"Deep ITM call (moneyness={moneyness_ratio:.2f}, {moneyness_pct:+.1f}%)")
        elif 1.0 <= moneyness_ratio < 1.05:
            score += 1
            reasons.append(f"Slightly ITM call (moneyness={moneyness_ratio:.2f}, {moneyness_pct:+.1f}%)")
        elif 0.95 <= moneyness_ratio < 1.0:
            score += 1
            reasons.append(f"Near ATM call (moneyness={moneyness_ratio:.2f}, {moneyness_pct:+.1f}%)")
        else:
            reasons.append(f"OTM call (moneyness={moneyness_ratio:.2f}, {moneyness_pct:+.1f}%): Lower chance")
    else:
        if moneyness_ratio <= 0.95:
            score += 2
            reasons.append(f"Deep ITM put (moneyness={moneyness_ratio:.2f}, {moneyness_pct:+.1f}%)")
        elif 0.95 < moneyness_ratio <= 1.0:
            score += 1
            reasons.append(f"Slightly ITM put (moneyness={moneyness_ratio:.2f}, {moneyness_pct:+.1f}%)")
        elif 1.0 < moneyness_ratio <= 1.05:
            score += 1
            reasons.append(f"Near ATM put (moneyness={moneyness_ratio:.2f}, {moneyness_pct:+.1f}%)")
        else:
            reasons.append(f"OTM put (moneyness={moneyness_ratio:.2f}, {moneyness_pct:+.1f}%): Lower chance")

    if premium < 0.25 and delta >= 0.35:
        score += 1
        reasons.append(f"Low premium (${premium:.2f}) with decent delta: good value")
    elif premium > 1.00 and delta < 0.3:
        score -= 1
        reasons.append(f"High premium (${premium:.2f}) with low delta: poor value")
    else:
        reasons.append(f"Premium level (${premium:.2f}) is typical")

    if score >= 9:
        verdict = "Strong Buy"
    elif score >= 7:
        verdict = "Buy"
    elif score >= 5:
        verdict = "Mild Buy"
    elif score >= 3:
        verdict = "Hold"
    else:
        verdict = "Avoid"

    return verdict, reasons

def main():
    st.title("Short-Term Option Analyzer")

    symbol = st.text_input("Symbol (e.g. NAK)").upper()

    if symbol:
        ticker = yf.Ticker(symbol)
        try:
            expirations = ticker.options
        except Exception:
            expirations = []

        if expirations:
            expiration_str = st.selectbox("Expiration Date", expirations)
        else:
            st.warning("No expiration dates found for this symbol.")
            return

        purchase_date = st.date_input("Purchase Date", datetime.today())

        option_type = st.selectbox("Option Type", ["call", "put"])

        strike = st.number_input("Strike Price", min_value=0.0, format="%.2f")

        moneyness_pct = st.number_input("Moneyness % (e.g. -13.7)", format="%.2f")

        iv = st.number_input("Implied Volatility (IV %) e.g. 120 for 120%", min_value=0.0, format="%.2f")

        delta = st.number_input("Delta (0–1)", min_value=0.0, max_value=1.0, format="%.4f")

        premium = st.number_input("Option Premium", min_value=0.0, format="%.4f")

        if st.button("Analyze Option"):
            hist = ticker.history(period="60d")
            if hist.empty:
                st.error("Failed to fetch stock data.")
                return

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

            try:
                chain = ticker.option_chain(expiration_str)
                df = chain.calls if option_type == 'call' else chain.puts
                row = df[df['strike'] == strike]
                if row.empty:
                    st.error("Strike price not found in option chain.")
                    return
                volume = int(row['volume'].values[0])
                open_interest = int(row['openInterest'].values[0])
            except Exception:
                st.error("Could not load options data.")
                return

            days_to_exp = get_days_to_expiration(datetime.strptime(expiration_str, "%Y-%m-%d"), purchase_date)
            moneyness_ratio = 1 + (moneyness_pct / 100)

            verdict, reasons = score_option(
                current_price, ma20, ma50, rsi, delta, iv, volume, open_interest,
                days_to_exp, option_type, moneyness_pct, moneyness_ratio, premium
            )

            st.subheader("Results")
            st.write(f"Symbol: {symbol}")
            st.write(f"Option Type: {option_type}")
            st.write(f"Expiration Date: {expiration_str}")
            st.write(f"Strike Price: {strike}")
            st.write(f"Premium: ${premium:.2f}")
            st.write(f"Delta: {delta:.4f}")
            st.write(f"Implied Volatility (IV): {iv:.2f}%")
            st.write(f"Volume: {volume}")
            st.write(f"Open Interest: {open_interest}")
            st.write(f"RSI: {rsi:.2f}")
            st.write(f"Current Price: ${current_price:.2f}")
            st.write(f"MA20: {ma20:.2f}")
            st.write(f"MA50: {ma50:.2f}")
            st.write(f"Days to Expiration: {days_to_exp}")
            st.write(f"Moneyness: {moneyness_pct:+.2f}%")
            st.write(f"Verdict: {verdict}")
            st.write("Reasons:")
            for reason in reasons:
                st.write("- " + reason)

    st.markdown("---")
    st.header("Upload Unusual Options Activity CSV")
    uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])
    if uploaded_file:
        try:
            # Read with utf-8-sig to handle BOM if present
            df = pd.read_csv(uploaded_file, delimiter='\t', encoding='utf-8-sig')
            # Strip whitespace from column names
            df.columns = df.columns.str.strip()
            # Optional: Display columns to debug
            # st.write("Columns detected:", list(df.columns))

            df_sorted = df.sort_values(by="Price~").head(10)
            st.dataframe(df_sorted[[
                "Symbol", "Price~", "Exp Date", "Type", "Strike", "Moneyness",
                "Bid", "Ask", "Volume", "Open Int", "Vol/OI", "Imp Vol", "Delta", "Time"
            ]], use_container_width=True)
        except Exception as e:
            st.error(f"Failed to process uploaded file: {e}")

if __name__ == "__main__":
    main()
