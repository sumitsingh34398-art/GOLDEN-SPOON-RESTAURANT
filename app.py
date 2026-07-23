import psycopg2
import csv
import io
import os
import json
import pytz
from flask import Flask, request, jsonify, send_from_directory, make_response, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'golden_spoon_secret'
CORS(app)

ADMIN_USER = "Sumit"
ADMIN_PASS = "S007"

# Supabase PostgreSQL Connection URL (Updated to Direct Connection Port 5432 for stable cloud deployment)
DATABASE_URL = 'postgresql://postgres.emrzttveagpiiifiyhsc:Sumit%40007.006@db.emrzttveagpiiifiyhsc.supabase.co:5432/postgres'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id SERIAL PRIMARY KEY, 
                  name TEXT, phone TEXT, address TEXT, 
                  items TEXT, total REAL, date TEXT, status TEXT DEFAULT 'pending')''')
    
    # Update: Users table mein 'name' column joda gaya hai
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id SERIAL PRIMARY KEY, 
                  name TEXT, phone TEXT UNIQUE, password TEXT)''')
    
    # Nayi Menu Table (Admin se dishes manage karne ke liye)
    c.execute('''CREATE TABLE IF NOT EXISTS menu 
                 (id SERIAL PRIMARY KEY, 
                  name TEXT, price REAL, image TEXT)''')
    
    # Update: Reviews table mein image column bhi joda gaya hai online customer reviews ke liye
    c.execute('''CREATE TABLE IF NOT EXISTS reviews 
                 (id SERIAL PRIMARY KEY, 
                  name TEXT, rating INTEGER, comment TEXT, image TEXT, date TEXT)''')
    
    # Safe check: Agar purane database mein 'image' column nahi hai, toh use add kar diya jayega taaki error na aaye
    try:
        c.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS image TEXT")
    except Exception:
        conn.rollback()

    conn.commit()
    c.close()
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
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Update: Database mein name, phone, aur password save kiye ja rahe hain
        c.execute("INSERT INTO users (name, phone, password) VALUES (%s, %s, %s)", (data['name'], data['phone'], data['password']))
        conn.commit()
        return jsonify({"success": True})
    except Exception:
        conn.rollback()
        return jsonify({"success": False, "message": "User already exists"})
    finally:
        c.close()
        conn.close()

@app.route('/login-user', methods=['POST'])
def login_user():
    data = request.json
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE phone=%s AND password=%s", (data['phone'], data['password']))
    user = c.fetchone()
    c.close()
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
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO orders (name, phone, address, items, total, date, status) VALUES (%s, %s, %s, %s, %s, %s, 'pending')",
              (data['name'], data['phone'], data['address'], str(data['items']), data['total'], current_time))
    conn.commit()
    c.close()
    conn.close()
    return jsonify({"message": "Order Saved Successfully!"})

@app.route('/get-orders', methods=['GET'])
def get_orders():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, phone, address, items, total, date, status FROM orders ORDER BY id DESC")
    orders = c.fetchall()
    c.close()
    conn.close()
    return jsonify(orders)

@app.route('/update-order/<int:id>', methods=['POST'])
def update_order(id):
    new_status = request.json.get('status')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE orders SET status = %s WHERE id = %s", (new_status, id))
    conn.commit()
    c.close()
    conn.close()
    return jsonify({"message": "Status Updated!"})

@app.route('/download-csv')
def download_csv():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, phone, address, items, total, date, status FROM orders ORDER BY id DESC")
    orders = c.fetchall()
    c.close()
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
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, phone, address, items, total, date, status FROM orders WHERE id=%s", (order_id,))
    order = c.fetchone()
    c.close()
    conn.close()
    
    if not order: return "Order not found"
    
    name, phone, address, items_str, total, date = order[1], order[2], order[3], order[4], float(order[5]), order[6]
    items = json.loads(items_str.replace("'", '"'))
    
    subtotal = total
    service_charge = subtotal * 0.02
    gst = subtotal * 0.015
    final_total = subtotal + service_charge + gst
    
    items_html = "".join([f"<tr><td style='text-align:left;'>{i['name']}</td><td>{i['qty']}</td><td>{i['price']}</td><td>{int(i['qty'])*int(i['price'])}</td></tr>" for i in items])
    
    return f"""
    <html><head>
        <!-- html2canvas library jodi gayi hai taaki receipt ko image mein badla ja sake -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
        <style>
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
            .btn-container {{ display: flex; justify-content: center; gap: 10px; margin-top: 20px; }}
            .action-btn {{ background: #d4af37; border: none; padding: 10px 15px; cursor: pointer; font-weight: bold; font-size: 13px; border-radius: 4px; color: #000; }}
            @media print {{ .action-btn {{ display: none; }} }}
        </style>
    </head><body>
        <div class="receipt" id="receiptContent">
            <h1>GOLDEN SPOON</h1>
            <p style="margin:0; letter-spacing: 2px;">RESTAURANT</p>
            <p style="font-size: 12px; margin-bottom: 20px;">PREMIUM DINING EXPERIENCE</p>
            <div class="chef-box">
                <strong>Chef Sumit Singh</strong><br>Executive Chef
            </div>
            <div style="text-align:left; font-size: 13px;">
                Order ID: #{order_id}<br>Customer: {name}<br>Phone: {phone}<br>Date: {date}
            </div>
            <table><tr><th>ITEM</th><th>QTY</th><th>RATE</th><th>AMT</th></tr>{items_html}</table>
            <div class="totals">
                Subtotal: ₹{subtotal:.2f}<br>Service Charge (2%): ₹{service_charge:.2f}<br>GST (1.5%): ₹{gst:.2f}<br>
                <h3 style="color:#d4af37; font-size: 20px; margin: 10px 0;">TOTAL: ₹{final_total:.2f}</h3>
            </div>
            <div class="footer">
                Thank You! We hope to serve you again.<br>+91 9602697303<br>24, Food Street, Model Town, Hisar<br>https://golden-spoon-restaurant.onrender.com
            </div>
            <div class="btn-container">
                <button class="action-btn" onclick="window.print()">Print Receipt</button>
                <button class="action-btn" onclick="shareReceipt()">Send / Share</button>
            </div>
        </div>

        <script>
            async function shareReceipt() {{
                const receiptElement = document.getElementById('receiptContent');
                try {{
                    const canvas = await html2canvas(receiptElement, {{ scale: 2 }});
                    canvas.toBlob(async (blob) => {{
                        const file = new File([blob], "Receipt_{order_id}.png", {{ type: "image/png" }});
                        
                        if (navigator.canShare && navigator.canShare({{ files: [file] }})) {{
                            try {{
                                await navigator.share({{
                                    title: 'Golden Spoon Receipt #{order_id}',
                                    text: 'Here is your receipt from Golden Spoon Restaurant.',
                                    files: [file]
                                }});
                            }} catch (error) {{
                                console.log('Sharing error:', error);
                            }}
                        }} else {{
                            // Fallback agar direct file sharing support na ho
                            const link = document.createElement('a');
                            link.download = 'Receipt_{order_id}.png';
                            link.href = canvas.toDataURL('image/png');
                            link.click();
                            alert('Sharing files not supported directly on this browser, image downloaded instead!');
                        }}
                    }});
                }} catch (err) {{
                    console.error('Canvas error:', err);
                    alert('Failed to generate receipt image.');
                }}
            }}
        </script>
    </body></html>
    """

# --- NEW ADMIN FEATURES ROUTES ---

@app.route('/get-users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    c = conn.cursor()
    # Update: Users table se id, name, aur phone teeno fetch kiye ja rahe hain
    c.execute("SELECT id, name, phone FROM users ORDER BY id DESC")
    users = c.fetchall()
    c.close()
    conn.close()
    return jsonify(users)

@app.route('/get-menu', methods=['GET'])
def get_menu():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, price, image FROM menu")
    items = c.fetchall()
    c.close()
    conn.close()
    return jsonify(items)

@app.route('/add-menu-item', methods=['POST'])
def add_menu_item():
    name = request.form.get('name')
    price = request.form.get('price')
    
    file = request.files.get('image')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        image_url = f"{UPLOAD_FOLDER}/{filename}"
    else:
        image_url = "assets/default.jpg"
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO menu (name, price, image) VALUES (%s, %s, %s)", (name, price, image_url))
    conn.commit()
    c.close()
    conn.close()
    return jsonify({"success": True, "message": "Item added successfully!"})

@app.route('/delete-menu-item/<int:id>', methods=['POST'])
def delete_menu_item(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM menu WHERE id = %s", (id,))
    conn.commit()
    c.close()
    conn.close()
    return jsonify({"success": True, "message": "Item deleted successfully!"})

# --- ONLINE REVIEWS ROUTES ---
@app.route('/add-review', methods=['POST'])
def add_review():
    name = request.form.get('name')
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    
    file = request.files.get('image')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        image_url = f"{UPLOAD_FOLDER}/{filename}"
    else:
        image_url = "assets/default.jpg"

    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO reviews (name, rating, comment, image, date) VALUES (%s, %s, %s, %s, %s)",
              (name, rating, comment, image_url, current_time))
    conn.commit()
    c.close()
    conn.close()
    return jsonify({"success": True, "message": "Review submitted successfully!"})

@app.route('/get-reviews', methods=['GET'])
def get_reviews():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, rating, comment, image, date FROM reviews ORDER BY id DESC")
    reviews = c.fetchall()
    c.close()
    conn.close()
    return jsonify(reviews)

# --- FORGOT PASSWORD / RESET PASSWORD ROUTE ---
@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    phone = data.get('phone')
    new_password = data.get('newPassword')
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE phone=%s", (phone,))
    user = c.fetchone()
    
    if user:
        c.execute("UPDATE users SET password = %s WHERE phone = %s", (new_password, phone))
        conn.commit()
        c.close()
        conn.close()
        return jsonify({"success": True})
    else:
        c.close()
        conn.close()
        return jsonify({"success": False, "message": "Phone number not registered!"})

if __name__ == '__main__':
    app.run(debug=True)
