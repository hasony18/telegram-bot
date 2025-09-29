# main.py
import os
import sqlite3
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime

# ===== إعداد المتغيرات =====
TOKEN = "8209179220:AAEPi4Zx9lBWIkg992nq-j41A-HOZJGCv1w"   # ✅ توكنك
ADMIN_ID = 7641885800
WEBHOOK_URL = "https://Python.the9016.repl.co"

bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

# ===== قاعدة البيانات =====
DB_PATH = "shop.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL DEFAULT 0,
        stock INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        discount REAL DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        province TEXT,
        address TEXT,
        phone TEXT,
        status TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_product(name, price, stock=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO products (name, price, stock, created_at) VALUES (?, ?, ?, ?)",
        (name, price, stock, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

def list_products():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, price, stock FROM products")
    rows = c.fetchall()
    conn.close()
    return rows

def add_coupon(code, discount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO coupons (code, discount) VALUES (?, ?)", (code, discount))
    conn.commit()
    conn.close()

def list_orders():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, user_id, product_id, province, address, phone, status FROM orders ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return rows

def update_order_status(order_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()

# ===== أوامر البوت =====
@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        "🎉 أهلاً وسهلاً بك في متجرنا الموثوق!\n\n"
        "🛒 هنا تجد أفضل المنتجات بجودة عالية وأسعار مناسبة.\n"
        "✅ ثقة وأمان في كل عملية شراء.\n\n"
        "استخدم /products لعرض منتجاتنا."
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['products'])
def show_products(message):
    products = list_products()
    if not products:
        bot.reply_to(message, "🚫 ماكو منتجات مضافة بعد.")
        return

    markup = types.InlineKeyboardMarkup()
    for pid, name, price, stock in products:
        btn = types.InlineKeyboardButton(
            text=f"{name} - {price}$ ({stock} بالمخزن)",
            callback_data=f"buy_{pid}"
        )
        markup.add(btn)

    bot.send_message(message.chat.id, "اختر منتج للشراء:", reply_markup=markup)

# ====== الشراء ======
user_state = {}

PROVINCES = [
    "بغداد", "البصرة", "نينوى", "أربيل", "دهوك", "السليمانية", "النجف",
    "كربلاء", "بابل", "ديالى", "الأنبار", "المثنى", "ذي قار",
    "واسط", "ميسان", "كركوك", "صلاح الدين", "القادسية"
]

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    pid = int(call.data.split("_")[1])
    user_state[call.message.chat.id] = {"step": "province", "product_id": pid}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for prov in PROVINCES:
        markup.add(prov)

    bot.send_message(call.message.chat.id, "📍 اختر محافظتك:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("step") == "province")
def ask_address(message):
    user_state[message.chat.id]["province"] = message.text
    user_state[message.chat.id]["step"] = "address"
    bot.send_message(message.chat.id, "🏠 ضف عنوانك الكامل:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("step") == "address")
def ask_phone(message):
    user_state[message.chat.id]["address"] = message.text
    user_state[message.chat.id]["step"] = "phone"
    bot.send_message(message.chat.id, "📞 ضف رقم هاتفك:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("step") == "phone")
def finish_order(message):
    state = user_state[message.chat.id]
    state["phone"] = message.text
    state["step"] = "done"

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO orders (user_id, product_id, province, address, phone, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (message.chat.id, state["product_id"], state["province"], state["address"], state["phone"], "تم الاستلام", datetime.utcnow().isoformat())
    )
    order_id = c.lastrowid
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, "✅ تم تجهيز طلبك بنجاح!\n📦 جاري شحن طلبك 🚚")

    bot.send_message(
        ADMIN_ID,
        f"📦 طلب جديد #{order_id}:\n"
        f"الزبون: {message.chat.first_name}\n"
        f"المحافظة: {state['province']}\n"
        f"العنوان: {state['address']}\n"
        f"الهاتف: {state['phone']}"
    )

# ====== أوامر الأدمن ======
@bot.message_handler(commands=['addproduct'])
def admin_add_product(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, name, price, stock = message.text.split(" ", 3)
        add_product(name, float(price), int(stock))
        bot.reply_to(message, f"✅ تمت إضافة المنتج: {name}")
    except:
        bot.reply_to(message, "❌ الصيغة: /addproduct اسم السعر الكمية")

@bot.message_handler(commands=['addcoupon'])
def admin_add_coupon(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, code, discount = message.text.split(" ", 2)
        add_coupon(code, float(discount))
        bot.reply_to(message, f"✅ تمت إضافة الكوبون: {code}")
    except:
        bot.reply_to(message, "❌ الصيغة: /addcoupon الكود نسبة_الخصم")

@bot.message_handler(commands=['orders'])
def admin_list_orders(message):
    if message.chat.id != ADMIN_ID:
        return
    orders = list_orders()
    if not orders:
        bot.reply_to(message, "🚫 لا توجد طلبات.")
        return

    for oid, uid, pid, prov, addr, phone, status in orders:
        text = (
            f"📦 طلب #{oid}\n"
            f"👤 زبون: {uid}\n"
            f"🛒 منتج ID: {pid}\n"
            f"📍 محافظة: {prov}\n"
            f"🏠 عنوان: {addr}\n"
            f"📞 هاتف: {phone}\n"
            f"📌 الحالة: {status}"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚚 قيد الشحن", callback_data=f"status_{oid}_قيد الشحن"))
        markup.add(types.InlineKeyboardButton("✅ تم التوصيل", callback_data=f"status_{oid}_تم التوصيل"))
        bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("status_"))
def change_order_status(call):
    _, oid, new_status = call.data.split("_", 2)
    oid = int(oid)
    update_order_status(oid, new_status)

    bot.answer_callback_query(call.id, f"✅ تم تغيير الحالة إلى {new_status}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM orders WHERE id=?", (oid,))
    row = c.fetchone()
    conn.close()
    if row:
        user_id = row[0]
        bot.send_message(user_id, f"📌 تحديث حالة طلبك #{oid}: {new_status}")

# ====== Webhook ======
@server.route("/" + TOKEN, methods=["POST"])
def webhook_receive():
    json_str = request.stream.read().decode("utf-8")
    update = types.Update.de_json(json_str)
    if update is not None:   # ✅ يمنع الخطأ
        bot.process_new_updates([update])
    return "OK", 200
@server.route("/")
def home():
    return "Bot is running 🚀", 200
def set_webhook():
    bot.remove_webhook()
    url = WEBHOOK_URL.rstrip("/") + "/" + TOKEN
    bot.set_webhook(url=url)

# ===== تشغيل البرنامج =====
if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8080)