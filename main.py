from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "CLICK server is running", 200


@app.route("/click/prepare", methods=["POST"])
def click_prepare():
    data = request.form.to_dict()

    return jsonify({
        "click_trans_id": data.get("click_trans_id", ""),
        "merchant_trans_id": data.get("merchant_trans_id", ""),
        "merchant_prepare_id": 1,
        "error": 0,
        "error_note": "Success"
    })


@app.route("/click/complete", methods=["POST"])
def click_complete():
    data = request.form.to_dict()

    return jsonify({
        "click_trans_id": data.get("click_trans_id", ""),
        "merchant_trans_id": data.get("merchant_trans_id", ""),
        "merchant_confirm_id": 1,
        "error": 0,
        "error_note": "Success"
    })
