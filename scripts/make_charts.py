"""
Harbor & Pine: static charts of the key findings for the README.

Input : data_clean/harbor_pine.db  (run clean_and_load.py and run_sql.py first)
Output: images/chart_*.png
Run   : python scripts/make_charts.py   (from the project root)
"""
from pathlib import Path
import sqlite3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "images"
IMG.mkdir(exist_ok=True)
con = sqlite3.connect(ROOT / "data_clean" / "harbor_pine.db")
q = lambda sql: pd.read_sql_query(sql, con)

BLUE, LIGHT, RED, ORANGE, GREY, DARK = "#2563EB", "#93C5FD", "#C0392B", "#E67E22", "#9CA3AF", "#111827"
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 12,
                     "axes.titlelocation": "left"})
money = FuncFormatter(lambda v, _: f"${v/1e6:.1f}M" if abs(v) >= 1e6 else f"${v/1e3:.0f}K")


SITE_IMG = ROOT / "site" / "img"
SITE_IMG.mkdir(parents=True, exist_ok=True)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(IMG / name, dpi=150)
    fig.savefig(SITE_IMG / name, dpi=110)       # smaller copy for the web page
    plt.close(fig)
    print(f"wrote images/{name}")


# 1. RFM segments: share of customers vs share of revenue -------------------
seg = q("""SELECT segment, COUNT(*) AS customers, SUM(monetary) AS revenue
           FROM customer_rfm GROUP BY segment""")
seg["pct_cust"] = seg.customers / seg.customers.sum()
seg["pct_rev"] = seg.revenue / seg.revenue.sum()
order = ["Champions", "Loyal", "Potential Loyalists", "New Customers", "Need Attention",
         "At Risk", "Hibernating", "Lost"]
seg = seg.set_index("segment").loc[order[::-1]]
fig, ax = plt.subplots(figsize=(9, 4.6))
y = range(len(seg))
ax.barh([i + 0.2 for i in y], seg.pct_cust, height=0.4, color=GREY, label="Share of customers")
ax.barh([i - 0.2 for i in y], seg.pct_rev, height=0.4, color=BLUE, label="Share of revenue")
ax.set_yticks(list(y), seg.index)
ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
for i, (c, r) in enumerate(zip(seg.pct_cust, seg.pct_rev)):
    ax.text(r + 0.003, i - 0.2, f"{r:.1%}", va="center", fontsize=8)
    ax.text(c + 0.003, i + 0.2, f"{c:.1%}", va="center", fontsize=8, color="#4B5563")
ax.legend(loc="lower right", frameon=False)
ax.set_title(f"Champions are {seg.pct_cust['Champions']:.1%} of customers but "
             f"{seg.pct_rev['Champions']:.1%} of revenue")
save(fig, "chart_rfm_segments.png")

# 2. Review score by delivery delay ----------------------------------------
d = q("""SELECT CASE WHEN o.delay_days <= 0 THEN 'On time' WHEN o.delay_days <= 3 THEN '1-3 days late'
                     WHEN o.delay_days <= 7 THEN '4-7 days late' ELSE '8+ days late' END AS band,
                MIN(o.delay_days) AS k, AVG(r.review_score) AS score, AVG(r.review_score <= 2) AS bad
         FROM orders o JOIN reviews r USING (order_id)
         WHERE o.order_status = 'delivered' GROUP BY band ORDER BY k""")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6))
cols = [BLUE, ORANGE, RED, RED]
a1.bar(d.band, d.score, color=cols)
a1.set_ylim(0, 5)
a1.set_title("Average review score")
for x, v in enumerate(d.score):
    a1.text(x, v + 0.08, f"{v:.2f}", ha="center")
a2.bar(d.band, d.bad, color=cols)
a2.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
a2.set_title("Share of 1- and 2-star reviews")
for x, v in enumerate(d.bad):
    a2.text(x, v + 0.01, f"{v:.0%}", ha="center")
for a in (a1, a2):
    a.tick_params(axis="x", labelsize=9)
fig.suptitle(f"Reviews fall from {d.score.iloc[0]:.1f} stars on time to {d.score.iloc[2]:.1f} when 4-7 days late",
             x=0.01, ha="left",
             fontweight="bold", fontsize=13)
save(fig, "chart_review_by_delay.png")

# 3. Repeat purchase after a late first delivery ----------------------------
r = q("""WITH ranked AS (
           SELECT o.*, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_purchase_timestamp) AS n,
                  COUNT(*) OVER (PARTITION BY customer_id) AS total_orders
           FROM orders o WHERE order_status <> 'canceled')
         SELECT CASE WHEN delay_days > 3 THEN 'Late by 4+ days' WHEN delay_days > 0 THEN 'Late by 1-3 days'
                     ELSE 'On time' END AS first_delivery, AVG(total_orders > 1) AS again
         FROM ranked WHERE n = 1 AND order_status = 'delivered' AND order_purchase_timestamp < '2025-07-01'
         GROUP BY 1 ORDER BY again DESC""")
fig, ax = plt.subplots(figsize=(7, 3.4))
ax.barh(r.first_delivery[::-1], r.again[::-1], color=[RED, ORANGE, BLUE])
ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
for i, v in enumerate(r.again[::-1]):
    ax.text(v + 0.005, i, f"{v:.1%}", va="center")
ax.set_title("Customers whose first order came 4+ days late rarely return")
ax.set_xlabel("Placed a second order")
save(fig, "chart_repeat_after_late.png")

# 4. Monthly revenue ---------------------------------------------------------
m = q("""SELECT strftime('%Y-%m', order_purchase_timestamp) AS ym, SUM(order_total) AS revenue
         FROM orders WHERE order_status <> 'canceled' GROUP BY ym ORDER BY ym""")
m["date"] = pd.to_datetime(m.ym)
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.plot(m.date, m.revenue, color=BLUE, lw=2)
ax.fill_between(m.date, m.revenue, color=BLUE, alpha=0.08)
ax.yaxis.set_major_formatter(money)
for _, row in m[m.date.dt.month == 12].iterrows():
    ax.annotate(f"{money(row.revenue)}", (row.date, row.revenue), textcoords="offset points",
                xytext=(0, 6), ha="center", fontsize=8)
yr = m.groupby(m.date.dt.year).revenue.sum().pct_change()
ax.set_title(f"Monthly revenue: +{yr[2024]:.0%} in 2024, +{yr[2025]:.0%} in 2025, peaking every Nov-Dec")
save(fig, "chart_monthly_revenue.png")

# 5. Repeat rate by acquisition channel ---------------------------------------
c = q("""WITH pc AS (SELECT o.customer_id, c.acquisition_channel AS ch, COUNT(*) AS n
                    FROM orders o JOIN customers c USING (customer_id)
                    WHERE o.order_status <> 'canceled' GROUP BY 1, 2)
         SELECT ch, AVG(n > 1) AS repeat_rate, COUNT(*) AS customers FROM pc
         WHERE ch <> 'Unknown' GROUP BY ch ORDER BY repeat_rate""")
fig, ax = plt.subplots(figsize=(7, 3.4))
ax.barh(c.ch, c.repeat_rate, color=[RED if v < 0.2 else BLUE for v in c.repeat_rate])
ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
for i, (v, n) in enumerate(zip(c.repeat_rate, c.customers)):
    ax.text(v + 0.005, i, f"{v:.1%}  ({n:,} customers)", va="center", fontsize=9)
ax.set_xlim(0, c.repeat_rate.max() * 1.45)
ratio = c.set_index("ch").repeat_rate
ax.set_title(f"Referral customers come back {ratio['Referral'] / ratio['Marketplace ad']:.1f}x as often as marketplace-ad ones")
save(fig, "chart_channel_repeat.png")

# 6. Late rate by carrier --------------------------------------------------------
lr = q("""SELECT carrier, AVG(is_late) AS late, COUNT(*) AS n FROM orders
          WHERE order_status = 'delivered' GROUP BY carrier ORDER BY late""")
fig, ax = plt.subplots(figsize=(7, 3))
ax.barh(lr.carrier, lr.late, color=[BLUE, ORANGE, RED])
ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
for i, (v, n) in enumerate(zip(lr.late, lr.n)):
    ax.text(v + 0.004, i, f"{v:.1%} of {n:,} orders", va="center", fontsize=9)
ax.set_xlim(0, lr.late.max() * 1.5)
li = lr.set_index("carrier").late
ax.set_title(f"Economy shipping is late {li['Economy'] / li['Standard']:.1f}x as often as Standard")
save(fig, "chart_late_by_carrier.png")
