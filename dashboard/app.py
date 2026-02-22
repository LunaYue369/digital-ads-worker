#!/usr/bin/env python3
"""
Business Analyst Dashboard — Square-style POS monitor.

Usage:
    streamlit run dashboard/app.py
    streamlit run dashboard/app.py -- --industry seafood_restaurant
"""
import sys
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools" / "biz"))
from biz_db import get_db_path

# ── Industry config ────────────────────────────────────────────────────────────
INDUSTRIES = {
    "seafood_restaurant": "🦞 Seafood Restaurant",
    "massage_spa":        "💆 Massage & Spa",
    "used_car_dealer":    "🚗 Used Car Dealer",
}

SEED_SCRIPTS = {
    "seafood_restaurant": "biz_seed_data.py",
    "massage_spa":        "biz_seed_massage_spa.py",
    "used_car_dealer":    "biz_seed_used_car.py",
}

# ── Colour palette (Square-inspired, light theme) ─────────────────────────────
SQ_BLUE   = "#006AFF"
SQ_GREEN  = "#00915E"
SQ_RED    = "#E5350E"
SQ_YELLOW = "#D97706"
SQ_GRAY   = "#6B7280"
BG_CARD   = "#F9FAFB"
CHART_BG  = "#FFFFFF"
FONT_DARK = "#111827"
GRID_COL  = "#E5E7EB"

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Business Analyst · Clawdbot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auto-refresh every 10 s
st_autorefresh(interval=10_000, key="autorefresh")

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Light background */
.stApp { background-color: #FFFFFF; color: #111827; }
.stApp p, .stApp span, .stApp div { color: #111827; }

/* Metric cards */
div[data-testid="metric-container"] {
    background: #F9FAFB;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 16px 20px;
}
div[data-testid="metric-container"] label { color: #6B7280; font-size: 0.78rem; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.6rem; font-weight: 700; color: #111827;
}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] svg { display: none; }

/* Section headings */
h1, h2, h3 { color: #111827; border-bottom: 1px solid #E5E7EB; padding-bottom: 6px; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #F3F4F6; }
section[data-testid="stSidebar"] * { color: #111827 !important; }

/* Dataframe */
div[data-testid="stDataFrame"] { color: #111827; }

/* Catalog table badges */
.active-yes { color: #00915E; font-weight: 600; }
.active-no  { color: #E5350E; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────
def get_conn_cached(industry: str):
    """Create a fresh connection per render — avoids thread-safety issues with Streamlit."""
    db_path = get_db_path(industry)
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def qdf(conn, sql: str, params=()):
    """Run SQL, return DataFrame."""
    return pd.read_sql_query(sql, conn, params=params)


def latest_date(conn) -> str:
    row = conn.execute("SELECT MAX(date) FROM transactions").fetchone()
    return row[0] if row and row[0] else date.today().isoformat()


def date_range(period: str, latest: str):
    end = date.fromisoformat(latest)
    if period == "Today":
        return end.isoformat(), end.isoformat()
    elif period == "This Week (7d)":
        return (end - timedelta(days=6)).isoformat(), end.isoformat()
    elif period == "This Month (30d)":
        return (end - timedelta(days=29)).isoformat(), end.isoformat()
    else:
        return (end - timedelta(days=89)).isoformat(), end.isoformat()


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Clawdbot Analytics")
    st.markdown("---")

    industry = st.selectbox(
        "Store / Industry",
        list(INDUSTRIES.keys()),
        format_func=lambda x: INDUSTRIES[x],
    )

    period = st.radio(
        "Time Period",
        ["Today", "This Week (7d)", "This Month (30d)", "Last 90d"],
        index=1,
    )

    st.markdown("---")
    st.caption("Auto-refreshes every 10 s")
    st.caption(f"DB: `data/pos/{industry}.db`")


# ── Load data ──────────────────────────────────────────────────────────────────
conn = get_conn_cached(industry)
if conn is None:
    seed_script = SEED_SCRIPTS.get(industry, "biz_seed_data.py")
    st.error(
        f"Database not found for **{INDUSTRIES[industry]}**.  \n"
        f"Run: `python tools/biz/{seed_script}` to generate mock data."
    )
    st.stop()

latest = latest_date(conn)
d_from, d_to = date_range(period, latest)

# Prior period (same length, one period back) for delta
span = (date.fromisoformat(d_to) - date.fromisoformat(d_from)).days + 1
prev_to   = (date.fromisoformat(d_from) - timedelta(days=1)).isoformat()
prev_from = (date.fromisoformat(prev_to) - timedelta(days=span - 1)).isoformat()

# ── KPI aggregates ─────────────────────────────────────────────────────────────
def kpi(conn, fr, to):
    row = conn.execute("""
        SELECT
            ROUND(SUM(CASE WHEN void=0 THEN total    ELSE 0 END), 2) AS revenue,
            SUM(CASE WHEN void=0 THEN 1     ELSE 0 END)               AS orders,
            SUM(CASE WHEN void=0 THEN covers ELSE 0 END)              AS covers,
            ROUND(AVG(CASE WHEN void=0 THEN total END), 2)            AS avg_check,
            SUM(CASE WHEN void=1 THEN 1 ELSE 0 END)                   AS voids
        FROM transactions
        WHERE date BETWEEN ? AND ?
    """, (fr, to)).fetchone()
    return dict(row)

cur  = kpi(conn, d_from, d_to)
prev = kpi(conn, prev_from, prev_to)

cost_row = conn.execute("""
    SELECT ROUND(SUM(li.total_cost)*100.0
                 / NULLIF(SUM(li.total_price),0), 1) AS cost_pct
    FROM line_items li
    JOIN transactions t ON li.transaction_id = t.id
    WHERE t.date BETWEEN ? AND ? AND t.void = 0
""", (d_from, d_to)).fetchone()
cost_pct = cost_row[0] if cost_row and cost_row[0] else 0.0


def delta_pct(cur_val, prev_val):
    if not prev_val or prev_val == 0:
        return None
    return round((cur_val - prev_val) / prev_val * 100, 1)


# ── Header ─────────────────────────────────────────────────────────────────────
col_title, col_badge = st.columns([5, 1])
with col_title:
    st.markdown(f"## {INDUSTRIES[industry]} · Business Dashboard")
    st.caption(f"Period: **{d_from}** → **{d_to}**  |  Latest data: {latest}")
with col_badge:
    st.markdown(
        f"<div style='background:{SQ_GREEN};border-radius:8px;"
        f"padding:6px 12px;text-align:center;margin-top:14px;"
        f"font-weight:600;font-size:0.8rem;color:#FFFFFF;'>● LIVE</div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── KPI cards ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

rev_delta = delta_pct(cur["revenue"] or 0, prev["revenue"] or 0)
ord_delta = delta_pct(cur["orders"]  or 0, prev["orders"]  or 0)
cov_delta = delta_pct(cur["covers"]  or 0, prev["covers"]  or 0)
chk_delta = delta_pct(cur["avg_check"] or 0, prev["avg_check"] or 0)

def fmt_delta(d):
    if d is None: return None
    return f"{'+' if d >= 0 else ''}{d}%"

k1.metric("💰 Revenue",    f"${cur['revenue']:,.0f}",  fmt_delta(rev_delta))
k2.metric("🧾 Orders",     f"{cur['orders']:,}",       fmt_delta(ord_delta))
k3.metric("👥 Covers",     f"{cur['covers']:,}",       fmt_delta(cov_delta))
k4.metric("📋 Avg Check",  f"${cur['avg_check'] or 0:,.2f}", fmt_delta(chk_delta))
k5.metric("🏷️ Cost Ratio", f"{cost_pct}%",             None)

st.markdown("---")

# ── Row 2: Hourly chart + Top items ────────────────────────────────────────────
col_hourly, col_items = st.columns([3, 2])

with col_hourly:
    st.markdown("### Hourly Sales")
    hourly_df = qdf(conn, """
        SELECT hour,
               ROUND(SUM(CASE WHEN void=0 THEN total ELSE 0 END), 2) AS revenue,
               SUM(CASE WHEN void=0 THEN 1 ELSE 0 END)               AS orders
        FROM transactions
        WHERE date BETWEEN ? AND ?
        GROUP BY hour ORDER BY hour
    """, (d_from, d_to))

    if hourly_df.empty:
        st.info("No data for selected period.")
    else:
        fig_h = go.Figure()
        fig_h.add_trace(go.Bar(
            x=hourly_df["hour"],
            y=hourly_df["revenue"],
            marker_color=SQ_BLUE,
            opacity=0.85,
            name="Revenue",
            hovertemplate="Hour %{x}:00<br>Revenue: $%{y:,.0f}<extra></extra>",
        ))
        fig_h.update_layout(
            plot_bgcolor=CHART_BG,
            paper_bgcolor=CHART_BG,
            font_color=FONT_DARK,
            height=280,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(
                tickmode="array",
                tickvals=list(range(8, 23)),
                ticktext=[f"{h}:00" for h in range(8, 23)],
                gridcolor=GRID_COL,
            ),
            yaxis=dict(tickprefix="$", gridcolor=GRID_COL),
            showlegend=False,
        )
        st.plotly_chart(fig_h, use_container_width=True)

with col_items:
    st.markdown("### Top Items by Revenue")
    items_df = qdf(conn, """
        SELECT li.item_name,
               ROUND(SUM(li.total_price), 2) AS revenue,
               SUM(li.qty)                   AS units
        FROM line_items li
        JOIN transactions t ON li.transaction_id = t.id
        WHERE t.date BETWEEN ? AND ? AND t.void = 0
        GROUP BY li.item_id
        ORDER BY revenue DESC
        LIMIT 8
    """, (d_from, d_to))

    if items_df.empty:
        st.info("No data for selected period.")
    else:
        fig_i = go.Figure(go.Bar(
            x=items_df["revenue"],
            y=items_df["item_name"],
            orientation="h",
            marker_color=SQ_GREEN,
            opacity=0.85,
            hovertemplate="%{y}<br>Revenue: $%{x:,.0f}<extra></extra>",
        ))
        fig_i.update_layout(
            plot_bgcolor=CHART_BG,
            paper_bgcolor=CHART_BG,
            font_color=FONT_DARK,
            height=280,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(tickprefix="$", gridcolor=GRID_COL),
            yaxis=dict(autorange="reversed", gridcolor=GRID_COL),
            showlegend=False,
        )
        st.plotly_chart(fig_i, use_container_width=True)

# ── Row 3: Daily revenue trend ─────────────────────────────────────────────────
st.markdown("### Daily Revenue Trend")
daily_df = qdf(conn, """
    SELECT date,
           ROUND(SUM(CASE WHEN void=0 THEN total ELSE 0 END), 2) AS revenue,
           SUM(CASE WHEN void=0 THEN 1 ELSE 0 END)               AS orders
    FROM transactions
    WHERE date BETWEEN ? AND ?
    GROUP BY date ORDER BY date
""", (d_from, d_to))

if not daily_df.empty:
    fig_d = go.Figure()
    fig_d.add_trace(go.Scatter(
        x=daily_df["date"],
        y=daily_df["revenue"],
        mode="lines+markers",
        line=dict(color=SQ_BLUE, width=2),
        marker=dict(size=5, color=SQ_BLUE),
        fill="tozeroy",
        fillcolor="rgba(0,106,255,0.08)",
        hovertemplate="%{x}<br>Revenue: $%{y:,.0f}<extra></extra>",
        name="Revenue",
    ))
    fig_d.update_layout(
        plot_bgcolor=CHART_BG,
        paper_bgcolor=CHART_BG,
        font_color=FONT_DARK,
        height=220,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(gridcolor=GRID_COL),
        yaxis=dict(tickprefix="$", gridcolor=GRID_COL),
        showlegend=False,
    )
    st.plotly_chart(fig_d, use_container_width=True)

# ── Row 4: Category breakdown + Payment mix ───────────────────────────────────
col_cat, col_pay = st.columns(2)

with col_cat:
    st.markdown("### Revenue by Category")
    cat_df = qdf(conn, """
        SELECT li.category,
               ROUND(SUM(li.total_price), 2) AS revenue
        FROM line_items li
        JOIN transactions t ON li.transaction_id = t.id
        WHERE t.date BETWEEN ? AND ? AND t.void = 0
        GROUP BY li.category ORDER BY revenue DESC
    """, (d_from, d_to))

    if not cat_df.empty:
        fig_c = px.pie(
            cat_df, values="revenue", names="category",
            color_discrete_sequence=[SQ_BLUE, SQ_GREEN, SQ_YELLOW, SQ_GRAY,
                                     SQ_RED, "#A78BFA", "#34D399"],
            hole=0.45,
        )
        fig_c.update_layout(
            plot_bgcolor=CHART_BG, paper_bgcolor=CHART_BG,
            font_color=FONT_DARK, height=260,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(font_color=FONT_DARK),
            showlegend=True,
        )
        fig_c.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_c, use_container_width=True)

with col_pay:
    st.markdown("### Payment Methods")
    pay_df = qdf(conn, """
        SELECT payment_method,
               COUNT(*)                                            AS orders,
               ROUND(SUM(CASE WHEN void=0 THEN total ELSE 0 END), 2) AS revenue
        FROM transactions
        WHERE date BETWEEN ? AND ? AND void = 0
        GROUP BY payment_method ORDER BY revenue DESC
    """, (d_from, d_to))

    if not pay_df.empty:
        pay_df["label"] = pay_df["payment_method"].str.replace("_", " ").str.title()
        fig_p = px.bar(
            pay_df, x="revenue", y="label", orientation="h",
            color_discrete_sequence=[SQ_YELLOW],
        )
        fig_p.update_layout(
            plot_bgcolor=CHART_BG, paper_bgcolor=CHART_BG,
            font_color=FONT_DARK, height=260,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(tickprefix="$", gridcolor=GRID_COL),
            yaxis=dict(title="", autorange="reversed", gridcolor=GRID_COL),
            showlegend=False,
        )
        st.plotly_chart(fig_p, use_container_width=True)

# ── Row 5 & 6: Table date range picker ────────────────────────────────────────
st.markdown("---")
tbl_col1, tbl_col2, tbl_col3 = st.columns([2, 2, 4])
with tbl_col1:
    tbl_from = st.date_input(
        "Table From",
        value=date.fromisoformat(d_from),
        min_value=date(2020, 1, 1),
        max_value=date.fromisoformat(latest),
        key="tbl_from",
    )
with tbl_col2:
    tbl_to = st.date_input(
        "Table To",
        value=date.fromisoformat(latest),
        min_value=date(2020, 1, 1),
        max_value=date.fromisoformat(latest),
        key="tbl_to",
    )
tbl_from_s = tbl_from.isoformat()
tbl_to_s   = tbl_to.isoformat()

# ── Row 5: Recent transactions table ──────────────────────────────────────────
st.markdown("### Recent Transactions")

txn_df = qdf(conn, """
    SELECT created_at, date, hour,
           order_type, covers, employee_id,
           subtotal, discount, tax, tip, total,
           payment_method,
           CASE WHEN void=1 THEN '❌ Void' ELSE 'Valid' END AS status
    FROM transactions
    WHERE date BETWEEN ? AND ?
    ORDER BY created_at DESC
    LIMIT 200
""", (tbl_from_s, tbl_to_s))

if not txn_df.empty:
    txn_df["total"] = txn_df["total"].apply(lambda x: f"${x:,.2f}")
    txn_df["subtotal"] = txn_df["subtotal"].apply(lambda x: f"${x:,.2f}")
    txn_df.rename(columns={
        "created_at": "Time", "order_type": "Type",
        "covers": "Covers", "employee_id": "Staff",
        "subtotal": "Subtotal", "discount": "Disc",
        "tax": "Tax", "tip": "Tip", "total": "Total",
        "payment_method": "Payment", "status": "Status",
    }, inplace=True)
    st.dataframe(
        txn_df[["Time", "Type", "Covers", "Staff",
                "Subtotal", "Disc", "Tax", "Tip", "Total",
                "Payment", "Status"]],
        use_container_width=True,
        height=320,
        hide_index=True,
    )

# ── Row 6: Line Items detail ──────────────────────────────────────────────────
st.markdown("### Order Line Items")
st.caption("Individual items from every transaction in the selected period — sorted by most recent first")

li_df = qdf(conn, """
    SELECT
        t.created_at                                        AS "Time",
        substr(t.id, 5, 8)                                 AS "Txn",
        t.order_type                                        AS "Type",
        li.item_name                                        AS "Item",
        li.category                                         AS "Category",
        li.qty                                              AS "Qty",
        printf('$%.2f', li.unit_price)                     AS "Unit Price",
        printf('$%.2f', li.total_price)                    AS "Revenue",
        printf('$%.2f', li.total_cost)                     AS "Cost",
        ROUND((li.total_price - li.total_cost) * 100.0
              / NULLIF(li.total_price, 0), 1)              AS "Margin %"
    FROM line_items li
    JOIN transactions t ON li.transaction_id = t.id
    WHERE t.date BETWEEN ? AND ? AND t.void = 0
    ORDER BY t.created_at DESC, li.item_name
    LIMIT 200
""", (tbl_from_s, tbl_to_s))

if li_df.empty:
    st.info("No line item data for selected period.")
else:
    st.dataframe(
        li_df,
        use_container_width=True,
        height=340,
        hide_index=True,
    )

# ── Row 7: Current Catalog / Menu ─────────────────────────────────────────────
st.markdown("---")
st.markdown("### Current Catalog / Menu")
st.caption("Live view of all items · Updates immediately when Clawdbot makes changes via `biz_update`")

catalog_df = qdf(conn, """
    SELECT
        name        AS "Item Name",
        category    AS "Category",
        printf('$%.2f', price) AS "Price",
        printf('$%.2f', cost)  AS "Cost",
        ROUND((price - cost) * 100.0 / NULLIF(price, 0), 1) AS "Margin %",
        CASE WHEN active = 1 THEN 'Active' ELSE '❌ Inactive' END AS "Status"
    FROM catalog
    ORDER BY category, price DESC
""")

if not catalog_df.empty:
    st.dataframe(
        catalog_df,
        use_container_width=True,
        height=min(40 + len(catalog_df) * 35, 420),
        hide_index=True,
    )
else:
    st.info("No catalog items found.")

st.markdown("---")
st.caption("Clawdbot Business Analyst · Powered by OpenClaw · SQLite backend")
