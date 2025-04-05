import requests
import json
import os
from flask import Flask, render_template, request

app = Flask(__name__)

# Use environment variable for the Cohere API key
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
if not COHERE_API_KEY:
    raise ValueError("Please set the COHERE_API_KEY environment variable.")
API_URL = "https://api.cohere.ai/v1/chat"


def call_cohere(prompt, system_message="You are a tax assistant for India."):
    headers = {
        "Authorization": f"Bearer {COHERE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "command-r-plus",
        "message": prompt,
        "system": system_message,
        "temperature": 0,
        "max_tokens": 700
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["text"]
    except requests.exceptions.HTTPError as e:
        return f"API Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"Unexpected Error: {e}"


def extract_details(user_input):
    prompt = (
        f"Extract income, deductions, and regime (old/new) from: '{user_input}'. "
        "Convert Indian terms like '10 lakhs' to numeric (10 lakhs = 1000000). "
        "If not specified, assume deductions are 0 and regime is 'new'. "
        "Return valid JSON only, nothing else, e.g., {{'income': 1000000, 'deductions': 150000, 'regime': 'old'}}."
    )
    response = call_cohere(prompt)
    if not response:
        return {"income": 0, "deductions": 0, "regime": "new"}
    try:
        response = response.replace("'", '"')
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        return {"income": 0, "deductions": 0, "regime": "new"}


def calculate_tax_new_regime(income):
    if income <= 300000:
        return 0
    elif income <= 600000:
        return (income - 300000) * 0.05
    elif income <= 900000:
        return 15000 + (income - 600000) * 0.10
    elif income <= 1200000:
        return 45000 + (income - 900000) * 0.15
    elif income <= 1500000:
        return 90000 + (income - 1200000) * 0.20
    else:
        return 150000 + (income - 1500000) * 0.30


def calculate_tax_old_regime(income, deductions):
    taxable_income = max(0, income - deductions - 50000)
    if taxable_income <= 250000:
        return 0
    elif taxable_income <= 500000:
        tax = (taxable_income - 250000) * 0.05
    elif taxable_income <= 1000000:
        tax = 12500 + (taxable_income - 500000) * 0.20
    else:
        tax = 112500 + (taxable_income - 1000000) * 0.30
    return tax * 1.04  # 4% cess


def suggest_itr_form(income):
    if income <= 5000000:
        return "ITR-1 (Sahaj)"
    else:
        return "ITR-2 or higher"


@app.route("/", methods=["GET", "POST"])
def index():
    response = None
    if request.method == "POST":
        user_input = request.form.get("user_input", "")
        details = extract_details(user_input)
        income = details.get("income", 0)
        deductions = details.get("deductions", 0)
        regime = details.get("regime", "new")

        tax_new = calculate_tax_new_regime(income)
        tax_old = calculate_tax_old_regime(income, deductions)
        itr_form = suggest_itr_form(income)

        savings = tax_old - tax_new
        if savings > 0:
            comparison = (f"For your income of ₹{income} and deductions of ₹{deductions}, "
                          f"the tax under the old regime is ₹{tax_old}, while the new regime tax is ₹{tax_new}. "
                          f"The new regime saves you ₹{savings} since it offers lower rates and doesn’t rely on deductions.")
        elif savings < 0:
            comparison = (f"For your income of ₹{income} and deductions of ₹{deductions}, "
                          f"the tax under the old regime is ₹{tax_old}, while the new regime tax is ₹{tax_new}. "
                          f"The old regime saves you ₹{-savings} because your deductions reduce taxable income effectively.")
        else:
            comparison = (f"For your income of ₹{income} and deductions of ₹{deductions}, "
                          f"both the old regime tax and new regime tax are ₹{tax_new}. No savings either way.")

        prompt = (
            f"User said: '{user_input}'. {comparison} The ITR form is {itr_form}. "
            "Respond naturally, explaining this comparison clearly and suggesting the better option."
        )
        response = call_cohere(prompt)

    return render_template("index.html", response=response)


if __name__ == "__main__":
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "c323295eb9c9bbf6a020373ac330a11f")  # Required for sessions
    app.run(debug=False)  # Disable debug for production