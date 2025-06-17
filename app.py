import pandas as pd
import datetime
from flask import Flask, request, render_template_string

app = Flask(__name__)

UPLOAD_FORM = """
<!doctype html>
<title>Options Analyzer</title>
<h1>Upload your CSV</h1>
<form action="/" method=post enctype=multipart/form-data>
  <input type=file name=file>
  <br><br>
  Premium (per contract): <input type=text name=premium>
  <br><br>
  Purchase Date (YYYY-MM-DD): <input type=text name=purchase_date>
  <br><br>
  <input type=submit value=Upload>
</form>
<pre>{{ output }}</pre>
"""

def parse_percentage(val):
    try:
        return float(val.strip('%')) / 100
    except:
        return None

def parse_float(val):
    try:
        return float(val.replace('%','').replace(',','').strip())
    except:
        return None

def parse_int(val):
    try:
        return int(val.replace(',','').strip())
    except:
        return 0

def get_days_to_expiration(exp_date_str, purchase_date_str):
    try:
        exp_date = datetime.datetime.strptime(exp_date_str, "%Y-%m-%d")
        purchase_date = datetime.datetime.strptime(purchase_date_str, "%Y-%m-%d")
        return (exp_date - purchase_date).days
    except:
        return None

def score_option(row, premium, purchase_date):
    score = 0
    reasons = []

    price = parse_float(row['Price~'])
    ma20 = parse_float(row.get('MA20', 0))
    ma50 = parse_float(row.get('MA50', 0))
    rsi = parse_float(row.get('RSI', 0))
    delta = parse_float(row.get('Delta'))
    volume = parse_int(row.get('Volume', 0))
    open_int = parse_int(row.get('Open Int', 0))
    iv = parse_percentage(row.get('Imp Vol', '0'))
    moneyness = parse_percentage(row.get('Moneyness', '0'))
    days_to_exp = get_days_to_expiration(row['Exp Date'], purchase_date)
    strike = parse_float(row['Strike'])
    option_type = row['Type'].lower()
    stock_price = price

    # Trend
    if price > ma20 and price > ma50:
        score += 2
        reasons.append("Strong uptrend (Price > MA20 & MA50)")
    elif price > ma20 or price > ma50:
        score += 1
        reasons.append("Mild uptrend")
    else:
        score -= 1
        reasons.append("Weak trend")

    # RSI
    if 50 <= rsi <= 70:
        score += 1
        reasons.append("RSI in bullish range (50–70)")
    elif rsi < 30:
        score -= 1
        reasons.append("RSI oversold")

    # Delta
    if delta >= 0.7:
        score += 2
        reasons.append("High delta (≥ 0.7): Good ITM chance short-term")
    elif delta >= 0.5:
        score += 1
        reasons.append("Moderate delta")
    elif delta <= 0.25:
        score -= 1
        reasons.append("Low delta")

    # IV
    if iv > 1.0:
        score -= 1
        reasons.append(f"Very high IV ({iv:.2%}): High premium but risky")
    elif iv > 0.6:
        score += 1
        reasons.append(f"High IV: Could benefit sellers")

    # Volume & OI
    if volume >= 500:
        score += 1
        reasons.append("High volume (≥ 500)")
    if open_int >= 500:
        score += 1
        reasons.append("Strong open interest (≥ 500)")
    elif open_int == 0:
        score -= 1
        reasons.append("No open interest")

    # Expiration
    if days_to_exp is not None:
        if days_to_exp < 15:
            score -= 2
            reasons.append(f"Expiration soon ({days_to_exp} days): risk of theta decay")
        elif days_to_exp < 30:
            score += 1
            reasons.append(f"Short-term play ({days_to_exp} days)")
        else:
            score += 0
            reasons.append(f"Expiration beyond 30 days: more uncertain for short-term")

    # Moneyness
    if moneyness > 1.2:
        score += 1
        reasons.append(f"Deep ITM call (moneyness={moneyness:.2f})")
    elif 1.0 < moneyness <= 1.2:
        score += 1
        reasons.append(f"ITM option")
    elif 0.95 < moneyness <= 1.0:
        score += 0
        reasons.append(f"ATM option")
    else:
        score -= 1
        reasons.append(f"OTM option")

    # Premium value analysis
    if option_type == 'call':
        intrinsic_value = max(0, stock_price - strike)
    else:
        intrinsic_value = max(0, strike - stock_price)

    extrinsic_value = premium - intrinsic_value
    value_ratio = extrinsic_value / premium if premium != 0 else 0

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

    verdict = "Buy" if score >= 4 else ("Watch" if score >= 2 else "Avoid")
    return verdict, reasons

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    output = ""
    if request.method == 'POST':
        file = request.files['file']
        premium = float(request.form['premium'])
        purchase_date = request.form['purchase_date']

        try:
            df = pd.read_csv(file)
            df = df.sort_values(by='Price~', ascending=False)
            results = []

            for i, row in df.iterrows():
                try:
                    verdict, reasons = score_option(row, premium, purchase_date)
                    result = f"{row['Symbol']} ({row['Type']} {row['Strike']} @ {row['Exp Date']})\nVerdict: {verdict}\n\nReasons:\n- " + "\n- ".join(reasons)
                    results.append(result + "\n" + "="*50 + "\n")
                except Exception as e:
                    results.append(f"Error analyzing row {i}: {e}\n")

            output = "\n".join(results)
        except Exception as e:
            output = f"Failed to process uploaded file: {e}"

    return render_template_string(UPLOAD_FORM, output=output)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
