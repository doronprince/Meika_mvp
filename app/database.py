import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "meika.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Expenses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        amount_krw REAL NOT NULL,
        store_name TEXT,
        transit_cost_krw REAL DEFAULT 0,
        date TEXT NOT NULL,
        notes TEXT
    )
    """)

    # Products Catalog Table (Seoul Student Retailers)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        store_name TEXT NOT NULL,
        store_type TEXT NOT NULL, -- 'Online', 'Local Supermarket', 'Traditional Market', 'Convenience Store'
        price_krw REAL NOT NULL,
        transit_cost_krw REAL DEFAULT 0,
        transit_mode TEXT DEFAULT 'Walk', -- 'Walk', 'Subway/Bus', 'Taxi'
        location TEXT NOT NULL,
        in_stock INTEGER DEFAULT 1,
        rating REAL DEFAULT 4.5,
        price_trend TEXT DEFAULT 'Stable' -- 'Rising', 'Falling', 'Stable'
    )
    """)

    # Copilot Chat Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        sender TEXT NOT NULL, -- 'user' or 'meika'
        message TEXT NOT NULL,
        xai_factors_json TEXT
    )
    """)

    conn.commit()

    # Seed data if catalog is empty
    cursor.execute("SELECT COUNT(*) FROM products_catalog")
    if cursor.fetchone()[0] == 0:
        seed_data = [
            ("10kg Shin Ramyun Rice / Grain", "Groceries", "Emart Everyday (Wolgye)", "Local Supermarket", 32000, 1500, "Subway/Bus", "Wolgye, Seoul", 1, 4.8, "Falling"),
            ("10kg Shin Ramyun Rice / Grain", "Groceries", "Coupang Wow", "Online", 29800, 0, "Walk", "Delivery (Seoul)", 1, 4.9, "Stable"),
            ("10kg Shin Ramyun Rice / Grain", "Groceries", "Gyeongdong Traditional Market", "Traditional Market", 27000, 2800, "Subway/Bus", "Jegi-dong, Seoul", 1, 4.6, "Falling"),
            
            ("Seoul Milk 1L", "Groceries", "GS25 Convenience Store", "Convenience Store", 3200, 0, "Walk", "Near Kwangwoon Univ", 1, 4.7, "Stable"),
            ("Seoul Milk 1L", "Groceries", "Emart Everyday (Wolgye)", "Local Supermarket", 2850, 1500, "Subway/Bus", "Wolgye, Seoul", 1, 4.8, "Stable"),
            ("Seoul Milk 1L", "Groceries", "Coupang Fresh (2-pack)", "Online", 5400, 0, "Walk", "Delivery (Seoul)", 1, 4.9, "Stable"),

            ("Shin Ramyun 20-Pack Box", "Groceries", "Coupang", "Online", 15800, 0, "Walk", "Delivery (Seoul)", 1, 4.9, "Stable"),
            ("Shin Ramyun 20-Pack Box", "Groceries", "Daiso Wolgye", "Local Supermarket", 16500, 0, "Walk", "Wolgye, Seoul", 1, 4.5, "Stable"),
            
            ("Anker Wireless Earbuds", "Electronics", "Coupang", "Online", 45000, 0, "Walk", "Delivery (Seoul)", 1, 4.8, "Falling"),
            ("Anker Wireless Earbuds", "Electronics", "Electromart Yongsan", "Local Supermarket", 49000, 3000, "Subway/Bus", "Yongsan, Seoul", 1, 4.7, "Stable"),

            ("Winter Puffer Jacket", "Apparel", "SPAO Wolgye", "Local Supermarket", 79000, 1500, "Subway/Bus", "Wolgye, Seoul", 1, 4.6, "Falling"),
            ("Winter Puffer Jacket", "Apparel", "Musinsa Online", "Online", 69000, 0, "Walk", "Delivery (Seoul)", 1, 4.8, "Stable"),
            ("Winter Puffer Jacket", "Apparel", "Dongdaemun Market", "Traditional Market", 55000, 3000, "Subway/Bus", "Dongdaemun, Seoul", 1, 4.4, "Stable"),

            ("Large Iced Americano", "Cafes", "Mega Coffee (Kwangwoon)", "Convenience Store", 2000, 0, "Walk", "Kwangwoon Univ Street", 1, 4.9, "Stable"),
            ("Large Iced Americano", "Cafes", "Starbucks (Kwangwoon)", "Convenience Store", 4500, 0, "Walk", "Kwangwoon Univ Street", 1, 4.7, "Stable"),
        ]
        cursor.executemany("""
        INSERT INTO products_catalog (product_name, category, store_name, store_type, price_krw, transit_cost_krw, transit_mode, location, in_stock, rating, price_trend)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, seed_data)

    # Seed sample expenses if empty
    cursor.execute("SELECT COUNT(*) FROM expenses")
    if cursor.fetchone()[0] == 0:
        today = datetime.now()
        sample_expenses = [
            ("Weekly Grocery Run", "Groceries", 42000, "Emart Everyday", 1500, (today - timedelta(days=1)).strftime("%Y-%m-%d"), "Rice, Milk, Eggs"),
            ("Iced Americano & Study", "Cafes & Dining", 4500, "Starbucks Kwangwoon", 0, (today - timedelta(days=2)).strftime("%Y-%m-%d"), "Study session"),
            ("Subway Monthly Pass Top-up", "Transportation", 55000, "Seoul Metro", 0, (today - timedelta(days=3)).strftime("%Y-%m-%d"), "Commute pass"),
            ("Daiso Room Supplies", "Housing & Utilities", 12500, "Daiso Wolgye", 0, (today - timedelta(days=5)).strftime("%Y-%m-%d"), "Storage boxes"),
            ("Student Cafeteria Lunch", "Cafes & Dining", 5000, "Kwangwoon Cafeteria", 0, (today - timedelta(days=6)).strftime("%Y-%m-%d"), "Kimchi stew"),
            ("Korean Textbooks", "Education", 35000, "Kyobo Bookstore", 3000, (today - timedelta(days=8)).strftime("%Y-%m-%d"), "AI & ML course materials"),
            ("Mobile Plan Bill", "Housing & Utilities", 33000, "KT Telecom", 0, (today - timedelta(days=10)).strftime("%Y-%m-%d"), "Student tier"),
        ]
        cursor.executemany("""
        INSERT INTO expenses (title, category, amount_krw, store_name, transit_cost_krw, date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, sample_expenses)

    conn.commit()
    conn.close()
