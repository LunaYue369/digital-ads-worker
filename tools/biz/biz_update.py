#!/usr/bin/env python3
"""
POS write-back tool — lets the agent modify catalog and simulate new transactions.

Actions:
    update_price    — change a catalog item's price (and optionally cost)
    toggle_item     — activate or deactivate a catalog item
    add_item        — add a new item to the catalog
    add_transaction — generate and insert a realistic new transaction
    void_last       — void the most recent N transactions

Usage:
    python tools/biz/biz_update.py --industry seafood_restaurant --action update_price --item_id king_crab --price 115.2
    python tools/biz/biz_update.py --industry seafood_restaurant --action toggle_item --item_id lobster --active false
    python tools/biz/biz_update.py --industry seafood_restaurant --action add_item --item_id salmon --name "Salmon Fillet" --category "Seafood" --price 45 --cost 16
    python tools/biz/biz_update.py --industry seafood_restaurant --action add_transaction --covers 4
    python tools/biz/biz_update.py --industry used_car_dealer --action add_transaction --covers 1 --employee_id sales_james --order_type in_person --payment_method credit_card --item_ids compact_suv --subtotal 15000 --discount 5000 --tax 1000 --tip 0 --total 11000
    python tools/biz/biz_update.py --industry seafood_restaurant --action void_last --n 1
"""
import argparse
import json
import random
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from biz_db import get_conn


# ── helpers ────────────────────────────────────────────────────────────────────

def list_catalog(conn):
    rows = conn.execute(
        "SELECT id, name, category, price, cost, active FROM catalog ORDER BY category, price DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def find_item(conn, item_id: str):
    row = conn.execute("SELECT * FROM catalog WHERE id = ?", (item_id,)).fetchone()
    if row:
        return dict(row)
    # fuzzy: try name contains
    rows = conn.execute(
        "SELECT * FROM catalog WHERE name LIKE ?", (f"%{item_id}%",)
    ).fetchall()
    return dict(rows[0]) if rows else None


# ── actions ────────────────────────────────────────────────────────────────────

def action_update_price(conn, args) -> str:
    item = find_item(conn, args.item_id)
    if not item:
        catalog = list_catalog(conn)
        ids = [r["id"] for r in catalog]
        return f"❌ Item '{args.item_id}' not found. Available IDs: {ids}"

    old_price = item["price"]
    new_price = float(args.price)
    new_cost  = float(args.cost) if args.cost else item["cost"]

    conn.execute(
        "UPDATE catalog SET price = ?, cost = ? WHERE id = ?",
        (new_price, new_cost, item["id"])
    )
    conn.commit()
    margin = round((new_price - new_cost) / new_price * 100, 1)
    return (
        f"✅ Price updated: {item['name']}\n"
        f"   ${old_price:.2f} → ${new_price:.2f}  (cost ${new_cost:.2f}, margin {margin}%)\n"
        f"   Dashboard will reflect this on next refresh."
    )


def action_toggle_item(conn, args) -> str:
    item = find_item(conn, args.item_id)
    if not item:
        catalog = list_catalog(conn)
        return f"❌ Item '{args.item_id}' not found. IDs: {[r['id'] for r in catalog]}"

    active = 0 if str(args.active).lower() in ("false", "0", "no", "off") else 1
    conn.execute("UPDATE catalog SET active = ? WHERE id = ?", (active, item["id"]))
    conn.commit()
    status = "✅ Active" if active else "❌ Inactive (hidden from menu)"
    return f"✅ {item['name']} → {status}\n   Dashboard catalog section updated."


def action_add_item(conn, args) -> str:
    existing = conn.execute("SELECT id FROM catalog WHERE id = ?", (args.item_id,)).fetchone()
    if existing:
        return f"❌ Item ID '{args.item_id}' already exists. Use update_price to modify it."

    price = float(args.price)
    cost  = float(args.cost)
    margin = round((price - cost) / price * 100, 1)
    conn.execute(
        "INSERT INTO catalog VALUES (?, ?, ?, ?, ?, 1)",
        (args.item_id, args.name, args.category, price, cost)
    )
    conn.commit()
    return (
        f"✅ New item added to catalog:\n"
        f"   ID: {args.item_id}\n"
        f"   Name: {args.name}  ({args.category})\n"
        f"   Price: ${price:.2f}  Cost: ${cost:.2f}  Margin: {margin}%"
    )


def action_add_transaction(conn, args) -> str:
    """Record a transaction. Accepts explicit fields; falls back to random for omitted ones."""
    covers  = int(args.covers) if args.covers else random.randint(1, 4)
    now     = datetime.now()
    txn_id  = "txn_" + uuid.uuid4().hex[:12]

    explicit_financials = args.subtotal is not None

    # ── Line items ──────────────────────────────────────────────────────────────
    items = []

    if args.item_ids:
        # Caller specified which items (comma-separated item_ids)
        for iid in [x.strip() for x in args.item_ids.split(",")]:
            item = find_item(conn, iid)
            if item:
                items.append({
                    "id": "li_" + uuid.uuid4().hex[:12],
                    "transaction_id": txn_id,
                    "item_id": item["id"], "item_name": item["name"],
                    "category": item["category"],
                    "qty": 1,
                    "unit_price": item["price"], "unit_cost": item["cost"],
                    "total_price": item["price"],  "total_cost": item["cost"],
                })

    if not items:
        if explicit_financials:
            # No items specified — create one synthetic line-item for the subtotal
            items.append({
                "id": "li_" + uuid.uuid4().hex[:12],
                "transaction_id": txn_id,
                "item_id": "manual_entry", "item_name": "Manual Entry",
                "category": "Manual",
                "qty": 1,
                "unit_price": float(args.subtotal), "unit_cost": 0.0,
                "total_price": float(args.subtotal), "total_cost": 0.0,
            })
        else:
            # Fully random items from active catalog
            rows = conn.execute(
                "SELECT id, name, category, price, cost FROM catalog WHERE active = 1"
            ).fetchall()
            if not rows:
                return "❌ No active catalog items found."
            catalog_rows = [dict(r) for r in rows]
            primary_candidates = [c for c in catalog_rows
                                   if c["category"] not in ("Add-on", "F&I", "Service")]
            if not primary_candidates:
                primary_candidates = catalog_rows
            n_items = random.randint(1, min(4, len(primary_candidates)))
            chosen  = random.sample(primary_candidates, n_items)
            for item in chosen:
                qty = (random.randint(1, max(1, covers - 1))
                       if item["category"] in ("饮料", "主食", "Add-on") else 1)
                items.append({
                    "id": "li_" + uuid.uuid4().hex[:12],
                    "transaction_id": txn_id,
                    "item_id": item["id"], "item_name": item["name"],
                    "category": item["category"],
                    "qty": qty,
                    "unit_price": item["price"], "unit_cost": item["cost"],
                    "total_price": round(item["price"] * qty, 2),
                    "total_cost":  round(item["cost"]  * qty, 2),
                })

    # ── Financials ──────────────────────────────────────────────────────────────
    if explicit_financials:
        subtotal = float(args.subtotal)
        discount = float(args.discount) if args.discount is not None else 0.0
        tax      = float(args.tax)      if args.tax      is not None else 0.0
        tip      = float(args.tip)      if args.tip      is not None else 0.0
        total    = (float(args.total)   if args.total    is not None
                    else round(subtotal - discount + tax + tip, 2))
    else:
        subtotal = round(sum(i["total_price"] for i in items), 2)
        discount = round(subtotal * 0.10, 2) if random.random() < 0.08 else 0.0
        net      = round(subtotal - discount, 2)
        tax      = round(net * 0.095, 2)
        tip      = round(net * random.uniform(0.15, 0.22), 2)
        total    = round(net + tax + tip, 2)

    # ── Other fields ────────────────────────────────────────────────────────────
    employee_id    = args.employee_id    or "emp_manual"
    order_type     = args.order_type     or "dine_in"
    payment_method = args.payment_method or random.choices(
        ["credit_visa", "credit_mc", "cash", "apple_pay"],
        weights=[35, 25, 25, 15])[0]

    txn = {
        "id": txn_id,
        "created_at": now.isoformat(),
        "date": now.date().isoformat(),
        "hour": now.hour,
        "day_of_week": now.weekday(),
        "table_no": (f"{random.choice('ABCDE')}{random.randint(1,10)}"
                     if order_type == "dine_in" else None),
        "covers": covers,
        "employee_id": employee_id,
        "order_type":  order_type,
        "subtotal": subtotal, "discount": discount,
        "tax": tax, "tip": tip, "total": total,
        "payment_method": payment_method,
        "void": 0,
    }

    conn.execute("""INSERT INTO transactions
        VALUES (:id,:created_at,:date,:hour,:day_of_week,:table_no,
                :covers,:employee_id,:order_type,:subtotal,:discount,
                :tax,:tip,:total,:payment_method,:void)""", txn)
    conn.executemany("""INSERT INTO line_items
        VALUES (:id,:transaction_id,:item_id,:item_name,:category,
                :qty,:unit_price,:unit_cost,:total_price,:total_cost)""", items)
    conn.commit()

    item_list = ", ".join(f"{i['item_name']} x{i['qty']}" for i in items)
    return (
        f"✅ New transaction recorded:\n"
        f"   ID      : {txn_id}\n"
        f"   Staff   : {employee_id}  |  Type: {order_type}  |  Covers: {covers}\n"
        f"   Items   : {item_list}\n"
        f"   Subtotal: ${subtotal:,.2f}  Disc: ${discount:,.2f}  "
        f"Tax: ${tax:,.2f}  Tip: ${tip:,.2f}\n"
        f"   Total   : ${total:,.2f}  |  Payment: {payment_method}\n"
        f"   Dashboard updates on next 10s refresh."
    )


def action_void_last(conn, args) -> str:
    n = int(args.n) if args.n else 1
    rows = conn.execute(
        "SELECT id, total FROM transactions WHERE void = 0 ORDER BY created_at DESC LIMIT ?", (n,)
    ).fetchall()
    if not rows:
        return "❌ No valid transactions to void."

    ids = [r["id"] for r in rows]
    conn.execute(
        f"UPDATE transactions SET void = 1 WHERE id IN ({','.join('?'*len(ids))})", ids
    )
    conn.commit()
    total_voided = sum(r["total"] for r in rows)
    return (
        f"✅ Voided {len(ids)} transaction(s)  (${total_voided:,.2f} removed from revenue)\n"
        f"   IDs: {ids}"
    )


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="POS write-back tool")
    parser.add_argument("--industry", default="seafood_restaurant")
    parser.add_argument("--action",   required=True,
                        choices=["update_price", "toggle_item", "add_item",
                                 "add_transaction", "void_last", "list_catalog"])
    # update_price / toggle_item / add_item
    parser.add_argument("--item_id",  default=None)
    parser.add_argument("--price",    default=None, type=float)
    parser.add_argument("--cost",     default=None, type=float)
    parser.add_argument("--active",   default=None)
    parser.add_argument("--name",     default=None)
    parser.add_argument("--category", default=None)
    # add_transaction — optional explicit fields
    parser.add_argument("--covers",         default=None, type=int)
    parser.add_argument("--employee_id",    default=None)
    parser.add_argument("--order_type",     default=None)
    parser.add_argument("--payment_method", default=None)
    parser.add_argument("--item_ids",       default=None,
                        help="Comma-separated item_ids to include as line items")
    parser.add_argument("--subtotal",       default=None, type=float)
    parser.add_argument("--discount",       default=None, type=float)
    parser.add_argument("--tax",            default=None, type=float)
    parser.add_argument("--tip",            default=None, type=float)
    parser.add_argument("--total",          default=None, type=float)
    # void_last
    parser.add_argument("--n",        default=1,    type=int)
    args = parser.parse_args()

    conn = get_conn(args.industry)

    if args.action == "list_catalog":
        catalog = list_catalog(conn)
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
        conn.close()
        return

    dispatch = {
        "update_price":    action_update_price,
        "toggle_item":     action_toggle_item,
        "add_item":        action_add_item,
        "add_transaction": action_add_transaction,
        "void_last":       action_void_last,
    }

    result = dispatch[args.action](conn, args)
    conn.close()
    print(result)


if __name__ == "__main__":
    main()
