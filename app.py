import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta

def get_days_to_expiration(expiration_date, purchase_date):
    return (expiration_date - purchase_date).days

def score_option(stock_price, ma20, ma50, rsi, delta, iv, volume, open_interest,
                 days_to_exp, option_type, moneyness_pct, moneyness_ratio, premium):
    score = 0
    reasons = []

    # Trend & RSI
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
    else:  # put
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

    # Delta
    if delta >= 0.7:
        score += 2
        reasons.append("High delta (≥0.7): Good ITM chance short-term")
    elif 0.35 <= delta < 0.7:
        score += 1
        reasons.append("Moderate delta (0.35–0.7): Medium chance")
    else:
        reasons.append(f"Low delta ({delta:.2f}): Lower probability")

    # IV
    if iv > 150:
        reasons.append(f"Very high IV ({iv:.2f}%): High premium but risky")
    elif 80 <= iv <= 150:
        score += 1
        reasons.append(f"Moderate IV ({iv:.2f}%): Normal volatility")
    else:
        score += 1
        reasons.append(f"Low IV ({iv:.2f}%): Possibly undervalued premium")

    # Liquidity
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

    # Days to expiration
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

    # Moneyness
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

    # Premium
    if premium < 0.25 and delta >= 0.35:
        score += 1
        reasons.append(f"Low premium (${premium:.2f}) with decent delta: good value")
    elif premium > 1.00 and delta < 0.3:
        score -= 1
        reasons.append(f"High premium (${premium:.2f}) with low delta: poor value")
    else:
        reasons.append(f"Premium level (${premium:.2f}) is typical")

    # Final verdict
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

    symbol = st.text_input("Enter stock symbol (e.g. FUBO)").upper()

    if not symbol:
        st.info("Please enter a stock symbol.")
        return

    # Fetch expiration dates
    try:
        ticker = yf.Ticker(symbol)
        expirations = ticker.options
    except Exception:
        st.error("Could not fetch option expirations. Check symbol and try again.")
        return

    if not expirations:
        st.error("No expiration dates found for this symbol.")
        return

    expiration = st.selectbox("Select option expiration date", expirations)

    # Compute default purchase date (5 days before expiration or today if that is in the past)
    expiration_date_dt = datetime.strptime(expiration, "%Y-%m-%d")
    default_purchase_date = expiration_date_dt - timedelta(days=5)
    if default_purchase_date.date() < datetime.today().date():
        default_purchase_date = datetime.today()

    purchase_date = st.date_input("Select purchase date", default_purchase_date.date())

    # Inputs
    option_type = st.selectbox("Option type", ["call", "put"])
    strike = st.number_input("Strike price", min_value=0.01, format="%.2f")
    moneyness_pct = st.number_input("Moneyness % (e.g. -13.7 for 13.7% OTM)", format="%.2f")
    iv = st.number_input("Implied Volatility (IV %) e.g. 120 for 120%", min_value=0.01, format="%.2f")
    delta = st.number_input("Delta (0 to 1)", min_value=0.0, max_value=1.0, format="%.4f")
    premium = st.number_input("Option premium", min_value=0.01, format="%.2f")

    if st.button("Analyze Option"):
        # Get stock data
        hist = ticker.history(period="60d")
        if hist.empty:
            st.error("Failed to fetch historical stock data.")
            return

        current_price = hist['Close'][-1]
        ma20 = hist['Close'].rolling(window=20).mean()[-1]
        ma50 = hist['Close'].rolling(window=50).mean()[-1]

        # RSI calculation
        delta_price = hist['Close'].diff()
        gain = delta_price.where(delta_price > 0, 0)
        loss = -delta_price.where(delta_price < 0, 0)
        avg_gain = gain.rolling(window=14).mean()[-1]
        avg_loss = loss.rolling(window=14).mean()[-1]
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi = 100 - (100 / (1 + rs)) if avg_loss != 0 else 100

        # Fetch option chain to get volume & open interest
        try:
            chain = ticker.option_chain(expiration)
            df = chain.calls if option_type == 'call' else chain.puts
            row = df[df['strike'] == strike]
            if row.empty:
                st.warning("Strike price not found in option chain. Volume and Open Interest set to 0.")
                volume = 0
                open_interest = 0
            else:
                volume = int(row['volume'].values[0])
                open_interest = int(row['openInterest'].values[0])
        except Exception:
            st.warning("Could not fetch option chain data. Volume and Open Interest set to 0.")
            volume = 0
            open_interest = 0

        days_to_exp = get_days_to_expiration(expiration_date_dt, datetime.combine(purchase_date, datetime.min.time()))
        moneyness_ratio = 1 + (moneyness_pct / 100)

        verdict, reasons = score_option(
            current_price, ma20, ma50, rsi, delta, iv, volume, open_interest,
            days_to_exp, option_type, moneyness_pct, moneyness_ratio, premium
        )

        st.subheader("Results")
        st.write(f"Symbol: {symbol}")
        st.write(f"Option type: {option_type}")
        st.write(f"Expiration date: {expiration}")
        st.write(f"Purchase date: {purchase_date}")
        st.write(f"Strike price: {strike}")
        st.write(f"Premium: ${premium:.2f}")
        st.write(f"Delta: {delta:.4f}")
        st.write(f"IV: {iv:.2f}%")
        st.write(f"Volume: {volume}")
        st.write(f"Open Interest: {open_interest}")
        st.write(f"RSI: {rsi:.2f}")
        st.write(f"Current stock price: ${current_price:.2f}")
        st.write(f"MA20: {ma20:.2f}")
        st.write(f"MA50: {ma50:.2f}")
        st.write(f"Days to expiration: {days_to_exp}")
        st.write(f"Moneyness: {moneyness_pct:+.2f}%")
        st.write(f"Verdict: **{verdict}**")
        st.write("Reasons:")
        for reason in reasons:
            st.write(f"- {reason}")

if __name__ == "__main__":
    main()
