from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return jsonify({"status": "ok"})


@app.route("/divide/<int:a>/<int:b>")
def divide(a, b):
    # Bug: no guard against division by zero. Overseer's Fixer agent should
    # catch this via the failing test in test_app.py and patch it.
    return jsonify({"result": a / b})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
