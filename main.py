import os
from flask import Flask, request, jsonify

app = Flask(name)

SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")

@app.route("/", methods=["GET"])
def home():
    return "CLICK server is running", 200

@app.route("/click/prepare", methods=["POST"])
def click_prepare():
    data = request.form.to_dict()

    click_trans_id = data.get("click_trans_id", "")
    merchant_trans_id = data.get("merchant_trans_id", "")

    return jsonify({
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_prepare_id": 1,
        "error": 0,
        "error_note": "Success"
    })

@app.route("/click/complete", methods=["POST"])
def click_complete():
    data = request.form.to_dict()

    click_trans_id = data.get("click_trans_id", "")
    merchant_trans_id = data.get("merchant_trans_id", "")

    return jsonify({
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_confirm_id": 1,
        "error": 0,
        "error_note": "Success"
    })

if name == "main":
    app.run(host="0.0.0.0", port=10000)
