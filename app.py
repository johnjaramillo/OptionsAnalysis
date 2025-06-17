import streamlit as st
import yfinance as yf
from datetime import datetime
import pandas as pd

def get_days_to_expiration(expiration_date, purchase_date):
    if isinstance(expiration_date, str):
        expiration_date = datetime.strptime(expiration_date, "%Y-%m-%d").date()
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
    st.title("📊 Short-Term Options Analyzer")

    uploaded_file = st.file_uploader("Upload Unusual Options CSV", type=["csv"])

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            df = df.head(10)  # Analyze top 10 rows
            results = []

            for i, row in df.iterrows():
                with st.expander(f"{i+1}. {row['Symbol']} {row['Type']} Exp: {row['Exp Date']}"):
                    try:
                        symbol = row['Symbol']
                        expiration = row['Exp Date']
                        option_type = row['Type'].lower()
                        strike = float(row['Strike'])
                        delta = float(row['Delta'])

                        moneyness_pct = float(str(row['Moneyness']).replace('%', '').replace('+', '').replace(',', ''))
                        iv = float(str(row['Imp Vol']).replace('%', '').replace('+', '').replace(',', ''))
                        volume = int(row['Volume'])
                        open_interest = int(row['Open Int'])

                        purchase_date = st.date_input(f"📅 Purchase date for {symbol}", key=f"date_{i}")
                        premium = st.number_input(f"💵 Premium for {symbol}", min_value=0.0, key=f"premium_{i}", format="%.2f")

                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(period="60d")
                        if hist.empty:
                            st.warning(f"⚠️ No price data for {symbol}")
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

                        days_to_exp = get_days_to_expiration(expiration, purchase_date)
                        moneyness_ratio = 1 + (moneyness_pct / 100)

                        verdict, reasons = score_option(
                            current_price, ma20, ma50, rsi, delta, iv, volume, open_interest,
                            days_to_exp, option_type, moneyness_pct, moneyness_ratio, premium
                        )

                        st.markdown(f"### Verdict: **{verdict}**")
                        st.write("Reasons:")
                        for r in reasons:
                            st.write(f"- {r}")

                    except Exception as e:
                        st.error(f"Error analyzing row {i}: {e}")

        except Exception as e:
            st.error(f"Failed to load file: {e}")

if __name__ == "__main__":
    main()
