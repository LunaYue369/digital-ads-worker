#!/usr/bin/env python3
"""
Mock POS data generator — Seafood Restaurant (海鲜餐厅)
Generates 3 months of realistic transaction data (Dec 2025 – Feb 2026).

Usage:
    python tools/biz/biz_seed_data.py
    python tools/biz/biz_seed_data.py --industry seafood_restaurant --reset
"""
import argparse
import random
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from biz_db import get_conn, init_schema

# ── Menu catalog ───────────────────────────────────────────────────────────────
CATALOG = [
    # id, name, category, price, cost
    ("king_crab",      "King Crab (1.2 lb)",        "Seafood",  128.00, 54.00),
    ("lobster",        "Boston Lobster",             "Seafood",   88.00, 36.00),
    ("oyster_platter", "Oyster Platter (6 pcs)",     "Seafood",   48.00, 18.00),
    ("seafood_combo",  "Seafood Combo Platter (4p)", "Seafood",  388.00,145.00),
    ("steamed_fish",   "Steamed Sea Bass",           "Seafood",   68.00, 25.00),
    ("shrimp_stirfry", "Garlic Stir-fry Shrimp",    "Seafood",   38.00, 12.00),
    ("clam_black_bean","Black Bean Clams",           "Seafood",   28.00,  9.00),
    ("scallop",        "Scallop & Seasonal Veg",     "Seafood",   58.00, 22.00),
    ("fried_rice",     "Yangzhou Fried Rice",        "Staple",    16.00,  4.00),
    ("noodle",         "Noodle Soup",                "Staple",    18.00,  5.00),
    ("white_rice",     "Steamed Rice",               "Staple",     3.00,  0.50),
    ("tea",            "Jasmine Tea (pot)",           "Drinks",    8.00,  1.00),
    ("soft_drink",     "Soft Drink",                 "Drinks",    4.00,  0.80),
]

CATALOG_DICT = {c[0]: c for c in CATALOG}

# Item weights (Pareto: top seafood drives ~70% revenue)
# Weight = probability of being ordered per table
ITEM_WEIGHTS = {
    "king_crab":       0.30,
    "lobster":         0.40,
    "oyster_platter":  0.45,
    "seafood_combo":   0.08,
    "steamed_fish":    0.35,
    "shrimp_stirfry":  0.50,
    "clam_black_bean": 0.40,
    "scallop":         0.25,
    "fried_rice":      0.55,
    "noodle":          0.30,
    "white_rice":      0.70,
    "tea":             0.65,
    "soft_drink":      0.40,
}

EMPLOYEES = ["emp_wang", "emp_li", "emp_zhang", "emp_chen", "emp_liu"]

# ── Demand model ───────────────────────────────────────────────────────────────
def daily_table_count(d: date) -> int:
    """Simulate realistic table counts based on day-of-week + holidays."""
    dow = d.weekday()  # 0=Mon, 6=Sun

    base = {0: 18, 1: 15, 2: 17, 3: 20, 4: 35, 5: 52, 6: 38}[dow]

    # Holiday multipliers
    holidays = {
        date(2025, 12, 24): 1.6,  # Christmas Eve
        date(2025, 12, 25): 1.7,  # Christmas
        date(2025, 12, 31): 1.8,  # New Year's Eve
        date(2026,  1,  1): 1.9,  # New Year's Day
        date(2026,  1, 16): 1.3,  # MLK Day
        date(2026,  1, 29): 2.2,  # Chinese New Year (Spring Festival)
        date(2026,  1, 30): 2.0,
        date(2026,  1, 31): 1.8,
        date(2026,  2,  1): 1.5,
        date(2026,  2, 14): 1.6,  # Valentine's Day
    }
    mult = holidays.get(d, 1.0)

    # Random weather / noise ±20%
    noise = random.uniform(0.82, 1.18)
    return max(5, int(base * mult * noise))


def service_timestamps(d: date, n_tables: int):
    """Generate timestamps spread across lunch + dinner service."""
    slots = []
    # Lunch  11:30–13:45 (~30% of tables)
    lunch_n = int(n_tables * random.uniform(0.25, 0.35))
    for _ in range(lunch_n):
        h = random.randint(11, 13)
        m = random.randint(0 if h > 11 else 30, 59)
        slots.append(datetime(d.year, d.month, d.day, h, m,
                               random.randint(0, 59)))
    # Dinner 17:00–21:15 (~70%)
    dinner_n = n_tables - lunch_n
    for _ in range(dinner_n):
        h = random.choices([17, 18, 19, 20, 21],
                           weights=[8, 22, 30, 25, 15])[0]
        m = random.randint(0, 59 if h < 21 else 15)
        slots.append(datetime(d.year, d.month, d.day, h, m,
                               random.randint(0, 59)))
    return slots


def build_transaction(ts: datetime, industry: str):
    """Build one transaction dict + its line items."""
    txn_id = "txn_" + uuid.uuid4().hex[:12]
    covers = random.choices([1, 2, 3, 4, 5, 6],
                             weights=[5, 25, 20, 30, 12, 8])[0]
    table_no = f"{random.choice('ABCDE')}{random.randint(1,10)}"
    employee = random.choice(EMPLOYEES)
    is_dinner = ts.hour >= 17
    order_type = random.choices(
        ["dine_in", "takeout", "delivery"],
        weights=[80, 12, 8])[0]

    # Build line items — dinner tables order more / pricier seafood
    items = []
    for item_id, weight in ITEM_WEIGHTS.items():
        if industry == "seafood_restaurant":
            # Dinner boost for seafood
            if is_dinner and CATALOG_DICT[item_id][2] == "Seafood":
                weight = min(weight * 1.4, 0.9)
        if random.random() < weight:
            qty = 1
            if CATALOG_DICT[item_id][2] in ("Drinks", "Staple") or item_id == "white_rice":
                qty = random.randint(1, max(1, covers - 1))
            _, name, category, price, cost = CATALOG_DICT[item_id]
            items.append({
                "id": "li_" + uuid.uuid4().hex[:12],
                "transaction_id": txn_id,
                "item_id": item_id,
                "item_name": name,
                "category": category,
                "qty": qty,
                "unit_price": price,
                "unit_cost": cost,
                "total_price": round(price * qty, 2),
                "total_cost": round(cost * qty, 2),
            })

    # Ensure at least one item
    if not items:
        _, name, category, price, cost = CATALOG_DICT["shrimp_stirfry"]
        items.append({
            "id": "li_" + uuid.uuid4().hex[:12],
            "transaction_id": txn_id,
            "item_id": "shrimp_stirfry",
            "item_name": name,
            "category": category,
            "qty": 1,
            "unit_price": price,
            "unit_cost": cost,
            "total_price": price,
            "total_cost": cost,
        })

    subtotal = round(sum(i["total_price"] for i in items), 2)
    discount = 0.0
    # Occasional 10% loyalty discount
    if random.random() < 0.08:
        discount = round(subtotal * 0.10, 2)
    net = round(subtotal - discount, 2)
    tax = round(net * 0.095, 2)          # ~9.5% SoCal sales tax
    tip = round(net * random.uniform(0.15, 0.22), 2) if order_type == "dine_in" else 0.0
    total = round(net + tax + tip, 2)

    payment = random.choices(
        ["credit_visa", "credit_mc", "credit_amex", "cash", "apple_pay"],
        weights=[35, 25, 15, 15, 10])[0]

    txn = {
        "id": txn_id,
        "created_at": ts.isoformat(),
        "date": ts.date().isoformat(),
        "hour": ts.hour,
        "day_of_week": ts.weekday(),
        "table_no": table_no if order_type == "dine_in" else None,
        "covers": covers,
        "employee_id": employee,
        "order_type": order_type,
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "tip": tip,
        "total": total,
        "payment_method": payment,
        "void": 1 if random.random() < 0.012 else 0,
    }
    return txn, items


# ── Main ──────────────────────────────────────────────────────────────────────
def seed(industry: str, start: date, end: date, reset: bool = False):
    init_schema(industry)
    conn = get_conn(industry)

    if reset:
        conn.executescript(
            "DELETE FROM line_items; DELETE FROM transactions; DELETE FROM catalog;")
        conn.commit()
        print("♻️  Cleared existing data")

    # Insert catalog
    existing = conn.execute("SELECT COUNT(*) FROM catalog").fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO catalog VALUES (?,?,?,?,?,1)", CATALOG)
        conn.commit()
        print(f"📋 Inserted {len(CATALOG)} menu items")

    # Generate transactions day by day
    total_txns = 0
    total_items = 0
    d = start
    while d <= end:
        n = daily_table_count(d)
        timestamps = service_timestamps(d, n)
        for ts in timestamps:
            txn, items = build_transaction(ts, industry)
            conn.execute("""
                INSERT OR IGNORE INTO transactions
                VALUES (:id,:created_at,:date,:hour,:day_of_week,:table_no,
                        :covers,:employee_id,:order_type,:subtotal,:discount,
                        :tax,:tip,:total,:payment_method,:void)""", txn)
            conn.executemany("""
                INSERT OR IGNORE INTO line_items
                VALUES (:id,:transaction_id,:item_id,:item_name,:category,
                        :qty,:unit_price,:unit_cost,:total_price,:total_cost)
                """, items)
            total_txns += 1
            total_items += len(items)
        d += timedelta(days=1)

    conn.commit()
    conn.close()

    days = (end - start).days + 1
    print(f"✅ Seeded {industry}")
    print(f"   Period : {start} → {end} ({days} days)")
    print(f"   Orders : {total_txns:,}")
    print(f"   Items  : {total_items:,}")
    print(f"   DB     : data/pos/{industry}.db")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed mock POS data")
    parser.add_argument("--industry", default="seafood_restaurant")
    parser.add_argument("--start", default="2025-12-01")
    parser.add_argument("--end", default="2026-02-28")
    parser.add_argument("--reset", action="store_true",
                        help="Clear existing data before seeding")
    args = parser.parse_args()

    seed(
        industry=args.industry,
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        reset=args.reset,
    )
