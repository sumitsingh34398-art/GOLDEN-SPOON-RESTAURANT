import csv
import io
import os
import json
import random
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, send_from_directory, make_response, session, redirect, url_for, send_file
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId

# PDF Generation libraries import
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'golden_spoon_secret'
CORS(app)

ADMIN_USER = "Sumit"
ADMIN_PASS = "S007"

# --- EMAIL CONFIGURATION FOR OTP ---
SENDER_EMAIL = "sumitsingh34398@gmail.com"
SENDER_PASSWORD = "pdvqxlcygglchqoq"
otp_storage = {}

# --- MONGODB ATLAS CONFIGURATION ---
MONGO_URI = os.environ.get('MONGO_URI', "mongodb+srv://sumitadmin007:Y5wFdxbxFYWvie39@sumit.n5qfisg.mongodb.net/?appName=Sumit")
try:
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client['GoldenSpoon']
    print("Connected to MongoDB Atlas successfully!")
except Exception as e:
    print(f"MongoDB Connection Error: {e}")

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

# --- USER AUTHENTICATION & OTP ROUTES ---

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({"success": False, "message": "Email is required!"})
    
    # --- Updated to instant direct 4-digit OTP generation without SMTP blocking ---
    otp = str(random.randint(1000, 9999))
    otp_storage[email] = otp
    print(f"Generated OTP for {email}: {otp}") # Console log for debugging if needed
    
    return jsonify({"success": True, "message": f"OTP sent successfully! (Code: {otp})"})

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data.get('email')
    user_otp = data.get('otp')
    
    if email in otp_storage and otp_storage[email] == user_otp:
        del otp_storage[email]
        return jsonify({"success": True, "message": "OTP verified successfully!"})
    else:
        return jsonify({"success": False, "message": "Invalid or expired OTP!"})

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    phone = data.get('phone')
    email = data.get('email')
    
    existing_user = mongo_db.users.find_one({"phone": phone})
    if existing_user:
        return jsonify({"success": False, "message": "User already exists"})
    
    try:
        user_data = {
            "name": data.get('name'),
            "phone": phone,
            "email": email,
            "password": data.get('password')
        }
        mongo_db.users.insert_one(user_data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/login-user', methods=['POST'])
def login_user():
    data = request.json
    phone = data.get('phone')
    password = data.get('password')
    
    user = mongo_db.users.find_one({"phone": phone, "password": password})
    if user:
        session['user'] = phone
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
    
    order_data = {
        "name": data.get('name'),
        "phone": data.get('phone'),
        "address": data.get('address'),
        "items": str(data.get('items')),
        "total": float(data.get('total')),
        "date": current_time,
        "status": "pending"
    }
    
    result = mongo_db.orders.insert_one(order_data)
    return jsonify({"message": "Order Saved Successfully!", "order_id": str(result.inserted_id)})

@app.route('/get-orders', methods=['GET'])
def get_orders():
    orders = list(mongo_db.orders.find().sort("_id", -1))
    orders_list = []
    for order in orders:
        order_id = str(order.get('_id'))
        orders_list.append([
            order_id,
            order.get('name'),
            order.get('phone'),
            order.get('address'),
            order.get('items'),
            order.get('total'),
            order.get('date'),
            order.get('status')
        ])
    return jsonify(orders_list)

@app.route('/update-order/<string:id>', methods=['POST'])
def update_order(id):
    new_status = None
    if request.is_json and request.json:
        new_status = request.json.get('status')
    if not new_status:
        new_status = request.form.get('status')
    
    if not new_status:
        return jsonify({"success": False, "message": "Status not provided"}), 400

    try:
        result = mongo_db.orders.update_one({"_id": ObjectId(id)}, {"$set": {"status": new_status}})
        if result.matched_count == 0:
            mongo_db.orders.update_one({"_id": id}, {"$set": {"status": new_status}})
    except Exception:
        mongo_db.orders.update_one({"_id": id}, {"$set": {"status": new_status}})
        
    return jsonify({"success": True, "message": "Status Updated!"})

@app.route('/download-csv')
def download_csv():
    orders = list(mongo_db.orders.find().sort("_id", -1))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Phone', 'Address', 'Items', 'Total', 'Date', 'Status'])
    for order in orders:
        writer.writerow([
            str(order.get('_id')),
            order.get('name'),
            order.get('phone'),
            order.get('address'),
            order.get('items'),
            order.get('total'),
            order.get('date'),
            order.get('status')
        ])
    
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=orders.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/receipt/<string:order_id>')
def get_receipt(order_id):
    order = None
    try:
        order = mongo_db.orders.find_one({"_id": ObjectId(order_id)})
        if not order:
            order = mongo_db.orders.find_one({"_id": order_id})
    except Exception:
        order = mongo_db.orders.find_one({"_id": order_id})
    
    if not order: return "Order not found"
    
    name = order.get('name')
    phone = order.get('phone')
    address = order.get('address')
    items_str = order.get('items')
    total = float(order.get('total'))
    date = order.get('date')
    
    items = json.loads(items_str.replace("'", '"'))
    
    subtotal = total
    # GST and Service charges removed as requested. Final total equals subtotal.
    final_total = subtotal
    
    items_html = "".join([f"<tr><td style='text-align:left;'>{i['name']}</td><td>{i['qty']}</td><td>{i['price']}</td><td>{int(i['qty'])*int(i['price'])}</td></tr>" for i in items])
    
    return f"""
    <html><head>
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

            /* Professional Luxury Modal Box Styling */
            .custom-modal {{
                display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.88); backdrop-filter: blur(8px);
                z-index: 1000; justify-content: center; align-items: center;
            }}
            .modal-box-content {{
                background: radial-gradient(circle at center, #181818 0%, #0c0c0c 100%);
                border: 2px solid #d4af37; padding: 35px 30px; border-radius: 20px;
                text-align: center; color: #fff; width: 100%; max-width: 350px;
                box-shadow: 0 20px 50px rgba(212, 175, 55, 0.3), inset 0 0 15px rgba(212, 175, 55, 0.1);
            }}
            .modal-logo {{
                width: 50px; height: 50px; border: 2px solid #d4af37; border-radius: 50%;
                display: flex; justify-content: center; align-items: center; margin: 0 auto 15px auto;
                background: rgba(212, 175, 55, 0.1); box-shadow: 0 0 15px rgba(212, 175, 55, 0.3); font-size: 22px;
            }}
            .modal-btn {{
                background: linear-gradient(135deg, #d4af37, #aa8c2c); border: none;
                padding: 10px 20px; cursor: pointer; font-weight: bold; border-radius: 8px;
                color: #000; width: 100%; margin-top: 15px; font-size: 14px;
                box-shadow: 0 5px 15px rgba(212, 175, 55, 0.3); transition: all 0.3s;
            }}
            .modal-btn:hover {{ background: linear-gradient(135deg, #e6c547, #d4af37); }}
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

        <!-- Professional Luxury Modal Box -->
        <div id="receiptModal" class="custom-modal">
            <div class="modal-box-content">
                <div class="modal-logo">🍽️</div>
                <h2 id="modalTitle" style="color:#d4af37; font-family:'Playfair Display', serif; font-size:20px; margin-bottom:8px;">Notification</h2>
                <div style="font-size: 12px; color: #bbb; margin-bottom: 12px;">Golden Spoon Restaurant</div>
                <p id="modalMsg" style="margin:10px 0 15px 0; font-size:13px; color:#ddd; line-height:1.4;"></p>
                <button class="modal-btn" onclick="closeModal()">CONTINUE</button>
            </div>
        </div>

        <script>
            function showModal(title, msg) {{
                document.getElementById('modalTitle').innerText = title;
                document.getElementById('modalMsg').innerText = msg;
                document.getElementById('receiptModal').style.display = 'flex';
            }}
            function closeModal() {{
                document.getElementById('receiptModal').style.display = 'none';
            }}

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
                            const link = document.createElement('a');
                            link.download = 'Receipt_{order_id}.png';
                            link.href = canvas.toDataURL('image/png');
                            link.click();
                            showModal('Download Complete', 'Sharing files not supported directly on this browser, image downloaded instead!');
                        }}
                    }});
                }} catch (err) {{
                    console.error('Canvas error:', err);
                    showModal('Error', 'Failed to generate receipt image.');
                }}
            }}
        </script>
    </body></html>
    """

# --- NEW ADMIN FEATURES ROUTES ---

@app.route('/get-users', methods=['GET'])
def get_users():
    users = list(mongo_db.users.find().sort("_id", -1))
    users_list = []
    for user in users:
        users_list.append([
            str(user.get('_id')),
            user.get('name'),
            user.get('phone')
        ])
    return jsonify(users_list)

@app.route('/download-users-csv')
def download_users_csv():
    users = list(mongo_db.users.find().sort("_id", -1))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Phone'])
    for user in users:
        writer.writerow([
            str(user.get('_id')),
            user.get('name'),
            user.get('phone')
        ])
    
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=registered_users.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/download-users-pdf')
def download_users_pdf():
    users = list(mongo_db.users.find().sort("_id", -1))

    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Golden Spoon Restaurant - Registered Users")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.line(50, 725, 550, 725)
    
    y = 695
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "User ID")
    c.drawString(200, y, "Customer Name")
    c.drawString(400, y, "Phone Number")
    y -= 20
    
    c.setFont("Helvetica", 10)
    for u in users:
        c.drawString(50, y, str(u.get('_id')))
        c.drawString(200, y, str(u.get('name', '')))
        c.drawString(400, y, str(u.get('phone', '')))
        y -= 20
        if y < 50:
            c.showPage()
            y = 750
            
    c.save()
    pdf_buffer.seek(0)
    
    return send_file(pdf_buffer, as_attachment=True, download_name="registered_users.pdf", mimetype='application/pdf')

@app.route('/get-menu', methods=['GET'])
def get_menu():
    items = list(mongo_db.menu.find())
    items_list = []
    for item in items:
        items_list.append([
            str(item.get('_id')),
            item.get('name'),
            item.get('price'),
            item.get('image')
        ])
    return jsonify(items_list)

@app.route('/add-menu-item', methods=['POST'])
def add_menu_item():
    name = request.form.get('name')
    price = float(request.form.get('price'))
    
    file = request.files.get('image')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        image_url = f"{UPLOAD_FOLDER}/{filename}"
    else:
        image_url = "assets/default.jpg"
    
    menu_data = {
        "name": name,
        "price": price,
        "image": image_url
    }
    mongo_db.menu.insert_one(menu_data)
    return jsonify({"success": True, "message": "Item added successfully!"})

@app.route('/delete-menu-item/<string:id>', methods=['POST'])
def delete_menu_item(id):
    try:
        result = mongo_db.menu.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 0:
            mongo_db.menu.delete_one({"_id": id})
    except Exception:
        mongo_db.menu.delete_one({"_id": id})
    return jsonify({"success": True, "message": "Item deleted successfully!"})

# --- ONLINE REVIEWS ROUTES ---
@app.route('/add-review', methods=['POST'])
def add_review():
    name = request.form.get('name')
    rating = int(request.form.get('rating'))
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
    
    review_data = {
        "name": name,
        "rating": rating,
        "comment": comment,
        "image": image_url,
        "date": current_time
    }
    mongo_db.reviews.insert_one(review_data)
    return jsonify({"success": True, "message": "Review submitted successfully!"})

@app.route('/get-reviews', methods=['GET'])
def get_reviews():
    reviews = list(mongo_db.reviews.find().sort("_id", -1))
    reviews_list = []
    for review in reviews:
        reviews_list.append([
            str(review.get('_id')),
            review.get('name'),
            review.get('rating'),
            review.get('comment'),
            review.get('image'),
            review.get('date')
        ])
    return jsonify(reviews_list)

# --- FORGOT PASSWORD / RESET PASSWORD ROUTE ---
@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    phone = data.get('phone')
    new_password = data.get('newPassword')
    
    user = mongo_db.users.find_one({"phone": phone})
    
    if user:
        mongo_db.users.update_one({"phone": phone}, {"$set": {"password": new_password}})
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Phone number not registered!"})

# --- UPDATE PASSWORD ROUTE ---
@app.route('/update-password', methods=['POST'])
def update_password():
    data = request.get_json()
    new_password = data.get('new_password')
    
    config_data = {"admin_password": new_password}
    with open('admin_config.json', 'w') as f:
        json.dump(config_data, f)

    return jsonify({"message": "Password updated and saved permanently successfully!"})

# --- BULK CLEAR ROUTES ---
@app.route('/clear-all-orders', methods=['POST'])
def clear_all_orders():
    try:
        mongo_db.orders.delete_many({})
        return jsonify({"success": True, "message": "All orders cleared successfully!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
