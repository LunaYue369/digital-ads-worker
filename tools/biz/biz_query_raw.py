#!/usr/bin/env python3
"""
Flexible raw query tool — lets the agent ask precise questions about the POS data.

Usage:
    python tools/biz/biz_query_raw.py --industry seafood_restaurant --question "which items sold best last week"
    python tools/biz/biz_query_raw.py --industry seafood_restaurant --date_from 2026-02-01 --date_to 2026-02-28 --group_by item
    python tools/biz/biz_query_raw.py --industry seafood_restaurant --group_by day --date_from 2026-01-01
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from biz_db import get_conn

PRESETS = {
    "item":     ("items",    "li.item_name, li.category"),
    "category": ("category", "li.category"),
    "day":      ("day",      "t.date"),
    "hour":     ("hour",     "t.hour"),
    "weekday":  ("weekday",  "t.day_of_week"),
    "employee": ("employee", "t.employee_id"),
    "payment":  ("payment",  "t.payment_method"),
    "order_type": ("order_type", "t.order_type"),
}

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def run_query(industry: str, date_from: str, date_to: str,
              group_by: str, limit: int) -> list:
    conn = get_conn(industry)

    if group_by in ("item", "category"):
        label, group_col = PRESETS[group_by]
        rows = conn.execute(f"""
            SELECT {group_col},
                   SUM(li.qty)                                AS units,
                   ROUND(SUM(li.total_price), 2)             AS revenue,
                   ROUND(SUM(li.total_cost), 2)              AS cost,
                   ROUND(SUM(li.total_cost)*100.0
                         / NULLIF(SUM(li.total_price),0), 1) AS cost_pct,
                   COUNT(DISTINCT t.id)                      AS in_orders
            FROM line_items li
            JOIN transactions t ON li.transaction_id = t.id
            WHERE t.date BETWEEN ? AND ? AND t.void = 0
            GROUP BY {group_col}
            ORDER BY revenue DESC
            LIMIT ?
        """, (date_from, date_to, limit)).fetchall()
    else:
        label, group_col = PRESETS.get(group_by, ("day", "t.date"))
        rows = conn.execute(f"""
            SELECT {group_col}                                        AS period,
                   COUNT(CASE WHEN void=0 THEN 1 END)                AS orders,
                   SUM(CASE WHEN void=0 THEN covers ELSE 0 END)      AS covers,
                   ROUND(SUM(CASE WHEN void=0 THEN total ELSE 0 END),2) AS revenue,
                   ROUND(AVG(CASE WHEN void=0 THEN total END), 2)    AS avg_check
            FROM transactions t
            WHERE t.date BETWEEN ? AND ?
            GROUP BY {group_col}
            ORDER BY revenue DESC
            LIMIT ?
        """, (date_from, date_to, limit)).fetchall()

    conn.close()

    result = [dict(r) for r in rows]
    # Humanize weekday numbers
    if group_by == "weekday":
        for r in result:
            r["weekday_name"] = WEEKDAY_NAMES[r["period"]]
    return result


def main():
    # Default: last 30 days ending at the latest DB date
    parser = argparse.ArgumentParser(description="Flexible POS data query")
    parser.add_argument("--industry",  default="seafood_restaurant")
    parser.add_argument("--date_from", default=None)
    parser.add_argument("--date_to",   default=None)
    parser.add_argument("--group_by",  default="day",
                        choices=list(PRESETS.keys()),
                        help="Grouping dimension")
    parser.add_argument("--limit",     type=int, default=30)
    args = parser.parse_args()

    conn = get_conn(args.industry)
    latest = conn.execute("SELECT MAX(date) FROM transactions").fetchone()[0]
    conn.close()

    if not latest:
        print("📭 No data in database.")
        sys.exit(0)

    date_to = args.date_to or latest
    date_from = args.date_from or (
        date.fromisoformat(date_to) - timedelta(days=29)).isoformat()

    rows = run_query(args.industry, date_from, date_to,
                     args.group_by, args.limit)

    print(f"📊 {args.group_by.capitalize()} breakdown  {date_from} → {date_to}")
    print(f"   {len(rows)} rows\n")
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
