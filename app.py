import pandas as pd

# === Load CSV ===
df = pd.read_excel("/mnt/data/First 15 Options.csv.xlsx")  # adjust if CSV not Excel
df = df.head(25)  # only first 25 rows

# === Helper function to classify option ===
def classify_option(row, premium):
    reasons = []
    score = 0

    # Unpack row values
    price = row['Price']
    ma20 = row['MA20']
    ma50 = row['MA50']
    rsi = row['RSI']
    delta = row['Delta']
    iv = row['IV']
    volume = row['Volume']
    oi = row['Open Interest']
    moneyness = row['Moneyness']
    days_to_exp = row['Days to Expiration']

    # 1. Trend
    if price > ma20 and price > ma50:
        score += 2
        reasons.append("Strong uptrend (Price > MA20 & MA50)")
    elif price > ma20 or price > ma50:
        score += 1
        reasons.append("Moderate uptrend (Price > one MA)")
    else:
        score -= 1
        reasons.append("Weak trend (Price below MAs)")

    # 2. RSI
    if 50 <= rsi <= 70:
        score += 1
        reasons.append("RSI in bullish range (50–70)")
    elif rsi < 30:
        score -= 2
        reasons.append("Oversold (<30) but risky")
    elif rsi > 70:
        score -= 1
        reasons.append("Overbought (>70)")
    else:
        score -= 1
        reasons.append("Neutral RSI")

    # 3. Delta
    if delta >= 0.7:
        score += 2
        reasons.append("High delta (≥0.7): Good ITM chance short-term")
    elif 0.5 <= delta < 0.7:
        score += 1
        reasons.append("Moderate delta (0.5–0.7)")
    else:
        score -= 1
        reasons.append("Low delta (<0.5)")

    # 4. IV
    if iv > 100:
        score -= 2
        reasons.append(f"Very high IV ({iv:.2f}%): High premium but risky")
    elif iv > 50:
        score += 1
        reasons.append(f"Moderate IV ({iv:.2f}%)")
    else:
        reasons.append(f"Low IV ({iv:.2f}%)")

    # 5. Liquidity
    if volume >= 500 and oi >= 500:
        score += 1
        reasons.append("High liquidity (Volume & OI ≥ 500)")
    elif volume >= 100 and oi >= 100:
        reasons.append("Moderate liquidity")
    else:
        score -= 1
        reasons.append("Low liquidity")

    # 6. Expiration
    if days_to_exp <= 30:
        score += 1
        reasons.append("Short-term expiration (≤30 days)")
    else:
        score -= 1
        reasons.append("Long-term expiration (>30 days)")

    # 7. Moneyness
    if moneyness > 1.2:
        score += 1
        reasons.append(f"Deep ITM call (moneyness={moneyness:.2f})")
    elif moneyness > 1.0:
        reasons.append(f"Slight ITM call (moneyness={moneyness:.2f})")
    else:
        score -= 1
        reasons.append(f"OTM call (moneyness={moneyness:.2f})")

    # 8. Premium valuation (relative to moneyness & delta)
    fair_premium = moneyness * delta * price * 0.05  # heuristic
    value_ratio = premium / (fair_premium + 1e-6)

    if value_ratio < 0.7:
        score += 2
        reasons.append(f"Cheap premium (${premium:.2f}) vs fair (${fair_premium:.2f})")
    elif 0.7 <= value_ratio <= 1.3:
        score += 1
        reasons.append(f"Fair premium (${premium:.2f}) vs fair (${fair_premium:.2f})")
    else:
        score -= 2
        reasons.append(f"Overpriced premium (${premium:.2f}) vs fair (${fair_premium:.2f})")

    # Penalty for expensive + long-dated
    if value_ratio > 0.9 and days_to_exp > 30:
        score -= 1
        reasons.append("Extra penalty: Overpaying on long-dated extrinsic")

    # Final verdict
    if score >= 6:
        verdict = "Strong Buy"
    elif 3 <= score < 6:
        verdict = "Buy"
    elif 1 <= score < 3:
        verdict = "Mild Buy"
    else:
        verdict = "Avoid"

    return verdict, score, reasons

# === Run premium ranges for each option ===
def premium_range_analysis(row):
    results = []
    for premium in [0.5, 1, 2, 5, 10, 20, 50]:  # example premium range
        verdict, score, reasons = classify_option(row, premium)
        results.append({
            "Premium": premium,
            "Verdict": verdict,
            "Score": score,
            "Reasons": reasons
        })
    return results

# === Display results ===
for idx, row in df.iterrows():
    print(f"\n=== Option {idx+1} ===")
    print(f"Underlying Price: {row['Price']}")
    print(f"MA20: {row['MA20']}, MA50: {row['MA50']}")
    print(f"RSI: {row['RSI']}, Delta: {row['Delta']}, IV: {row['IV']}%")
    print(f"Volume: {row['Volume']}, OI: {row['Open Interest']}")
    print(f"Moneyness: {row['Moneyness']}, Days to Expiration: {row['Days to Expiration']}")

    results = premium_range_analysis(row)
    for res in results:
        print(f"Premium ${res['Premium']:.2f} → Verdict: {res['Verdict']} (Score {res['Score']})")
        for r in res['Reasons']:
            print(f"  - {r}")
