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

    # Trend
    if option_type == 'call':
        if stock_price > ma20 and stock_price > ma50:
            score += 2
            reasons.append("Strong uptrend (Price > MA20 & MA50)")
        else:
            reasons.append("Weak uptrend or downtrend")
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
            reasons.append("Weak downtrend or uptrend")
        if 30 <= rsi <= 50:
            score += 1
            reasons.append("RSI in bearish range (30–50)")
        elif rsi < 30:
            reasons.append("RSI low (<30), possible oversold")

    # Delta
    if delta >= 0.7:
        score += 2
        reasons.append("High delta (≥0.7): Good ITM chance")
    elif 0.35 <= delta < 0.7:
        score += 1
        reasons.append("Moderate delta (0.35–0.7)")
    else:
        reasons.append(f"Low delta ({delta:.2f})")

    # IV
    if iv > 150:
        reasons.append(f"Very high IV ({iv:.2f}%): Risky")
    elif 80 <= iv <= 150:
        score += 1
        reasons.append(f"Moderate IV ({iv:.2f}%)")
    else:
        score += 1
        reasons.append(f"Low IV ({iv:.2f}%)")

    # Liquidity
    if volume >= 500:
        if open_interest >= 500:
            score += 2
            reasons.append("High liquidity")
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

    # Time to exp
    if days_to_exp <= 5:
        if delta >= 0.7:
            score += 2
            reasons.append("Short expiry, high delta")
        else:
            reasons.append("Short expiry, low delta")
    elif 6 <= days_to_exp <= 14:
        score += 2
        reasons.append("Medium-term expiry")
    elif 15 <= days_to_exp <= 30:
        score += 1
        reasons.append("Longer expiry")
    else:
        reasons.append("Long expiry")

    # Moneyness
    if option_type == 'call':
        if moneyness_ratio >= 1.05:
            score += 2
            reasons.append(f"Deep ITM call ({moneyness_pct:+.1f}%)")
        elif 1.0 <= moneyness_ratio < 1.05:
            score += 1
            reasons.append(f"Slightly ITM call ({moneyness_pct:+.1f}%)")
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
            reasons.append(f"Slightly ITM put ({moneyness_pct:+.1f}%)")
        elif 1.0 < moneyness_ratio <= 1.05:
            score += 1
            reasons.append(f"Near ATM put ({moneyness_pct:+.1f}%)")
        else:
            reasons.append(f"OTM put ({moneyness_pct:+.1f}%)")

    # Premium
    if premium < 0.25 and delta >= 0.35:
        score += 1
        reasons.append(f"Low premium with decent delta")
    elif premium > 1.00 and delta < 0.3:
        score -= 1
        reasons.append(f"High premium with low delta")
    else:
        reasons.append("Premium typical")

    # Final Verdict
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
    st.title("Batch Options Analyzer")

    uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            top10 = df.sort_values(by="Price~").head(10)
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return

        purchase_date = st.date_input("Purchase Date", datetime.today())
        default_premium = st.number_input("Enter default premium for each option", min_value=0.0, format="%.2f")

        for index, row in top10.iterrows():
            try:
                symbol = row['Symbol']
                expiration = datetime.strptime(str(row['Exp Date']), "%Y-%m-%d")
                option_type = row['Type'].lower()
                strike = float(row['Strike'])
                moneyness_pct = float(row['Moneyness'])
                moneyness_ratio = 1 + (moneyness_pct / 100)
                delta = float(row['Delta'])
                iv = float(row['Imp Vol'])
                volume = int(row['Volume'])
                open_interest = int(row['Open Int'])
                premium = default_premium

                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="60d")
                if hist.empty:
                    st.warning(f"{symbol}: No historical data.")
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

                verdict, reasons = score_option(
                    current_price, ma20, ma50, rsi, delta, iv,
                    volume, open_interest, days_to_exp,
                    option_type, moneyness_pct, moneyness_ratio, premium
                )

                with st.expander(f"{symbol} {option_type.upper()} @ {strike} expiring {expiration.date()} — {verdict}"):
                    st.write(f"Current Price: ${current_price:.2f}")
                    st.write(f"Premium: ${premium:.2f}")
                    st.write(f"Delta: {delta:.2f}")
                    st.write(f"IV: {iv:.2f}%")
                    st.write(f"Volume: {volume}")
                    st.write(f"Open Interest: {open_interest}")
                    st.write(f"RSI: {rsi:.2f}")
                    st.write(f"MA20: {ma20:.2f}")
                    st.write(f"MA50: {ma50:.2f}")
                    st.write(f"Moneyness: {moneyness_pct:+.2f}%")
                    st.write(f"Days to Expiration: {days_to_exp}")
                    st.write("Reasons:")
                    for r in reasons:
                        st.write(f"- {r}")

            except Exception as e:
                st.error(f"Error analyzing row {index}: {e}")

if __name__ == "__main__":
    main()
