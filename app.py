from flask import Flask, request, jsonify
from flask_cors import CORS # Ye frontend ko backend se baat karne ki ijazat dega

app = Flask(__name__)
CORS(app) # Ye zaroori line hai

@app.route('/save-order', methods=['POST'])
def save_order():
    data = request.json
    print("Naya Order Aaya:", data) # Ye aapke terminal mein dikhega
    
    # Yahan hum baad mein database ka code add karenge
    return jsonify({"status": "success", "message": "Order received by Python!"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)