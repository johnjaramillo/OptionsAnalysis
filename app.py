import streamlit as st
import yfinance as yf
from datetime import datetime

# Scoring logic from your CLI code (slightly trimmed for readability)
def get_days_to_expiration(expiration_date_str, buy_date_str):
    expiration_date = datetime.strptime(expiration_date_str, "%Y-%m-%d")
    buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d")
    return (expiration_date - buy_date).days

def score_option(stock_price, ma20, ma50, rsi, delta, iv, volume, open_interest,
                 days_to_exp, option_type, moneyness_pct, moneyness_ratio, premium):
    score = 0
    reasons = []

    if option_type == 'call':
        if stock_price > ma20 and stock_price > ma50:
            score += 2
            reasons.append("Strong uptrend (Price > MA20 & MA50)")
        if 50 <= rsi <= 70:
            score += 1
            reasons.append("RSI in bullish range (50–70)")
    else:
        if stock_price < ma20 and stock_price < ma50:
            score += 2
            reasons.append("Strong downtrend (Price < MA20 & MA50)")
        if 30 <= rsi <= 50:
            score += 1
            reasons.append("RSI in bearish range (30–50)")

    if delta >= 0.7:
        score += 2
        reasons.append("High delta (>= 0.7)")
    elif 0.35 <= delta < 0.7:
        score += 1
        reasons.append("Moderate delta")

    if 80 <= iv <= 150:
        score += 1
        reasons.append("Normal volatility")
    else:
        score += 1
        reasons.append("Low or high IV")

    if volume >= 500 and open_interest >= 500:
        score += 2
        reasons.append("High liquidity")
    elif volume >= 100 and open_interest >= 100:
        score += 1
        reasons.append("Moderate liquidity")

    if days_to_exp <= 5 and delta >= 0.7:
        score += 2
        reasons.append("Short-term with high delta")
    elif 6 <= days_to_exp <= 14:
        score += 2
        reasons.append("Medium term")
    elif 15 <= days_to_exp <= 30:
        score += 1

    if option_type == 'call':
        if moneyness_ratio >= 1.05:
            score += 2
            reasons.append("Deep ITM call")
        elif 1.0 <= moneyness_ratio < 1.05:
            score += 1
            reasons.append("Slightly ITM call")
    else:
        if moneyness_ratio <= 0.95:
            score += 2
            reasons.append("Deep ITM put")
        elif 0.95 < moneyness_ratio <= 1.0:
            score += 1
            reasons.append("Slightly ITM put")

    if premium < 0.25 and delta >= 0.35:
        score += 1
        reasons.append("Good value")

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
    st.title("Options Analyzer with Scoring")
    symbol = st.text_input("Enter stock symbol:").upper()
    buy_date = st.date_input("Buy date (for expiration calculation)", datetime.today())

    if symbol:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="60d")

        if hist.empty:
            st.error("Failed to fetch historical stock data.")
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

        st.write(f"**Current Price:** ${current_price:.2f}")
        st.write(f"**MA20:** {ma20:.2f}, **MA50:** {ma50:.2f}, **RSI:** {rsi:.2f}")

        expirations = ticker.options
        selected_exp = st.selectbox("Select expiration date:", expirations)

        option_type = st.radio("Option Type", ['call', 'put'])

        try:
            chain = ticker.option_chain(selected_exp)
            options_df = chain.calls if option_type == 'call' else chain.puts
            st.dataframe(options_df[['strike', 'lastPrice', 'impliedVolatility', 'delta', 'volume', 'openInterest']])

            selected_strike = st.number_input("Enter strike price to score:", step=0.01)
            selected_row = options_df[options_df['strike'] == selected_strike]

            if not selected_row.empty:
                row = selected_row.iloc[0]
                iv = float(row['impliedVolatility']) * 100
                delta_val = float(row['delta'])
                premium = float(row['lastPrice'])
                volume = int(row['volume'])
                open_interest = int(row['openInterest'])
                moneyness_pct = ((current_price - selected_strike) / selected_strike) * 100 if option_type == 'call' else ((selected_strike - current_price) / selected_strike) * 100
                moneyness_ratio = current_price / selected_strike if option_type == 'call' else selected_strike / current_price
                days_to_exp = get_days_to_expiration(selected_exp, buy_date.strftime("%Y-%m-%d"))

                verdict, reasons = score_option(current_price, ma20, ma50, rsi, delta_val, iv, volume,
                                                open_interest, days_to_exp, option_type, moneyness_pct,
                                                moneyness_ratio, premium)

                st.subheader("Verdict")
                st.write(f"**{verdict}**")
                st.write("### Reasons:")
                for reason in reasons:
                    st.markdown(f"- {reason}")

        except Exception as e:
            st.error("Could not load options data.")

if __name__ == "__main__":
    main()
