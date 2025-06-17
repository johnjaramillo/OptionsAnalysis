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

    # Estimate intrinsic value (for calls)
    if option_type == 'call':
        intrinsic_value = max(0, stock_price - strike)
    else:  # puts
        intrinsic_value = max(0, strike - stock_price)

    extrinsic_value = premium - intrinsic_value
    value_ratio = extrinsic_value / premium if premium != 0 else 0

    # Scoring logic based on value breakdown
    if intrinsic_value > 0 and value_ratio <= 0.3:
        score += 2
        reasons.append(f"Mostly intrinsic value (${intrinsic_value:.2f}): good deal")
    elif value_ratio <= 0.6:
        score += 1
        reasons.append(f"Decent balance of intrinsic (${intrinsic_value:.2f}) and extrinsic")
    elif value_ratio > 0.9:
        score -= 2
        reasons.append(f"Mostly extrinsic value (${extrinsic_value:.2f}): expensive for risk")
    else:
        reasons.append(f"Premium mix ok (${premium:.2f}, {value_ratio:.0%} extrinsic)")


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

    uploaded_file = st.file_uploader("Upload Unusual Options Activity CSV", type=["csv"])
    if uploaded_file:
        try:
            # Try common delimiters
            try:
                df = pd.read_csv(uploaded_file, delimiter=',')
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, delimiter='\t')

            # Debug: Show columns to user
            st.write("CSV columns detected:", list(df.columns))

            # Strip whitespace from columns and remove quotes
            df.columns = df.columns.str.strip().str.replace('"', '')

            # Sort by Price~ column (strip % if any and convert)
            def parse_price(x):
                try:
                    return float(str(x).replace('%','').replace(',',''))
                except:
                    return 0.0
            df['Price~'] = df['Price~'].apply(parse_price)
            df = df.sort_values(by='Price~', ascending=True).head(10)

            for idx, row in df.iterrows():
                st.markdown(f"### Option {idx+1}: {row['Symbol']} {row['Type']} Strike {row['Strike']} Exp {row['Exp Date']}")

                # User inputs per option:
                purchase_date = st.date_input(f"Purchase Date for option {idx+1}", datetime.today(), key=f"purchase_date_{idx}")
                premium = st.number_input(f"Premium for option {idx+1}", min_value=0.0, format="%.4f", key=f"premium_{idx}")

                # Prepare variables
                try:
                    strike = float(row['Strike'])
                    moneyness_pct = float(str(row['Moneyness']).replace('%','').replace('+',''))
                    delta = float(str(row['Delta']).replace('%',''))
                    iv = float(str(row['Imp Vol']).replace('%',''))
                    volume = int(row['Volume'])
                    open_interest = int(row['Open Int'])
                except Exception as e:
                    st.error(f"Skipping row {idx} due to data conversion error: {e}")
                    continue

                try:
                    ticker = yf.Ticker(row['Symbol'])
                    hist = ticker.history(period="60d")
                    if hist.empty:
                        st.error(f"Failed to fetch stock data for {row['Symbol']}. Skipping.")
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

                except Exception as e:
                    st.error(f"Error fetching stock data for {row['Symbol']}: {e}")
                    continue

                days_to_exp = get_days_to_expiration(datetime.strptime(row['Exp Date'], "%Y-%m-%d"), purchase_date)
                moneyness_ratio = 1 + (moneyness_pct / 100)
                option_type = row['Type'].lower()

                verdict, reasons = score_option(
                    current_price, ma20, ma50, rsi, delta, iv, volume, open_interest,
                    days_to_exp, option_type, moneyness_pct, moneyness_ratio, premium
                )

                st.write("**Stats:**")
                st.write(f"- Current Price: ${current_price:.2f}")
                st.write(f"- MA20: {ma20:.2f}")
                st.write(f"- MA50: {ma50:.2f}")
                st.write(f"- RSI: {rsi:.2f}")
                st.write(f"- Delta: {delta:.4f}")
                st.write(f"- Implied Volatility: {iv:.2f}%")
                st.write(f"- Volume: {volume}")
                st.write(f"- Open Interest: {open_interest}")
                st.write(f"- Days to Expiration: {days_to_exp}")
                st.write(f"- Moneyness: {moneyness_pct:+.2f}%")
                st.write(f"- Premium: ${premium:.2f}")

                st.write(f"**Verdict: {verdict}**")
                st.write("Reasons:")
                for reason in reasons:
                    st.write(f"- {reason}")

                st.markdown("---")

        except Exception as e:
            st.error(f"Failed to process uploaded file: {e}")
    else:
        st.info("Upload a CSV file to get started.")

if __name__ == "__main__":
    main()
