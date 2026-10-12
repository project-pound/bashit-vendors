import json
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "vendors.db"
DB_PATH.parent.mkdir(exist_ok=True, parents=True)
OPERATIONS_DB = Path("C:/Users/anujq/OneDrive/Documents/project_pound/bashit_operations/data/operations.db")

app = Flask(__name__)
app.secret_key = "bashit-vendors-secret"

VENDOR_USERS = {
    "cakevendor": {"password": "vendor123", "name": "Cake Studio", "vendor_type": "cake"},
    "foodvendor": {"password": "vendor123", "name": "Catering Hub", "vendor_type": "food"},
    "decorvendor": {"password": "vendor123", "name": "Decor House", "vendor_type": "decoration"},
}


def get_db_connection(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vendor_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                name TEXT,
                vendor_type TEXT
            )
            """
        )
        for username, data in VENDOR_USERS.items():
            conn.execute(
                "INSERT OR IGNORE INTO vendor_users (username, password, name, vendor_type) VALUES (?, ?, ?, ?)",
                (username, data["password"], data["name"], data["vendor_type"]),
            )


def fetch_orders_for_vendor(vendor_name=None):
    if not OPERATIONS_DB.exists():
        return [], []
    conn = sqlite3.connect(OPERATIONS_DB)
    conn.row_factory = sqlite3.Row
    orders = conn.execute(
        "SELECT * FROM vendor_orders ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    current = []
    past = []
    for order in orders:
        if vendor_name and order["vendor_name"] != vendor_name:
            continue
        item = {
            "id": order["id"],
            "lead_id": order["lead_id"],
            "category": order["category"],
            "vendor_name": order["vendor_name"],
            "vendor_phone": order["vendor_phone"],
            "status": order["status"],
            "created_at": order["created_at"],
            "updated_at": order["updated_at"],
            "order_details": json.loads(order["order_details"]) if order["order_details"] else {},
        }
        if item["status"] in {"pending", "accepted", "in_progress"}:
            current.append(item)
        else:
            past.append(item)
    return current, past


def render_login(message=""):
    return render_template_string(
        '''
        <html><head><title>BashIt Vendor Login</title>
        <style>body{font-family:Arial,sans-serif;background:#f4f6fb;display:flex;justify-content:center;align-items:center;height:100vh;} .card{background:white;padding:30px;border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,0.08);width:360px;} input{width:100%;padding:12px;margin:8px 0;border:1px solid #dbe2ef;border-radius:10px;} button{width:100%;padding:12px;border:none;background:#0f766e;color:white;border-radius:10px;font-weight:bold;} .msg{color:#b91c1c;margin-bottom:14px;}</style></head><body>
        <div class="card">
            <h2>BashIt Vendor Login</h2>
            {% if message %}<div class="msg">{{ message }}</div>{% endif %}
            <form method="post">
                <input name="username" placeholder="Username" required>
                <input name="password" type="password" placeholder="Password" required>
                <button type="submit">Login</button>
            </form>
        </div>
        </body></html>
        ''',
        message=message,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = VENDOR_USERS.get(username)
        if user and user["password"] == password:
            session["vendor"] = username
            session["vendor_name"] = user["name"]
            return redirect(url_for("dashboard"))
        return render_login("Invalid username or password.")
    return render_login()


@app.route("/logout")
def logout():
    session.pop("vendor", None)
    session.pop("vendor_name", None)
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    if "vendor" not in session:
        return redirect(url_for("login"))
    vendor_name = session["vendor_name"]
    current, past = fetch_orders_for_vendor(vendor_name)
    return render_template_string(
        '''
        <html><head><title>BashIt Vendor Dashboard</title>
        <style>body{font-family:Arial,sans-serif;background:#f5f7fb;margin:0;padding:24px;} .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;} .box{background:white;padding:18px;border-radius:12px;box-shadow:0 8px 28px rgba(0,0,0,0.04);margin-bottom:18px;} table{border-collapse:collapse;width:100%;} th,td{border-bottom:1px solid #e7ebf3;padding:10px;text-align:left;} a.button{display:inline-block;padding:10px 16px;background:#0f766e;color:white;border-radius:10px;text-decoration:none;} .status{font-weight:bold;} </style></head><body>
        <div class="top">
            <h1>{{ vendor_name }}</h1>
            <a class="button" href="/logout">Logout</a>
        </div>
        <div class="box">
            <h2>Current Orders</h2>
            <table>
                <tr><th>Lead</th><th>Category</th><th>Status</th><th>Order Details</th><th>Action</th></tr>
                {% for item in current %}
                <tr><td>{{ item['lead_id'] }}</td><td>{{ item['category'] }}</td><td class="status">{{ item['status'] }}</td><td>{{ item['order_details'].get('event_type', 'N/A') }} • {{ item['order_details'].get('event_date', 'N/A') }}</td><td><a href="/update/{{ item['id'] }}">Update</a></td></tr>
                {% endfor %}
            </table>
        </div>
        <div class="box">
            <h2>Past Orders & Payouts</h2>
            <table>
                <tr><th>Lead</th><th>Category</th><th>Status</th><th>Net Payout</th></tr>
                {% for item in past %}
                <tr><td>{{ item['lead_id'] }}</td><td>{{ item['category'] }}</td><td>{{ item['status'] }}</td><td>₹ 36,000</td></tr>
                {% endfor %}
            </table>
        </div>
        </body></html>
        ''',
        vendor_name=vendor_name,
        current=current,
        past=past,
    )


@app.route("/update/<int:order_id>", methods=["GET", "POST"])
def update_order(order_id):
    if "vendor" not in session:
        return redirect(url_for("login"))
    conn = sqlite3.connect(OPERATIONS_DB)
    conn.row_factory = sqlite3.Row
    order = conn.execute("SELECT * FROM vendor_orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    if not order:
        return "Order not found", 404
    if request.method == "POST":
        new_status = request.form.get("status", "pending")
        conn = sqlite3.connect(OPERATIONS_DB)
        conn.execute(
            "UPDATE vendor_orders SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, datetime.utcnow().isoformat(), order_id),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))
    return render_template_string(
        '''
        <html><head><title>Update Order</title>
        <style>body{font-family:Arial,sans-serif;background:#f5f7fb;padding:30px;} .card{background:white;padding:20px;border-radius:14px;box-shadow:0 8px 28px rgba(0,0,0,0.04);max-width:500px;} select,input,button{width:100%;padding:12px;border-radius:10px;border:1px solid #dfe7f3;margin:8px 0;} button{background:#0f766e;color:white;border:none;font-weight:bold;} </style></head><body>
        <div class="card">
            <h2>Update Order #{{ order_id }}</h2>
            <form method="post">
                <select name="status">
                    <option value="accepted">Accepted</option>
                    <option value="in_progress">In Progress</option>
                    <option value="completed">Completed</option>
                    <option value="delayed">Delayed</option>
                    <option value="cancelled">Cancelled</option>
                </select>
                <button type="submit">Save Status</button>
            </form>
        </div>
        </body></html>
        ''',
        order_id=order_id,
    )


ensure_tables()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003, debug=True)
