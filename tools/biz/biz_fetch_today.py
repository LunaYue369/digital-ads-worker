#!/usr/bin/env python3
"""
Fetch recent POS data for the agent to analyze.

Usage:
    python tools/biz/biz_fetch_today.py --industry seafood_restaurant
    python tools/biz/biz_fetch_today.py --industry seafood_restaurant --date 2026-02-20
    python tools/biz/biz_fetch_today.py --industry seafood_restaurant --days 7
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from biz_db import get_conn


def fetch(industry: str, target_date: date, days: int = 1) -> dict:
    conn = get_conn(industry)
    start = (target_date - timedelta(days=days - 1)).isoformat()
    end = target_date.isoformat()

    # Daily revenue summary
    daily = conn.execute("""
        SELECT date,
               COUNT(*)                                          AS orders,
               SUM(CASE WHEN void=0 THEN 1 ELSE 0 END)          AS valid_orders,
               SUM(CASE WHEN void=0 THEN covers ELSE 0 END)     AS covers,
               ROUND(SUM(CASE WHEN void=0 THEN subtotal ELSE 0 END), 2) AS net_sales,
               ROUND(SUM(CASE WHEN void=0 THEN discount ELSE 0 END), 2) AS discounts,
               ROUND(SUM(CASE WHEN void=0 THEN total ELSE 0 END), 2)    AS total_collected,
               ROUND(AVG(CASE WHEN void=0 THEN total END), 2)           AS avg_check,
               SUM(CASE WHEN void=1 THEN 1 ELSE 0 END)          AS voids
        FROM transactions
        WHERE date BETWEEN ? AND ?
        GROUP BY date ORDER BY date DESC
    """, (start, end)).fetchall()

    # Top items over the period
    top_items = conn.execute("""
        SELECT li.item_name, li.category,
               SUM(li.qty)                              AS units,
               ROUND(SUM(li.total_price), 2)            AS revenue,
               ROUND(SUM(li.total_cost), 2)             AS cost,
               ROUND(SUM(li.total_cost)*100.0
                     / NULLIF(SUM(li.total_price),0),1) AS cost_pct
        FROM line_items li
        JOIN transactions t ON li.transaction_id = t.id
        WHERE t.date BETWEEN ? AND ? AND t.void = 0
        GROUP BY li.item_id
        ORDER BY revenue DESC
        LIMIT 8
    """, (start, end)).fetchall()

    # Hourly breakdown (latest day only)
    hourly = conn.execute("""
        SELECT hour,
               COUNT(*)                                       AS orders,
               ROUND(SUM(CASE WHEN void=0 THEN total ELSE 0 END), 2) AS revenue
        FROM transactions
        WHERE date = ? AND void = 0
        GROUP BY hour ORDER BY hour
    """, (end,)).fetchall()

    # Cost ratio summary
    cost_summary = conn.execute("""
        SELECT ROUND(SUM(li.total_cost)*100.0
                     / NULLIF(SUM(li.total_price),0), 1) AS cost_ratio_pct,
               ROUND(SUM(li.total_cost), 2)              AS total_cost,
               ROUND(SUM(li.total_price), 2)             AS total_revenue
        FROM line_items li
        JOIN transactions t ON li.transaction_id = t.id
        WHERE t.date BETWEEN ? AND ? AND t.void = 0
    """, (start, end)).fetchone()

    # Same period last week (for WoW comparison)
    wow_start = (date.fromisoformat(start) - timedelta(days=7)).isoformat()
    wow_end = (date.fromisoformat(end) - timedelta(days=7)).isoformat()
    wow = conn.execute("""
        SELECT ROUND(SUM(CASE WHEN void=0 THEN total ELSE 0 END), 2) AS revenue,
               SUM(CASE WHEN void=0 THEN 1 ELSE 0 END)               AS orders
        FROM transactions WHERE date BETWEEN ? AND ?
    """, (wow_start, wow_end)).fetchone()

    conn.close()

    result = {
        "industry": industry,
        "period": f"{start} ~ {end}",
        "daily_summary": [dict(r) for r in daily],
        "top_items": [dict(r) for r in top_items],
        "hourly_today": [dict(r) for r in hourly],
        "cost_summary": dict(cost_summary) if cost_summary else {},
        "wow_comparison": dict(wow) if wow else {},
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch recent POS data")
    parser.add_argument("--industry", default="seafood_restaurant")
    parser.add_argument("--date",  default=None,
                        help="Target date YYYY-MM-DD (default: latest in DB)")
    parser.add_argument("--days",  type=int, default=1,
                        help="How many days to fetch (default: 1)")
    args = parser.parse_args()

    conn = get_conn(args.industry)
    if args.date:
        target = date.fromisoformat(args.date)
    else:
        row = conn.execute(
            "SELECT MAX(date) FROM transactions").fetchone()
        if not row or not row[0]:
            print("📭 No data found in database.")
            sys.exit(0)
        target = date.fromisoformat(row[0])
    conn.close()

    data = fetch(args.industry, target, days=args.days)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
