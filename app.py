import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime
import ta  # for RSI

# --- Helper functions ---

def calculate_indicators(ticker):
    """Fetch historical prices and compute MA20, MA50, RSI."""
    hist = ticker.history(period="6mo")
    hist["MA20"] = hist["Close"].rolling(20).mean()
    hist["MA50"] = hist["Close"].rolling(50).mean()
    hist["RSI"] = ta.momentum.RSIIndicator(hist["Close"], window=14).rsi()
    latest = hist.iloc[-1]
    return latest["MA20"], latest["MA50"], latest["RSI"]

def score_option(premium, iv, delta, rsi, moneyness, days_to_exp):
    """Return score and rating for an option contract."""
    score = 0
    reasons = []

    # Delta
    if 0.4 <= delta <= 0.6:
        score += 2
        reasons.append("Delta in ideal range (0.4–0.6)")
    elif 0.3 <= delta < 0.4 or 0.6 < delta <= 0.7:
        score += 1
        reasons.append("Delta acceptable")
    else:
        score -= 1
        reasons.append("Delta too weak/strong")

    # IV
    if iv < 40:
        score += 1
        reasons.append("Low implied volatility")
    else:
        score -= 1
        reasons.append("High implied volatility")

    # RSI
    if 40 <= rsi <= 60:
        score += 1
        reasons.append("RSI neutral (40–60)")
    elif rsi < 30:
        score += 2
        reasons.append("RSI oversold (<30)")
    elif rsi > 70:
        score -= 1
        reasons.append("RSI overbought (>70)")

    # Moneyness
    if -5 <= moneyness <= 5:
        score += 2
        reasons.append("At/near the money")
    elif -10 <= moneyness <= 10:
        score += 1
        reasons.append("Reasonably close to the money")
    else:
        score -= 1
        reasons.append("Too far in/out of the money")

    # Days to Expiration
    if 20 <= days_to_exp <= 60:
        score += 2
        reasons.append("Good expiration window (20–60 days)")
    elif 10 <= days_to_exp < 20 or 60 < days_to_exp <= 90:
        score += 1
        reasons.append("Okay expiration window")
    else:
        score -= 1
        reasons.append("Poor expiration window")

    # Premium rule of thumb (relative to moneyness)
    value_ratio = premium / max(1, abs(moneyness))
    if value_ratio < 0.5:
        score += 1
        reasons.append("Premium seems cheap")
    elif value_ratio > 0.9 and days_to_exp > 30:
        score -= 1
        reasons.append("Overpaying for long-dated extrinsic")

    # Final rating
    if score >= 6:
        rating = "Strong Buy"
    elif 4 <= score < 6:
        rating = "Buy"
    elif 2 <= score < 4:
        rating = "Mild Buy"
    else:
        rating = "Avoid"

    return score, rating, reasons


# --- Streamlit app ---
st.title("Options Evaluation Tool")

uploaded_file = st.file_uploader("Upload your CSV (Ticker, Expiration, Strike, Type)", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    results = []
    for idx, row in df.head(25).iterrows():
        try:
            ticker = yf.Ticker(row["Ticker"])
            current_price = ticker.history(period="1d")["Close"].iloc[-1]

            # Indicators
            ma20, ma50, rsi = calculate_indicators(ticker)

            # Days to expiration
            exp_date = datetime.strptime(str(row["Expiration"]), "%Y-%m-%d")
            days_to_exp = (exp_date - datetime.today()).days

            # Option chain
            opt_chain = ticker.option_chain(str(exp_date.date()))
            if row["Type"].lower() == "call":
                chain = opt_chain.calls
            else:
                chain = opt_chain.puts

            opt = chain[chain["strike"] == float(row["Strike"])]
            if opt.empty:
                continue

            opt = opt.iloc[0]
            premium = (opt["bid"] + opt["ask"]) / 2
            iv = opt["impliedVolatility"] * 100
            delta = opt.get("delta", np.nan)  # not always provided
            volume = opt["volume"]
            oi = opt["openInterest"]

            # Moneyness
            moneyness = ((current_price - row["Strike"]) / current_price) * 100 if row["Type"].lower() == "call" else ((row["Strike"] - current_price) / current_price) * 100

            # Scoring
            score, rating, reasons = score_option(premium, iv, delta, rsi, moneyness, days_to_exp)

            results.append({
                "Ticker": row["Ticker"],
                "Type": row["Type"],
                "Strike": row["Strike"],
                "Exp": str(exp_date.date()),
                "Price": round(current_price, 2),
                "Premium": round(premium, 2),
                "MA20": round(ma20, 2),
                "MA50": round(ma50, 2),
                "RSI": round(rsi, 2),
                "Delta": round(delta, 2) if pd.notna(delta) else "N/A",
                "IV (%)": round(iv, 2),
                "Volume": volume,
                "Open Interest": oi,
                "Moneyness (%)": round(moneyness, 2),
                "Days to Exp": days_to_exp,
                "Score": score,
                "Rating": rating,
                "Reasons": "; ".join(reasons)
            })
        except Exception as e:
            st.warning(f"Error on row {idx}: {e}")

    if results:
        st.dataframe(pd.DataFrame(results))
    else:
        st.error("No results to display. Check your CSV format.")
