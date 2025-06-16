import streamlit as st
import yfinance as yf
from datetime import datetime

def get_days_to_expiration(expiration_date, buy_date):
    return (expiration_date - buy_date).days

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
        reasons.append("High delta (≥0.7): Good ITM chance")
    elif 0.35 <= delta < 0.7:
        score += 1
        reasons.append("Moderate delta (0.35–0.7)")
    else:
        reasons.append(f"Low delta ({delta:.2f})")

    if iv > 150:
        reasons.append(f"Very high IV ({iv:.2f}%): High premium but risky")
    elif 80 <= iv <= 150:
        score += 1
        reasons.append(f"Moderate IV ({iv:.2f}%)")
    else:
        score += 1
        reasons.append(f"Low IV ({iv:.2f}%)")

    if volume >= 500:
        if open_interest >= 500:
            score += 2
            reasons.append("High liquidity (volume & OI ≥ 500)")
        else:
            score += 1
            reasons.append("High volume, moderate OI")
    elif volume >= 100:
        if open_interest >= 100:
            score += 1
            reasons.append("Moderate liquidity")
        else:
            reasons.append("Moderate volume, low OI")
    else:
        reasons.append("Low liquidity")

    if days_to_exp <= 5:
        if delta >= 0.7:
            score += 2
            reasons.append("Short-term high-delta: good chance")
        else:
            reasons.append("Short-term low-delta: risky")
    elif 6 <= days_to_exp <= 14:
        score += 2
        reasons.append("Medium-term: good balance")
    elif 15 <= days_to_exp <= 30:
        score += 1
        reasons.append("Longer term: slower move")
    else:
        reasons.append("Long horizon: more uncertain")

    if option_type == 'call':
        if moneyness_ratio >= 1.05:
            score += 2
            reasons.append(f"Deep ITM call ({moneyness_pct:+.1f}%)")
        elif 1.0 <= moneyness_ratio < 1.05:
            score += 1
            reasons.append(f"ITM call ({moneyness_pct:+.1f}%)")
        elif 0.95 <= moneyness_ratio < 1.0:
            score += 1
            reasons.append(f"Near ATM call ({moneyness_pct:+.1f}%)")
        else:
            reasons.append(f"OTM call ({moneyness_pct:+.1f}%)")
    else:
        if moneyness_ratio <= 0.95:
            score += 2
            reasons.append(f"Deep ITM put ({moneyness_pct:+.1f}%)")
        elif 0.95 < moneyness_ratio <= 1.0:
            score += 1
            reasons.append(f"ITM put ({moneyness_pct:+.1f}%)")
        elif 1.0 < moneyness_ratio <= 1.05:
            score += 1
            reasons.append(f"Near ATM put ({moneyness_pct:+.1f}%)")
        else:
            reasons.append(f"OTM put ({moneyness_pct:+.1f}%)")

    if premium < 0.25 and delta >= 0.35:
        score += 1
        reasons.append(f"Low premium (${premium:.2f}) with good delta")
    elif premium > 1.00 and delta < 0.3:
        score -= 1
        reasons.append(f"High premium (${premium:.2f}) with poor delta")
    else:
        reasons.append(f"Typical premium: ${premium:.2f}")

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

# Streamlit App
st.title("📈 Options Trade Evaluator")

symbol = st.text_input("Stock symbol (e.g., FUBO)", value="FUBO").upper()
option_type = st.selectbox("Option type", ["call", "put"])

# Load expiration dates
if symbol:
    try:
        ticker = yf.Ticker(symbol)
        expirations = ticker.options
        expiration = st.selectbox("Select Expiration Date", expirations)
    except Exception:
        expiration = None
        st.warning("Could not fetch expiration dates.")
else:
    expiration = None

strike = st.number_input("Strike price", step=0.01)
moneyness_pct = st.number_input("Moneyness % (e.g., -12 for -12%)")
iv = st.number_input("Implied Volatility (%)", step=0.1)
delta = st.number_input("Delta (0 to 1)", step=0.01)
premium = st.number_input("Premium ($)", step=0.01)
buy_date = st.date_input("Purchase Date")

if st.button("Analyze Option") and expiration:
    try:
        hist = ticker.history(period="60d")
        if hist.empty:
            st.error("Could not load historical data.")
        else:
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

            chain = ticker.option_chain(expiration)
            df = chain.calls if option_type == 'call' else chain.puts
            row = df[df['strike'] == strike]
            if row.empty:
                st.error("Strike not found in option chain.")
            else:
                volume = row['volume'].values[0]
                open_interest = row['openInterest'].values[0]
                days_to_exp = get_days_to_expiration(datetime.strptime(expiration, "%Y-%m-%d"), buy_date)
                moneyness_ratio = 1 + (moneyness_pct / 100)

                verdict, reasons = score_option(
                    current_price, ma20, ma50, rsi, delta, iv, volume, open_interest,
                    days_to_exp, option_type, moneyness_pct, moneyness_ratio, premium
                )

                st.subheader("📊 Results")
                st.markdown(f"**Stock Price**: ${current_price:.2f}")
                st.markdown(f"**MA20**: ${ma20:.2f} | **MA50**: ${ma50:.2f} | **RSI**: {rsi:.2f}")
                st.markdown(f"**Days to Expiration**: {days_to_exp}")
                st.markdown(f"**Volume**: {volume} | **Open Interest**: {open_interest}")
                st.markdown(f"**Moneyness**: {moneyness_pct:+.1f}%")
                st.markdown(f"**Verdict**: `{verdict}`")

                st.markdown("**Reasons:**")
                for reason in reasons:
                    st.markdown(f"- {reason}")

    except Exception as e:
        st.error(f"Error: {str(e)}")
