#!/usr/bin/env python3
"""
Mock POS data generator — SoCal Used Car Dealership
Generates 3 months of realistic deal data (Dec 2025 – Feb 2026).

Usage:
    python tools/biz/biz_seed_used_car.py
    python tools/biz/biz_seed_used_car.py --reset
"""
import argparse
import random
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from biz_db import get_conn, init_schema

INDUSTRY = "used_car_dealer"

CATALOG = [
    ("economy_sedan",  "Economy Sedan (Used, <100k mi)",    "Vehicle",  12500,  9800),
    ("compact_suv",    "Compact SUV (Used, <80k mi)",       "Vehicle",  22000, 17500),
    ("midsize_sedan",  "Midsize Sedan (Used, <60k mi)",     "Vehicle",  18500, 14800),
    ("fullsize_suv",   "Full-Size SUV (Cert., <70k mi)",    "Vehicle",  35000, 28000),
    ("pickup_truck",   "Pickup Truck (Used, <90k mi)",      "Vehicle",  28000, 22000),
    ("luxury_sedan",   "Luxury Sedan (Cert., <50k mi)",     "Vehicle",  48000, 38000),
    ("electric_suv",   "Electric SUV (Used, <60k mi)",      "Vehicle",  32000, 25000),
    ("ext_warranty",   "Extended Warranty (3yr/36k mi)",    "F&I",       2500,   800),
    ("gap_insurance",  "GAP Insurance",                     "F&I",        800,   200),
    ("detailing_pkg",  "Full Detail Package",               "Service",    350,   120),
    ("doc_fee",        "Documentation & Title Fee",         "Service",    250,   180),
]

CATALOG_DICT = {c[0]: c for c in CATALOG}

VEHICLES     = ["economy_sedan","compact_suv","midsize_sedan",
                "fullsize_suv","pickup_truck","luxury_sedan","electric_suv"]
VEH_WEIGHTS  = [0.22, 0.20, 0.20, 0.10, 0.13, 0.06, 0.09]

EMPLOYEES = ["sales_mike", "sales_sarah", "sales_james", "sales_linda", "sales_carlos"]


def daily_count(d: date) -> int:
    dow = d.weekday()
    base = {0: 3, 1: 2, 2: 3, 3: 3, 4: 4, 5: 5, 6: 2}[dow]
    # End-of-month rush
    if d.day >= 28:
        base = int(base * 1.6)
    elif d.day >= 25:
        base = int(base * 1.3)
    holidays = {
        date(2025, 12, 24): 0.7,
        date(2025, 12, 25): 0.0,   # closed
        date(2025, 12, 26): 1.4,   # post-Christmas deals
        date(2025, 12, 31): 2.0,   # end of year tax deals
        date(2026,  1,  1): 0.0,   # closed
        date(2026,  1,  2): 1.8,   # New Year deals
        date(2026,  1, 16): 1.3,
        date(2026,  1, 29): 1.2,   # CNY (Chinese community buys cars)
        date(2026,  2, 14): 0.8,
    }
    mult = holidays.get(d, 1.0)
    if mult == 0.0:
        return 0
    return max(0, int(base * mult * random.uniform(0.85, 1.15)))


def service_timestamps(d: date, n: int):
    slots = []
    for _ in range(n):
        h = random.choices([9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
                           weights=[5, 12, 15, 12, 10, 12, 12, 12, 8, 2])[0]
        slots.append(datetime(d.year, d.month, d.day, h,
                              random.randint(0, 59), random.randint(0, 59)))
    return slots


def build_transaction(ts: datetime, industry: str):
    txn_id = "txn_" + uuid.uuid4().hex[:12]

    vehicle_id = random.choices(VEHICLES, weights=VEH_WEIGHTS)[0]
    _, vname, vcat, vprice, vcost = CATALOG_DICT[vehicle_id]

    items = [{
        "id": "li_" + uuid.uuid4().hex[:12],
        "transaction_id": txn_id,
        "item_id": vehicle_id, "item_name": vname, "category": vcat,
        "qty": 1, "unit_price": vprice, "unit_cost": vcost,
        "total_price": vprice, "total_cost": vcost,
    }]

    # F&I and service add-ons
    add_ons = [
        ("ext_warranty",  0.62),
        ("gap_insurance",  0.38),
        ("detailing_pkg",  0.55),
        ("doc_fee",        1.00),   # always charged
    ]
    for addon_id, prob in add_ons:
        if random.random() < prob:
            _, n2, c2, p2, co2 = CATALOG_DICT[addon_id]
            items.append({
                "id": "li_" + uuid.uuid4().hex[:12],
                "transaction_id": txn_id,
                "item_id": addon_id, "item_name": n2, "category": c2,
                "qty": 1, "unit_price": p2, "unit_cost": co2,
                "total_price": p2, "total_cost": co2,
            })

    subtotal = round(sum(i["total_price"] for i in items), 2)
    # Car deals often have negotiated discount
    discount = 0.0
    if random.random() < 0.70:
        discount = round(random.uniform(200, min(subtotal * 0.05, 2500)), 0)
    net = round(subtotal - discount, 2)
    tax = round(net * 0.095, 2)
    total = round(net + tax, 2)   # no tip on car sales

    payment = random.choices(
        ["financing", "cash", "certified_check", "credit_card"],
        weights=[55, 20, 18, 7])[0]

    covers = random.choices([1, 2], weights=[65, 35])[0]  # solo or couple

    txn = {
        "id": txn_id,
        "created_at": ts.isoformat(),
        "date": ts.date().isoformat(),
        "hour": ts.hour,
        "day_of_week": ts.weekday(),
        "table_no": f"Deal-{random.randint(100, 999)}",
        "covers": covers,
        "employee_id": random.choice(EMPLOYEES),
        "order_type": random.choices(
            ["in_person", "online_delivery", "out_of_state_ship"],
            weights=[85, 10, 5])[0],
        "subtotal": subtotal, "discount": discount,
        "tax": tax, "tip": 0.0, "total": total,
        "payment_method": payment,
        "void": 1 if random.random() < 0.008 else 0,
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
        print(f"📋 Inserted {len(CATALOG)} items")

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
    print(f"   Deals  : {total_txns:,}")
    print(f"   Items  : {total_items:,}")
    print(f"   DB     : data/pos/{INDUSTRY}.db")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",  default="2025-12-01")
    parser.add_argument("--end",    default="2026-02-28")
    parser.add_argument("--reset",  action="store_true")
    args = parser.parse_args()
    seed(date.fromisoformat(args.start), date.fromisoformat(args.end), args.reset)
