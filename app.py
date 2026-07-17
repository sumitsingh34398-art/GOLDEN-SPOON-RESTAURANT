import sqlite3
import csv
import io
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'golden_spoon_secret'
CORS(app)

ADMIN_USER = "Sumit"
ADMIN_PASS = "S007"

def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT, phone TEXT, address TEXT, 
                  items TEXT, total REAL, date TEXT, status TEXT DEFAULT 'pending')''')
    conn.commit()
    conn.close()

init_db()

# --- ROUTES ---

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# Yahan add kiya hai taaki /admin kaam kare
@app.route('/admin')
def admin_page():
    return send_from_directory('.', 'admin.html')

@app.route('/<filename>.html')
def serve_html(filename):
    return send_from_directory('.', f'{filename}.html')

@app.route('/assets/<path:path>')
def serve_assets(path):
    return send_from_directory('assets', path)

@app.route('/images/<path:path>')
def serve_images(path):
    return send_from_directory('images', path)

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

# --- API ROUTES ---

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    if data.get('username') == ADMIN_USER and data.get('password') == ADMIN_PASS:
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route('/save-order', methods=['POST'])
def save_order():
    data = request.json
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("INSERT INTO orders (name, phone, address, items, total, date, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
              (data['name'], data['phone'], data['address'], str(data['items']), data['total'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({"message": "Order Saved!"})

@app.route('/get-orders', methods=['GET'])
def get_orders():
    filter_type = request.args.get('filter', 'all')
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    query = "SELECT * FROM orders"
    if filter_type == 'today':
        today = datetime.now().strftime("%Y-%m-%d")
        query += f" WHERE date LIKE '{today}%'"
    elif filter_type == 'week':
        last_week = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        query += f" WHERE date >= '{last_week}'"
    query += " ORDER BY id DESC"
    c.execute(query)
    orders = c.fetchall()
    conn.close()
    return jsonify(orders)

@app.route('/update-order/<int:id>', methods=['POST'])
def update_order(id):
    new_status = request.json.get('status')
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Status Updated!"})

@app.route('/download-csv')
def download_csv():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM orders")
    orders = c.fetchall()
    conn.close()
    from flask import make_response
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Name', 'Phone', 'Address', 'Items', 'Total', 'Date', 'Status'])
    cw.writerows(orders)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=orders_report.csv"
    output.headers["Content-type"] = "text/csv"
    return output

if __name__ == '__main__':
    app.run(debug=False)