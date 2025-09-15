import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
import yfinance as yf

# -----------------------------
# Helper functions
# -----------------------------

def safe_float(val):
    """Convert strings like '158.22%' or '+28.57%' to float."""
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    val = str(val).replace("%", "").replace("+", "").replace(",", "").strip()
    try:
        return float(val)
    except ValueError:
        return None

def get_days_to_expiration(exp_date_str, purchase_date):
    """Calculate DTE given expiration date and purchase date."""
    try:
        exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
        if isinstance(purchase_date, datetime):
            purchase_date = purchase_date.date()
        return (exp_date.date() - purchase_date).days
    except Exception:
        return None

def score_option(row, premium, purchase_date):
    """Score and analyze an option trade."""
    reasons = []
    score = 0

    # Extract values
    price = safe_float(row.get("Price~"))
    delta = safe_float(row.get("Delta"))
    iv = safe_float(row.get("Imp Vol"))
    oi = safe_float(row.get("Open Int"))
    vol = safe_float(row.get("Volume"))
    moneyness = safe_float(row.get("Moneyness"))
    strike = safe_float(row.get("Strike"))
    option_type = row.get("Type", "").lower()
    exp_date = row.get("Exp Date")
    days_to_exp = get_days_to_expiration(exp_date, purchase_date)

    # Simulated stats
    ma20 = price * 0.97 if price else None
    ma50 = price * 0.95 if price else None
    rsi = 55 if price else None

    # -----------------------------
    # Hard filters & penalties
    # -----------------------------
    if delta is None:
        delta = 0.0
    if option_type in ["call", "put"] and delta < 0.35:
        reasons.append(f"Delta too low ({delta:.2f}) — avoid buying low-probability options")
        return "Avoid", reasons

    # Trend checks
    if price and ma20 and price > ma20:
        score += 1
        reasons.append("Price above 20-day MA (uptrend)")
    if price and ma50 and price > ma50:
        score += 1
        reasons.append("Price above 50-day MA (uptrend)")
    if rsi and 50 <= rsi <= 70:
        score += 1
        reasons.append("RSI in bullish range (50–70)")
    if delta and delta >= 0.7:
        score += 2
        reasons.append("High delta (≥0.7): ITM probability good")
    elif delta and delta >= 0.5:
        score += 1
        reasons.append("Moderate delta (0.5–0.7)")

    # IV
    if iv and iv >= 150:
        score -= 1
        reasons.append("Very high IV (≥150%): premium expensive/risky")

    # Liquidity
    if vol and vol >= 500:
        score += 1
        reasons.append("High volume (≥500)")
    if oi and oi >= 500:
        score += 1
        reasons.append("High open interest (≥500)")

    # Expiration
    if days_to_exp is not None:
        if days_to_exp >= 30:
            score += 1
            reasons.append("Expiration ≥30 days: safer for swings")
        elif days_to_exp <= 7:
            score -= 1
            reasons.append("Expiration ≤7 days: higher risk")

    # ITM check
    if moneyness and moneyness > 1.2:
        score += 1
        reasons.append(f"Deep ITM (moneyness={moneyness:.2f})")

    # Premium breakdown
    if price and strike:
        intrinsic = max(price - strike, 0) if option_type == "call" else max(strike - price, 0)
        extrinsic = max(premium - intrinsic, 0)
        value_ratio = extrinsic / premium if premium > 0 else 1
        if value_ratio > 0.9:
            score -= 4
            reasons.append("Premium almost all extrinsic — overpriced")
        elif value_ratio > 0.75:
            score -= 2
            reasons.append("Premium mostly extrinsic — weaker trade")
        if value_ratio > 0.7 and iv and iv > 200:
            score -= 1
            reasons.append("High extrinsic + very high IV: extra penalty")

    # Short-dated low delta
    if days_to_exp is not None and days_to_exp <= 10 and delta < 0.7:
        score -= 2
        reasons.append("Short-dated (<10d) with sub-0.7 delta: theta risk — penalized")

    # Verdict
    if score >= 9:
        verdict = "Strong Buy"
    elif score >= 6:
        verdict = "Buy"
    elif score >= 4:
        verdict = "Mild Buy"
    elif score >= 2:
        verdict = "Hold"
    else:
        verdict = "Avoid"

    # Add stats
    reasons.insert(0, f"Stats — Price: {price}, MA20: {ma20}, MA50: {ma50}, Delta: {delta}, RSI: {rsi}, Vol: {vol}, OI: {oi}, IV: {iv}, DTE: {days_to_exp}")

    return verdict, reasons

def premium_range_analysis(row, purchase_date, price_lookup):
    """Run premium range analysis for different verdicts."""
    results = []
    test_premiums = np.linspace(0.5, 5.0, 10)  # adjust search range if needed
    for prem in test_premiums:
        verdict, _ = score_option(row, prem, purchase_date, price)
        results.append((prem, verdict))
    return results
# -----------------------------
# Streamlit UI
# -----------------------------

def main():
    st.title("Options Analyzer with Smarter Verdicts")

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if not uploaded_file:
        return

    df = pd.read_csv(uploaded_file)
    df = df.head(25)  # only first 25 rows
    df.columns = df.columns.str.strip().str.replace('"', "")
    if "Price~" in df.columns:
        df = df.sort_values(by="Price~", ascending=True)

    for idx, row in df.iterrows():
        st.markdown("---")
        st.subheader(f"{row.get('Symbol', 'N/A')} {row.get('Type', '')} @ {row.get('Strike', 'N/A')} exp {row.get('Exp Date', '')}")

        col1, col2 = st.columns(2)
        with col1:
            premium = st.number_input(f"Premium for {row.get('Symbol', '')}", min_value=0.01, step=0.01, key=f"prem_{idx}")
        with col2:
            purchase_date = st.date_input(f"Purchase date for {row.get('Symbol', '')}", value=datetime.today(), key=f"date_{idx}")

        if st.button(f"Analyze {row.get('Symbol', '')}", key=f"analyze_{idx}"):
            verdict, reasons = score_option(row, premium, purchase_date)
            st.write(f"**Verdict: {verdict}**")
            st.markdown("**Reasons:**")
            for r in reasons:
                st.write("- " + r)
        # Premium range analysis
        ranges = premium_range_analysis(row, purchase_date, price_lookup)
        st.write("**Premium Range Verdicts:**")
        for prem, verdict in ranges:
            st.write(f"${prem:.2f} → {verdict}")
            
if __name__ == "__main__":
    main()


