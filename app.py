import sqlite3
import csv
import io
import os
import json
import pytz
from flask import Flask, request, jsonify, send_from_directory, make_response, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'golden_spoon_secret'
CORS(app)

ADMIN_USER = "Sumit"
ADMIN_PASS = "S007"
DB_PATH = os.path.join(os.getcwd(), 'orders.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT, phone TEXT, address TEXT, 
                  items TEXT, total REAL, date TEXT, status TEXT DEFAULT 'pending')''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  phone TEXT UNIQUE, password TEXT)''')
    # Nayi Menu Table (Admin se dishes manage karne ke liye)
    c.execute('''CREATE TABLE IF NOT EXISTS menu 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT, price REAL, image TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- ROUTES ---

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/admin')
def admin_page():
    return send_from_directory('.', 'admin.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    if data.get('username') == ADMIN_USER and data.get('password') == ADMIN_PASS:
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

# --- USER AUTHENTICATION ROUTES ---

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (phone, password) VALUES (?, ?)", (data['phone'], data['password']))
        conn.commit()
        return jsonify({"success": True})
    except:
        return jsonify({"success": False, "message": "User already exists"})
    finally:
        conn.close()

@app.route('/login-user', methods=['POST'])
def login_user():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE phone=? AND password=?", (data['phone'], data['password']))
    user = c.fetchone()
    conn.close()
    if user:
        session['user'] = data['phone']
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route('/check-session')
def check_session():
    if 'user' in session:
        return jsonify({"logged_in": True})
    return jsonify({"logged_in": False})

@app.route('/logout')
def logout():
    session.pop('user', None)
    return jsonify({"success": True})

@app.route('/book-table')
def book_table():
    if 'user' not in session:
        return send_from_directory('.', 'login.html')
    return send_from_directory('.', 'order.html')

# --- ORDER ROUTES ---

@app.route('/save-order', methods=['POST'])
def save_order():
    data = request.json
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO orders (name, phone, address, items, total, date, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
              (data['name'], data['phone'], data['address'], str(data['items']), data['total'], current_time))
    conn.commit()
    conn.close()
    return jsonify({"message": "Order Saved Successfully!"})

@app.route('/get-orders', methods=['GET'])
def get_orders():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = c.fetchall()
    conn.close()
    return jsonify(orders)

@app.route('/update-order/<int:id>', methods=['POST'])
def update_order(id):
    new_status = request.json.get('status')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Status Updated!"})

@app.route('/download-csv')
def download_csv():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Phone', 'Address', 'Items', 'Total', 'Date', 'Status'])
    writer.writerows(orders)
    
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=orders.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/receipt/<int:order_id>')
def get_receipt(order_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    order = c.fetchone()
    conn.close()
    
    if not order: return "Order not found"
    
    name, total, date = order[1], float(order[5]), order[6]
    items = json.loads(order[4].replace("'", '"'))
    
    subtotal = total
    service_charge = subtotal * 0.02
    gst = subtotal * 0.015
    final_total = subtotal + service_charge + gst
    
    items_html = "".join([f"<tr><td style='text-align:left;'>{i['name']}</td><td>{i['qty']}</td><td>{i['price']}</td><td>{int(i['qty'])*int(i['price'])}</td></tr>" for i in items])
    
    return f"""
    <html><head><style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Poppins&display=swap');
        body {{ background: #e0e0e0; display: flex; justify-content: center; padding: 20px; }}
        .receipt {{ 
            width: 400px; height: auto; min-height: 600px;
            background: #fff; border: 15px double #d4af37; padding: 30px;
            text-align: center; font-family: 'Poppins', sans-serif;
        }}
        h1 {{ font-family: 'Playfair Display', serif; color: #d4af37; margin: 0; font-size: 28px; }}
        .chef-box {{ border-bottom: 1px dashed #d4af37; padding-bottom: 10px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ border-top: 1px solid #d4af37; border-bottom: 1px solid #d4af37; padding: 8px; color: #d4af37; font-size: 14px; }}
        td {{ padding: 8px; border-bottom: 1px dashed #eee; font-size: 14px; }}
        .totals {{ text-align: right; margin-top: 20px; font-weight: bold; font-size: 14px; }}
        .footer {{ margin-top: 30px; font-size: 12px; border-top: 1px solid #d4af37; padding-top: 10px; }}
        @media print {{ .print-btn {{ display: none; }} }}
    </style></head><body>
        <div class="receipt">
            <h1>GOLDEN SPOON</h1>
            <p style="margin:0; letter-spacing: 2px;">RESTAURANT</p>
            <p style="font-size: 12px; margin-bottom: 20px;">PREMIUM DINING EXPERIENCE</p>
            <div class="chef-box">
                <strong>Chef Sumit Singh</strong><br>Executive Chef
            </div>
            <div style="text-align:left; font-size: 13px;">
                Order ID: #{order_id}<br>Customer: {name}<br>Date: {date}
            </div>
            <table><tr><th>ITEM</th><th>QTY</th><th>RATE</th><th>AMT</th></tr>{items_html}</table>
            <div class="totals">
                Subtotal: ₹{subtotal:.2f}<br>Service Charge (2%): ₹{service_charge:.2f}<br>GST (1.5%): ₹{gst:.2f}<br>
                <h3 style="color:#d4af37; font-size: 20px; margin: 10px 0;">TOTAL: ₹{final_total:.2f}</h3>
            </div>
            <div class="footer">
                Thank You! We hope to serve you again.<br>+91 9602697303<br>46, Sarojini Marg, Ashok Nager, jaipur<br>www.goldenspoon.com
            </div>
            <button class="print-btn" onclick="window.print()" style="margin-top:20px; background:#d4af37; border:none; padding:10px 20px; cursor:pointer;">Print Receipt</button>
        </div>
    </body></html>
    """

# --- NEW ADMIN FEATURES ROUTES (Added safely) ---

@app.route('/get-users', methods=['GET'])
def get_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, phone FROM users ORDER BY id DESC")
    users = c.fetchall()
    conn.close()
    return jsonify(users)

@app.route('/get-menu', methods=['GET'])
def get_menu():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM menu")
    items = c.fetchall()
    conn.close()
    return jsonify(items)

@app.route('/add-menu-item', methods=['POST'])
def add_menu_item():
    data = request.json
    name = data.get('name')
    price = data.get('price')
    image = data.get('image')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO menu (name, price, image) VALUES (?, ?, ?)", (name, price, image))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Item added successfully!"})

if __name__ == '__main__':
    app.run(debug=True)
