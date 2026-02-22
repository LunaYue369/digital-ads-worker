#!/usr/bin/env python3
"""
Mock POS data generator — SoCal Massage & Spa
Generates 3 months of realistic appointment data (Dec 2025 – Feb 2026).

Usage:
    python tools/biz/biz_seed_massage_spa.py
    python tools/biz/biz_seed_massage_spa.py --reset
"""
import argparse
import random
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from biz_db import get_conn, init_schema

INDUSTRY = "massage_spa"

CATALOG = [
    ("swedish_60",     "Swedish Massage (60 min)",       "Massage",     80.00, 22.00),
    ("deep_tissue_60", "Deep Tissue (60 min)",           "Massage",    100.00, 28.00),
    ("hot_stone_90",   "Hot Stone (90 min)",             "Massage",    130.00, 35.00),
    ("foot_reflex",    "Foot Reflexology (45 min)",      "Reflexology", 60.00, 16.00),
    ("couples_90",     "Couples Massage (90 min)",       "Couples",    160.00, 44.00),
    ("facial_60",      "Classic Facial (60 min)",        "Facial",      90.00, 25.00),
    ("body_scrub",     "Body Scrub & Wrap",              "Body",       110.00, 30.00),
    ("neck_30",        "Neck & Shoulder (30 min)",       "Massage",     45.00, 12.00),
    ("aromatherapy",   "Aromatherapy Upgrade",           "Add-on",      20.00,  5.00),
    ("hot_towel",      "Hot Towel Upgrade",              "Add-on",      10.00,  2.00),
]

CATALOG_DICT = {c[0]: c for c in CATALOG}

PRIMARY_SERVICES = ["swedish_60", "deep_tissue_60", "hot_stone_90",
                    "foot_reflex", "couples_90", "facial_60", "body_scrub", "neck_30"]
PRIMARY_WEIGHTS  = [0.28, 0.23, 0.12, 0.14, 0.06, 0.08, 0.05, 0.04]

EMPLOYEES = ["therapist_amy", "therapist_jay", "therapist_mia",
             "therapist_tom", "therapist_sue"]


def daily_count(d: date) -> int:
    dow = d.weekday()
    base = {0: 12, 1: 10, 2: 11, 3: 13, 4: 16, 5: 22, 6: 20}[dow]
    holidays = {
        date(2025, 12, 24): 1.3,
        date(2025, 12, 25): 0.3,
        date(2025, 12, 31): 1.3,
        date(2026,  1,  1): 0.5,
        date(2026,  1, 16): 1.2,
        date(2026,  2, 14): 2.0,   # Valentine's Day — biggest day for spas
        date(2026,  2, 13): 1.6,   # Friday before
        date(2026,  2, 15): 1.4,   # Sunday after
    }
    return max(3, int(base * holidays.get(d, 1.0) * random.uniform(0.85, 1.15)))


def service_timestamps(d: date, n: int):
    slots = []
    lunch_n = int(n * random.uniform(0.25, 0.35))
    for _ in range(lunch_n):
        h = random.randint(11, 13)
        slots.append(datetime(d.year, d.month, d.day, h,
                              random.randint(0, 59), random.randint(0, 59)))
    eve_n = int(n * random.uniform(0.45, 0.55))
    for _ in range(eve_n):
        h = random.choices([16, 17, 18, 19, 20], weights=[10, 25, 30, 25, 10])[0]
        slots.append(datetime(d.year, d.month, d.day, h,
                              random.randint(0, 59), random.randint(0, 59)))
    for _ in range(n - lunch_n - eve_n):
        h = random.randint(10, 15)
        slots.append(datetime(d.year, d.month, d.day, h,
                              random.randint(0, 59), random.randint(0, 59)))
    return slots


def build_transaction(ts: datetime, industry: str):
    txn_id = "txn_" + uuid.uuid4().hex[:12]

    primary_id = random.choices(PRIMARY_SERVICES, weights=PRIMARY_WEIGHTS)[0]
    is_couples = primary_id == "couples_90"
    covers = 2 if is_couples else random.choices([1, 2], weights=[88, 12])[0]

    _, pname, pcat, pprice, pcost = CATALOG_DICT[primary_id]
    items = [{
        "id": "li_" + uuid.uuid4().hex[:12],
        "transaction_id": txn_id,
        "item_id": primary_id, "item_name": pname, "category": pcat,
        "qty": 1, "unit_price": pprice, "unit_cost": pcost,
        "total_price": pprice, "total_cost": pcost,
    }]

    # Add-ons
    for addon_id, prob in [("aromatherapy", 0.38), ("hot_towel", 0.28)]:
        if random.random() < prob:
            _, n2, c2, p2, co2 = CATALOG_DICT[addon_id]
            qty = covers if is_couples else 1
            items.append({
                "id": "li_" + uuid.uuid4().hex[:12],
                "transaction_id": txn_id,
                "item_id": addon_id, "item_name": n2, "category": c2,
                "qty": qty, "unit_price": p2, "unit_cost": co2,
                "total_price": round(p2 * qty, 2), "total_cost": round(co2 * qty, 2),
            })

    subtotal = round(sum(i["total_price"] for i in items), 2)
    discount = round(subtotal * 0.10, 2) if random.random() < 0.10 else 0.0
    net = round(subtotal - discount, 2)
    tax = round(net * 0.095, 2)
    tip = round(net * random.uniform(0.18, 0.26), 2)
    total = round(net + tax + tip, 2)

    txn = {
        "id": txn_id,
        "created_at": ts.isoformat(),
        "date": ts.date().isoformat(),
        "hour": ts.hour,
        "day_of_week": ts.weekday(),
        "table_no": f"Room {random.randint(1, 5)}",
        "covers": covers,
        "employee_id": random.choice(EMPLOYEES),
        "order_type": random.choices(["appointment", "walk_in"], weights=[75, 25])[0],
        "subtotal": subtotal, "discount": discount,
        "tax": tax, "tip": tip, "total": total,
        "payment_method": random.choices(
            ["credit_visa", "credit_mc", "credit_amex", "cash", "apple_pay", "zelle"],
            weights=[28, 22, 15, 18, 12, 5])[0],
        "void": 1 if random.random() < 0.005 else 0,
    }
    return txn, items


def seed(start: date, end: date, reset: bool = False):
    init_schema(INDUSTRY)
    conn = get_conn(INDUSTRY)

    if reset:
        conn.executescript("DELETE FROM line_items; DELETE FROM transactions; DELETE FROM catalog;")
        conn.commit()
        print("♻️  Cleared existing data")

    if conn.execute("SELECT COUNT(*) FROM catalog").fetchone()[0] == 0:
        conn.executemany("INSERT OR IGNORE INTO catalog VALUES (?,?,?,?,?,1)", CATALOG)
        conn.commit()
        print(f"📋 Inserted {len(CATALOG)} services")

    total_txns = total_items = 0
    d = start
    while d <= end:
        n = daily_count(d)
        for ts in service_timestamps(d, n):
            txn, items = build_transaction(ts, INDUSTRY)
            conn.execute("""INSERT OR IGNORE INTO transactions
                VALUES (:id,:created_at,:date,:hour,:day_of_week,:table_no,
                        :covers,:employee_id,:order_type,:subtotal,:discount,
                        :tax,:tip,:total,:payment_method,:void)""", txn)
            conn.executemany("""INSERT OR IGNORE INTO line_items
                VALUES (:id,:transaction_id,:item_id,:item_name,:category,
                        :qty,:unit_price,:unit_cost,:total_price,:total_cost)""", items)
            total_txns += 1
            total_items += len(items)
        d += timedelta(days=1)

    conn.commit()
    conn.close()
    days = (end - start).days + 1
    print(f"✅ Seeded {INDUSTRY}")
    print(f"   Period : {start} → {end} ({days} days)")
    print(f"   Appts  : {total_txns:,}")
    print(f"   Items  : {total_items:,}")
    print(f"   DB     : data/pos/{INDUSTRY}.db")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",  default="2025-12-01")
    parser.add_argument("--end",    default="2026-02-28")
    parser.add_argument("--reset",  action="store_true")
    args = parser.parse_args()
    seed(date.fromisoformat(args.start), date.fromisoformat(args.end), args.reset)
