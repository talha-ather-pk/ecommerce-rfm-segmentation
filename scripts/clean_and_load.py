"""
Harbor & Pine: clean the raw export, validate it, and load it into SQLite + star-schema CSVs.

Input : data_raw/*.csv  (from generate_data.py)
Output: data_clean/harbor_pine.db  (SQLite, clean tables for the SQL analysis)
        data_clean/fact_orders.csv, fact_order_items.csv, dim_customer.csv, dim_product.csv,
        dim_date.csv, data_quality_log.csv  (for Power BI)
Run   : python scripts/clean_and_load.py   (from the project root)
"""
from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data_raw", ROOT / "data_clean"
OUT.mkdir(exist_ok=True)
log = []


def note(table, check, n, action):
    log.append({"table": table, "check": check, "rows_affected": int(n), "action": action})
    print(f"[DQ] {table:<12} {check}: {n:,} -> {action}")


STATES = {  # code: (name, region)
    "CA": ("California", "West"), "WA": ("Washington", "West"), "OR": ("Oregon", "West"),
    "AZ": ("Arizona", "West"), "CO": ("Colorado", "West"), "NV": ("Nevada", "West"),
    "UT": ("Utah", "West"), "TX": ("Texas", "South"), "FL": ("Florida", "South"),
    "GA": ("Georgia", "South"), "NC": ("North Carolina", "South"), "VA": ("Virginia", "South"),
    "TN": ("Tennessee", "South"), "AL": ("Alabama", "South"), "LA": ("Louisiana", "South"),
    "IL": ("Illinois", "Midwest"), "OH": ("Ohio", "Midwest"), "MI": ("Michigan", "Midwest"),
    "IN": ("Indiana", "Midwest"), "MN": ("Minnesota", "Midwest"), "WI": ("Wisconsin", "Midwest"),
    "MO": ("Missouri", "Midwest"), "NY": ("New York", "Northeast"), "PA": ("Pennsylvania", "Northeast"),
    "NJ": ("New Jersey", "Northeast"), "MA": ("Massachusetts", "Northeast"),
    "CT": ("Connecticut", "Northeast"), "MD": ("Maryland", "Northeast"),
}
NAME_TO_CODE = {v[0].upper(): k for k, v in STATES.items()}
CATEGORIES = ["Home Decor", "Kitchen & Dining", "Bedding & Bath", "Furniture", "Lighting",
              "Garden & Outdoor", "Storage & Organization", "Rugs & Textiles", "Candles & Fragrance"]

cust = pd.read_csv(RAW / "customers.csv")
prod = pd.read_csv(RAW / "products.csv")
orders = pd.read_csv(RAW / "orders.csv")
items = pd.read_csv(RAW / "order_items.csv")
pay = pd.read_csv(RAW / "payments.csv")
rev = pd.read_csv(RAW / "reviews.csv")
for name, df in [("customers", cust), ("products", prod), ("orders", orders),
                 ("order_items", items), ("payments", pay), ("reviews", rev)]:
    note(name, "rows loaded", len(df), "none")

# ---- customers ------------------------------------------------------------
raw_state = cust["state_code"].astype(str).str.strip()
std = raw_state.str.upper().map(lambda s: s if s in STATES else NAME_TO_CODE.get(s))
note("customers", "state given as full name or lower case", (raw_state != std).sum(),
     "standardised to 2-letter code")
assert std.notna().all(), "unknown state value"
cust["state_code"] = std
city_clean = cust["city"].str.strip().str.title()
note("customers", "city with extra spaces or wrong case", (cust["city"] != city_clean).sum(),
     "trimmed and title-cased")
cust["city"] = city_clean
note("customers", "missing acquisition_channel", cust["acquisition_channel"].isna().sum(),
     "set to 'Unknown'")
cust["acquisition_channel"] = cust["acquisition_channel"].fillna("Unknown")
cust["state_name"] = cust["state_code"].map(lambda s: STATES[s][0])
cust["region"] = cust["state_code"].map(lambda s: STATES[s][1])
cust["signup_date"] = pd.to_datetime(cust["signup_date"])
note("customers", "duplicate customer_id", cust["customer_id"].duplicated().sum(), "checked")

# ---- products -------------------------------------------------------------
canon = {c.lower(): c for c in CATEGORIES}
fixed = prod["category"].str.strip().str.lower().map(canon)
note("products", "category in wrong case", (prod["category"] != fixed).sum(), "mapped to standard names")
prod["category"] = fixed
note("products", "missing weight_kg", prod["weight_kg"].isna().sum(), "filled with category median")
prod["weight_kg"] = prod.groupby("category")["weight_kg"].transform(lambda s: s.fillna(s.median()))

# ---- orders ---------------------------------------------------------------
ts_cols = ["order_purchase_timestamp", "order_approved_at", "order_shipped_date",
           "order_delivered_date", "order_estimated_delivery_date"]
for c in ts_cols:
    orders[c] = pd.to_datetime(orders[c], format="%Y-%m-%d %H:%M:%S", errors="coerce")
note("orders", "unparseable purchase timestamp", orders["order_purchase_timestamp"].isna().sum(), "checked")
bad_seq = orders["order_delivered_date"] < orders["order_purchase_timestamp"]
note("orders", "delivered before purchase", bad_seq.sum(), "checked")
deliv = orders["order_status"].eq("delivered")
note("orders", "delivered orders missing delivery date",
     (deliv & orders["order_delivered_date"].isna()).sum(), "checked")
orders["delivery_days"] = (orders["order_delivered_date"] - orders["order_purchase_timestamp"]).dt.total_seconds() / 86400
orders["delay_days"] = (orders["order_delivered_date"].dt.normalize()
                        - orders["order_estimated_delivery_date"].dt.normalize()).dt.days
orders["is_late"] = orders["delay_days"] > 0
note("orders", "delivered after the promised date", orders["is_late"].sum(),
     "kept, flagged is_late with delay_days")
note("orders", "canceled orders", orders["order_status"].eq("canceled").sum(),
     "kept, excluded from revenue and RFM")
note("orders", "orders still in transit at 31 Dec 2025", orders["order_status"].eq("shipped").sum(),
     "kept, counted as revenue, no delivery metrics")

# ---- order items ----------------------------------------------------------
d = items.duplicated()
note("order_items", "duplicated export rows", d.sum(), "dropped")
items = items[~d].copy()
note("order_items", "duplicate (order_id, order_item_id)",
     items.duplicated(["order_id", "order_item_id"]).sum(), "checked")
items["line_revenue"] = (items["quantity"] * items["unit_price"]).round(2)
items = items.merge(prod[["product_id", "unit_cost"]], on="product_id", how="left")
note("order_items", "product_id not in products", items["unit_cost"].isna().sum(), "checked")
items["line_cost"] = (items["quantity"] * items["unit_cost"]).round(2)
items["line_margin"] = (items["line_revenue"] - items["line_cost"]).round(2)

# order total = items + shipping?
it_sum = items.groupby("order_id")["line_revenue"].sum()
chk = orders.set_index("order_id")
diff = (it_sum.reindex(chk.index).fillna(0) + chk["shipping_fee"] - chk["order_total"]).abs()
note("orders", "order_total differs from items + shipping (> $0.05)", (diff > 0.05).sum(), "checked")

# ---- payments -------------------------------------------------------------
paid = pay.groupby("order_id")["payment_value"].sum()
pdiff = (paid.reindex(chk.index).fillna(0) - chk["order_total"]).round(2)
mismatch = pdiff.abs() > 0.05
note("payments", "payments do not add up to order_total", mismatch.sum(),
     "kept, flagged payment_mismatch for finance follow-up")
orders["payment_mismatch"] = orders["order_id"].map(mismatch).fillna(False).astype(bool)
orders["amount_paid"] = orders["order_id"].map(paid).round(2)
orders["payment_type"] = orders["order_id"].map(
    pay.sort_values("payment_value", ascending=False).drop_duplicates("order_id")
       .set_index("order_id")["payment_type"])

# ---- reviews --------------------------------------------------------------
d = rev.duplicated()
note("reviews", "duplicated export rows", d.sum(), "dropped")
rev = rev[~d].copy()
note("reviews", "more than one review per order", rev["order_id"].duplicated().sum(), "checked")
note("reviews", "review without a comment", rev["review_comment"].isna().sum(), "kept (score only)")
rev["review_creation_date"] = pd.to_datetime(rev["review_creation_date"])
orders = orders.merge(rev[["order_id", "review_score"]], on="order_id", how="left")

# ---- derived order columns -------------------------------------------------
agg = items.groupby("order_id").agg(items_count=("quantity", "sum"), lines=("order_item_id", "count"),
                                    items_revenue=("line_revenue", "sum"), items_margin=("line_margin", "sum"),
                                    max_discount_pct=("discount_pct", "max"))
orders = orders.merge(agg, on="order_id", how="left")
orders = orders.sort_values(["customer_id", "order_purchase_timestamp"])
valid = orders["order_status"] != "canceled"
orders["customer_order_number"] = (orders[valid].groupby("customer_id").cumcount() + 1).astype("Int64")
orders["customer_has_repeat"] = orders["customer_id"].map(orders[valid].groupby("customer_id").size() > 1) \
    .fillna(False).astype(bool)
orders["is_first_order"] = orders["customer_order_number"].eq(1)
orders["order_date"] = orders["order_purchase_timestamp"].dt.normalize()
orders["delivery_band"] = pd.cut(orders["delay_days"], [-99, 0, 3, 7, 99],
                                 labels=["On time", "1-3 days late", "4-7 days late", "8+ days late"])
orders["delivery_band_order"] = orders["delivery_band"].cat.codes.where(orders["delivery_band"].notna()).add(1).astype("Int64")

# ---- SQLite ---------------------------------------------------------------
db = OUT / "harbor_pine.db"
db.unlink(missing_ok=True)
with sqlite3.connect(db) as con:
    def put(name, df):
        df = df.copy()
        for c in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[c]):
                df[c] = df[c].dt.strftime("%Y-%m-%d %H:%M:%S")
        df.to_sql(name, con, index=False)
    put("customers", cust)
    put("products", prod)
    put("orders", orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp",
                          "order_approved_at", "order_shipped_date", "order_delivered_date",
                          "order_estimated_delivery_date", "carrier", "shipping_fee", "order_total",
                          "delay_days", "is_late", "payment_mismatch"]])
    put("order_items", items[["order_id", "order_item_id", "product_id", "quantity", "unit_price",
                              "discount_pct", "line_revenue", "line_cost", "line_margin"]])
    put("payments", pay)
    put("reviews", rev)
    con.executescript("""
        CREATE INDEX ix_orders_customer ON orders(customer_id);
        CREATE INDEX ix_items_order ON order_items(order_id);
        CREATE INDEX ix_pay_order ON payments(order_id);
        CREATE INDEX ix_rev_order ON reviews(order_id);
    """)
print(f"wrote {db.relative_to(ROOT)}")

# ---- star schema CSVs for Power BI -----------------------------------------
fact_orders = orders[["order_id", "customer_id", "order_date", "order_status", "carrier", "payment_type",
                      "order_total", "shipping_fee", "items_revenue", "items_margin", "items_count",
                      "max_discount_pct", "delivery_days", "delay_days", "is_late", "delivery_band", "delivery_band_order",
                      "review_score", "customer_order_number", "is_first_order", "customer_has_repeat",
                      "payment_mismatch"]]
fact_items = items.merge(orders[["order_id", "customer_id", "order_date", "order_status"]], on="order_id")
fact_items = fact_items[["order_id", "order_item_id", "customer_id", "product_id", "order_date",
                         "order_status", "quantity", "unit_price", "discount_pct", "line_revenue",
                         "line_cost", "line_margin"]]
dim_customer = cust[["customer_id", "city", "state_code", "state_name", "region",
                     "acquisition_channel", "signup_date"]]
dim_product = prod[["product_id", "product_name", "category", "list_price", "unit_cost", "weight_kg"]]
dates = pd.date_range("2023-01-01", "2025-12-31", freq="D")
dim_date = pd.DataFrame({"date": dates, "year": dates.year, "quarter": "Q" + dates.quarter.astype(str),
                         "month_num": dates.month, "month": dates.strftime("%b"),
                         "year_month": dates.strftime("%Y-%m"), "weekday": dates.strftime("%a")})
for name, df in {"fact_orders": fact_orders, "fact_order_items": fact_items, "dim_customer": dim_customer,
                 "dim_product": dim_product, "dim_date": dim_date}.items():
    df.to_csv(OUT / f"{name}.csv", index=False, date_format="%Y-%m-%d")
    print(f"wrote data_clean/{name}.csv  ({len(df):,} rows)")
pd.DataFrame(log).to_csv(OUT / "data_quality_log.csv", index=False)

rev_orders = orders[orders["order_status"] != "canceled"]
print(f"\nRevenue (excl. canceled): {rev_orders['order_total'].sum():,.2f}")
print(f"Orders (excl. canceled) : {len(rev_orders):,}")
print(f"Customers with an order : {rev_orders['customer_id'].nunique():,}")
