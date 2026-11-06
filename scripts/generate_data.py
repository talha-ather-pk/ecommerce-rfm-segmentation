"""
Generate a synthetic e-commerce dataset for "Harbor & Pine", a fictional US online
home & lifestyle store (Jan 2023 to Dec 2025).

The data is simulated, not real. Behaviour is modelled so the analysis has something
real to find, and is written down here so nothing is hidden:
  * order volume grows ~25% a year and peaks in Nov/Dec
  * customers differ in how likely they are to come back (latent loyalty)
  * delivery takes longer for regions far from the warehouse (in the Midwest)
    and for the Economy carrier; some orders arrive after the promised date
  * late deliveries lower the review score, and low scores make a customer
    less likely to order again
The raw files also contain the kind of mess real exports have (duplicate rows,
inconsistent state names, untrimmed text, a few payment mismatches, missing values),
which scripts/clean_and_load.py has to fix.

Output: data_raw/*.csv   Run: python scripts/generate_data.py (from the project root)
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw"
RAW.mkdir(exist_ok=True)

START, END = pd.Timestamp("2023-01-01"), pd.Timestamp("2025-12-31 23:59")
N_CUSTOMERS = 30_000

# --------------------------------------------------------------------------
# Geography: state, region, share of customers, extra shipping days
# --------------------------------------------------------------------------
STATES = [
    ("CA", "California", "West", 12.0, 2), ("WA", "Washington", "West", 2.5, 2),
    ("OR", "Oregon", "West", 1.4, 2), ("AZ", "Arizona", "West", 2.3, 2),
    ("CO", "Colorado", "West", 1.9, 1), ("NV", "Nevada", "West", 1.0, 2),
    ("UT", "Utah", "West", 1.0, 1),
    ("TX", "Texas", "South", 9.0, 1), ("FL", "Florida", "South", 6.8, 2),
    ("GA", "Georgia", "South", 3.3, 1), ("NC", "North Carolina", "South", 3.2, 1),
    ("VA", "Virginia", "South", 2.6, 1), ("TN", "Tennessee", "South", 2.1, 0),
    ("AL", "Alabama", "South", 1.5, 1), ("LA", "Louisiana", "South", 1.4, 1),
    ("IL", "Illinois", "Midwest", 3.9, 0), ("OH", "Ohio", "Midwest", 3.6, 0),
    ("MI", "Michigan", "Midwest", 3.0, 0), ("IN", "Indiana", "Midwest", 2.1, 0),
    ("MN", "Minnesota", "Midwest", 1.8, 0), ("WI", "Wisconsin", "Midwest", 1.8, 0),
    ("MO", "Missouri", "Midwest", 1.9, 0),
    ("NY", "New York", "Northeast", 6.0, 1), ("PA", "Pennsylvania", "Northeast", 3.9, 1),
    ("NJ", "New Jersey", "Northeast", 2.8, 1), ("MA", "Massachusetts", "Northeast", 2.1, 1),
    ("CT", "Connecticut", "Northeast", 1.1, 1), ("MD", "Maryland", "Northeast", 1.9, 1),
]
CITIES = {
    "CA": ["Los Angeles", "San Diego", "San Jose", "San Francisco", "Sacramento", "Fresno"],
    "WA": ["Seattle", "Spokane", "Tacoma"], "OR": ["Portland", "Eugene", "Salem"],
    "AZ": ["Phoenix", "Tucson", "Mesa"], "CO": ["Denver", "Colorado Springs", "Aurora"],
    "NV": ["Las Vegas", "Reno", "Henderson"], "UT": ["Salt Lake City", "Provo"],
    "TX": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "El Paso"],
    "FL": ["Miami", "Orlando", "Tampa", "Jacksonville"], "GA": ["Atlanta", "Savannah", "Augusta"],
    "NC": ["Charlotte", "Raleigh", "Greensboro"], "VA": ["Virginia Beach", "Richmond", "Arlington"],
    "TN": ["Nashville", "Memphis", "Knoxville"], "AL": ["Birmingham", "Huntsville", "Mobile"],
    "LA": ["New Orleans", "Baton Rouge"], "IL": ["Chicago", "Aurora", "Naperville"],
    "OH": ["Columbus", "Cleveland", "Cincinnati"], "MI": ["Detroit", "Grand Rapids", "Lansing"],
    "IN": ["Indianapolis", "Fort Wayne"], "MN": ["Minneapolis", "Saint Paul", "Rochester"],
    "WI": ["Milwaukee", "Madison"], "MO": ["Kansas City", "St. Louis", "Springfield"],
    "NY": ["New York", "Buffalo", "Rochester", "Albany"], "PA": ["Philadelphia", "Pittsburgh"],
    "NJ": ["Newark", "Jersey City", "Trenton"], "MA": ["Boston", "Worcester", "Cambridge"],
    "CT": ["Hartford", "New Haven", "Stamford"], "MD": ["Baltimore", "Annapolis"],
}
FIRST = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "David",
         "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas",
         "Sarah", "Daniel", "Karen", "Matthew", "Nancy", "Anthony", "Lisa", "Mark", "Betty",
         "Steven", "Sandra", "Andrew", "Ashley", "Joshua", "Emily", "Kevin", "Michelle", "Brian",
         "Amanda", "Omar", "Aisha", "Wei", "Mei", "Carlos", "Sofia", "Raj", "Priya", "Luis",
         "Maria", "Ahmed", "Fatima", "Noah", "Olivia", "Liam", "Emma", "Ethan", "Ava"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez",
        "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor",
        "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Clark",
        "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Scott", "Nguyen",
        "Hill", "Khan", "Patel", "Chen", "Kim", "Ali", "Singh", "Cohen", "Murphy", "Rivera"]

# --------------------------------------------------------------------------
# Products: category, share of orders, median price, price spread, weight (kg)
# --------------------------------------------------------------------------
CATEGORIES = [
    ("Home Decor", 0.17, 38, 0.55, 1.2), ("Kitchen & Dining", 0.16, 32, 0.6, 1.5),
    ("Bedding & Bath", 0.13, 55, 0.5, 2.0), ("Furniture", 0.08, 210, 0.55, 18.0),
    ("Lighting", 0.08, 65, 0.5, 2.5), ("Garden & Outdoor", 0.09, 48, 0.65, 4.0),
    ("Storage & Organization", 0.11, 28, 0.5, 1.8), ("Rugs & Textiles", 0.07, 95, 0.6, 5.0),
    ("Candles & Fragrance", 0.11, 18, 0.4, 0.5),
]
ADJ = ["Classic", "Modern", "Rustic", "Coastal", "Nordic", "Linen", "Oak", "Matte", "Woven",
       "Ceramic", "Brass", "Velvet", "Cotton", "Bamboo", "Marble", "Walnut", "Stoneware", "Jute"]
NOUNS = {
    "Home Decor": ["Vase", "Wall Mirror", "Picture Frame", "Throw Pillow", "Wall Art", "Clock"],
    "Kitchen & Dining": ["Dinner Plate Set", "Mug Set", "Cutting Board", "Serving Bowl",
                         "Knife Block", "Glass Tumblers", "Utensil Crock"],
    "Bedding & Bath": ["Duvet Cover", "Sheet Set", "Bath Towel Set", "Bath Mat", "Quilt",
                       "Pillowcase Pair"],
    "Furniture": ["Side Table", "Bookshelf", "Accent Chair", "Coffee Table", "Console Table",
                  "Bar Stool", "Nightstand"],
    "Lighting": ["Table Lamp", "Floor Lamp", "Pendant Light", "String Lights", "Desk Lamp"],
    "Garden & Outdoor": ["Planter", "Outdoor Cushion", "Watering Can", "Bistro Set",
                         "Garden Lantern", "Bird Feeder"],
    "Storage & Organization": ["Storage Basket", "Drawer Organizer", "Shoe Rack", "Wall Shelf",
                               "Laundry Hamper", "Storage Box Set"],
    "Rugs & Textiles": ["Area Rug", "Runner Rug", "Throw Blanket", "Curtain Panel", "Doormat"],
    "Candles & Fragrance": ["Scented Candle", "Reed Diffuser", "Candle Set", "Room Spray",
                            "Tealight Pack"],
}
COLORS = ["White", "Black", "Grey", "Sage", "Navy", "Terracotta", "Natural", "Blush", "Charcoal"]

# cost as a share of list price (gross margin differs by category)
COST_RATIO = {"Home Decor": (0.40, 0.55), "Kitchen & Dining": (0.45, 0.60), "Bedding & Bath": (0.42, 0.56),
              "Furniture": (0.58, 0.74), "Lighting": (0.48, 0.62), "Garden & Outdoor": (0.50, 0.66),
              "Storage & Organization": (0.44, 0.58), "Rugs & Textiles": (0.38, 0.52),
              "Candles & Fragrance": (0.25, 0.38)}

# Carriers: share, promised days, mean extra delay, prob of a big delay
CARRIERS = [("Standard", 0.62, 5, 0.3, 0.05), ("Express", 0.18, 2, 0.1, 0.03),
            ("Economy", 0.20, 8, 0.9, 0.13)]


def pick(items, n, p=None):
    return rng.choice(len(items), size=n, p=p)


# ---- products -------------------------------------------------------------
rows, pid = [], 1
for cat, share, median, spread, weight in CATEGORIES:
    n = int(650 * share) + 20
    for _ in range(n):
        noun = NOUNS[cat][rng.integers(len(NOUNS[cat]))]
        name = f"{ADJ[rng.integers(len(ADJ))]} {noun} - {COLORS[rng.integers(len(COLORS))]}"
        price = round(float(np.exp(np.log(median) + rng.normal(0, spread))), 2)
        price = max(price, 4.99)
        rows.append({"product_id": f"P{pid:05d}", "product_name": name, "category": cat,
                     "list_price": round(np.floor(price) + 0.99, 2),
                     "unit_cost": round(price * rng.uniform(*COST_RATIO[cat]), 2),
                     "weight_kg": round(float(weight * rng.lognormal(0, 0.35)), 2),
                     "launch_date": (START - pd.Timedelta(days=int(rng.integers(0, 700)))).date()})
        pid += 1
products = pd.DataFrame(rows)
cat_share = {c[0]: c[1] for c in CATEGORIES}
products["pick_w"] = products["category"].map(cat_share) / products.groupby("category")["category"].transform("size")
products["pick_w"] *= np.exp(-products["list_price"] / 400)        # cheaper items sell more often
products["pick_w"] *= rng.lognormal(0, 0.8, len(products))          # a few best-sellers
products["pick_w"] /= products["pick_w"].sum()

# ---- customers ------------------------------------------------------------
st_w = np.array([s[3] for s in STATES]); st_w /= st_w.sum()
st_idx = pick(STATES, N_CUSTOMERS, st_w)
# first purchase date: growth trend + Nov/Dec peak
days = pd.date_range(START, END.normalize(), freq="D")
t = np.arange(len(days)) / 365
season = 1 + 0.35 * np.isin(days.month, [11]) + 0.6 * np.isin(days.month, [12]) \
    + 0.15 * np.isin(days.month, [5, 6]) - 0.15 * np.isin(days.month, [1, 2])
bf = (days.month == 11) & (days.day >= 24) & (days.day <= 30)        # Black Friday week
day_w = (1.25 ** t) * season * np.where(bf, 2.2, 1.0) * np.where(days.day_of_week >= 5, 0.85, 1.0)
day_w /= day_w.sum()
first_day = days[rng.choice(len(days), N_CUSTOMERS, p=day_w)]

channel = rng.choice(["Organic search", "Paid social", "Email", "Referral", "Marketplace ad"],
                     N_CUSTOMERS, p=[0.34, 0.27, 0.12, 0.10, 0.17])
# latent loyalty: referral & email customers come back more, marketplace ads less
loyal_base = rng.beta(1.6, 3.2, N_CUSTOMERS)
loyal_base *= pd.Series(channel).map({"Organic search": 1.0, "Paid social": 0.85, "Email": 1.25,
                                       "Referral": 1.3, "Marketplace ad": 0.7}).to_numpy()
loyal_base = np.clip(loyal_base, 0.01, 0.92)

customers = pd.DataFrame({
    "customer_id": [f"C{i:06d}" for i in range(1, N_CUSTOMERS + 1)],
    "first_name": [FIRST[i] for i in rng.integers(len(FIRST), size=N_CUSTOMERS)],
    "last_name": [LAST[i] for i in rng.integers(len(LAST), size=N_CUSTOMERS)],
    "state_code": [STATES[i][0] for i in st_idx],
    "city": [CITIES[STATES[i][0]][rng.integers(len(CITIES[STATES[i][0]]))] for i in st_idx],
    "acquisition_channel": channel,
    "signup_date": first_day - pd.to_timedelta(rng.integers(0, 20, N_CUSTOMERS), unit="D"),
})
state_info = {s[0]: s for s in STATES}

# ---- orders, items, payments, reviews --------------------------------------
orders, items, payments, reviews = [], [], [], []
oid = 0
review_comments = {
    5: ["Love it, exactly as pictured.", "Great quality, fast delivery!", "Beautiful, will buy again.",
        "Perfect, thank you!", ""],
    4: ["Nice product, packaging could be better.", "Good value.", "Happy with it overall.", ""],
    3: ["It's okay. Colour slightly different.", "Average quality for the price.",
        "Arrived later than expected.", ""],
    2: ["Arrived late and the box was damaged.", "Not as described.", "Took far too long to arrive.",
        "Quality is poor."],
    1: ["Very late, no updates from the carrier.", "Item arrived broken.",
        "Still waiting for a refund.", "Terrible experience, won't order again."],
}
car_w = np.array([c[1] for c in CARRIERS])

for ci in range(N_CUSTOMERS):
    cid = customers.at[ci, "customer_id"]
    st = customers.at[ci, "state_code"]
    region_extra = state_info[st][4]
    loyalty = loyal_base[ci]
    when = first_day[ci] + pd.Timedelta(minutes=int(rng.integers(6 * 60, 23 * 60 + 59)))
    n_prev = 0
    while when <= END:
        oid += 1
        order_id = f"O{oid:07d}"
        carrier = CARRIERS[rng.choice(3, p=car_w)]
        # ---- items
        n_items = rng.choice([1, 2, 3, 4], p=[0.62, 0.24, 0.10, 0.04])
        prod_idx = rng.choice(len(products), n_items, replace=False, p=products["pick_w"].to_numpy())
        promo = (when.month == 11 and 24 <= when.day <= 30) or rng.random() < 0.18
        disc_rate = rng.choice([0.10, 0.15, 0.20, 0.25]) if promo else 0.0
        subtotal = 0.0
        for k, pi in enumerate(prod_idx):
            pr = products.iloc[pi]
            qty = int(rng.choice([1, 1, 1, 1, 2, 2, 3])) if pr["list_price"] < 60 else 1
            price = round(pr["list_price"] * (1 - disc_rate), 2)
            items.append({"order_id": order_id, "order_item_id": k + 1, "product_id": pr["product_id"],
                          "quantity": qty, "unit_price": price,
                          "discount_pct": int(disc_rate * 100)})
            subtotal += price * qty
        weight = float(sum(products.iloc[pi]["weight_kg"] for pi in prod_idx))
        shipping = 0.0 if subtotal >= 75 else round(5.99 + 0.6 * weight, 2)
        if carrier[0] == "Express":
            shipping = round(shipping + 9.99, 2)
        total = round(subtotal + shipping, 2)
        # ---- status & delivery
        r = rng.random()
        status = "canceled" if r < 0.022 else "delivered"
        promised_days = carrier[2] + region_extra + 2               # store pads its estimate
        est = (when + pd.Timedelta(days=promised_days)).normalize() + pd.Timedelta(hours=20)
        approved = when + pd.Timedelta(minutes=int(rng.gamma(2, 25)))
        shipped = delivered = None
        delay = 0
        if status == "delivered":
            ship_lag = rng.gamma(2, 0.6) + (1.2 if when.month == 12 else 0)
            shipped = approved + pd.Timedelta(days=float(ship_lag))
            transit = carrier[2] - 1 + 0.8 * region_extra + rng.normal(carrier[3], 0.8)
            if rng.random() < carrier[4] + (0.06 if when.month == 12 else 0):
                transit += rng.gamma(2.5, 2.5)                       # carrier problem
            delivered = shipped + pd.Timedelta(days=float(max(transit, 0.6)))
            if delivered > END:
                status, delivered = "shipped", None                   # still in transit at year end
            else:
                delay = (delivered.normalize() - est.normalize()).days
        orders.append({"order_id": order_id, "customer_id": cid, "order_status": status,
                       "order_purchase_timestamp": when, "order_approved_at": approved,
                       "order_shipped_date": shipped, "order_delivered_date": delivered,
                       "order_estimated_delivery_date": est, "carrier": carrier[0],
                       "shipping_fee": shipping, "order_total": total})
        # ---- payments
        method = rng.choice(["credit_card", "paypal", "debit_card", "gift_card"],
                            p=[0.58, 0.22, 0.15, 0.05])
        if method == "gift_card" and total > 25:
            gc = round(min(total, float(rng.choice([25, 50]))), 2)
            payments.append({"order_id": order_id, "payment_sequential": 1, "payment_type": "gift_card",
                             "payment_installments": 1, "payment_value": gc})
            if total - gc > 0:
                payments.append({"order_id": order_id, "payment_sequential": 2,
                                 "payment_type": "credit_card", "payment_installments": 1,
                                 "payment_value": round(total - gc, 2)})
        else:
            inst = int(rng.choice([1, 1, 1, 3, 4, 6])) if method == "credit_card" and total > 150 else 1
            payments.append({"order_id": order_id, "payment_sequential": 1, "payment_type": method,
                             "payment_installments": inst, "payment_value": total})
        # ---- review
        score = None
        if status == "delivered" and rng.random() < 0.82:
            mean = 4.45 if delay <= 0 else max(1.5, 4.2 - 0.38 * delay)   # drops with every day late
            if any(products.iloc[pi]["category"] == "Furniture" for pi in prod_idx):
                mean -= 0.25                                          # damage-prone
            score = int(np.clip(np.rint(rng.normal(mean, 0.85)), 1, 5))
            comment = review_comments[score][rng.integers(len(review_comments[score]))]
            created = delivered + pd.Timedelta(days=float(rng.gamma(2, 1.5)))
            reviews.append({"review_id": f"R{len(reviews) + 1:07d}", "order_id": order_id,
                            "review_score": score, "review_comment": comment or None,
                            "review_creation_date": created.normalize(),
                            "review_answer_timestamp": created + pd.Timedelta(hours=float(rng.gamma(2, 14)))})
        # ---- does the customer come back?
        p_back = loyalty * (1 + 0.08 * min(n_prev, 4))
        if status == "canceled":
            p_back *= 0.6
        if delay > 0:
            p_back *= max(0.35, 1 - 0.12 * delay)                    # late deliveries put people off
        if score is not None:
            p_back *= {1: 0.3, 2: 0.5, 3: 0.85, 4: 1.0, 5: 1.1}[score]
        if rng.random() > min(p_back, 0.93):
            break
        n_prev += 1
        gap = rng.gamma(1.4, 70 / (0.5 + loyalty))
        when = when + pd.Timedelta(days=float(max(gap, 3)), minutes=int(rng.integers(-300, 300)))

orders = pd.DataFrame(orders)
items = pd.DataFrame(items)
payments = pd.DataFrame(payments)
reviews = pd.DataFrame(reviews)

# --------------------------------------------------------------------------
# Real-world mess (documented, fixed by clean_and_load.py)
# --------------------------------------------------------------------------
n = len(customers)
m = rng.random(n) < 0.06                                              # full state names
customers.loc[m, "state_code"] = customers.loc[m, "state_code"].map(lambda s: state_info[s][1])
m = rng.random(n) < 0.03                                              # lower-case codes
customers.loc[m, "state_code"] = customers.loc[m, "state_code"].str.lower()
m = rng.random(n) < 0.05                                              # untidy city text
customers.loc[m, "city"] = "  " + customers.loc[m, "city"].str.upper() + " "
m = rng.random(n) < 0.02
customers.loc[m, "acquisition_channel"] = None

dup = items.sample(frac=0.004, random_state=SEED)                    # duplicated export rows
items = pd.concat([items, dup]).sort_values(["order_id", "order_item_id"]).reset_index(drop=True)
dup = reviews.sample(n=120, random_state=SEED)
reviews = pd.concat([reviews, dup]).reset_index(drop=True)

bad = payments.sample(n=40, random_state=SEED).index                 # payment does not match total
payments.loc[bad, "payment_value"] = (payments.loc[bad, "payment_value"] *
                                      rng.uniform(0.5, 0.95, len(bad))).round(2)
m = rng.random(len(products)) < 0.015
products.loc[m, "weight_kg"] = np.nan
m = rng.random(len(products)) < 0.03
products.loc[m, "category"] = products.loc[m, "category"].str.lower()

# timestamps as text, as an export would give them
fmt = "%Y-%m-%d %H:%M:%S"
for c in ["order_purchase_timestamp", "order_approved_at", "order_shipped_date",
          "order_delivered_date", "order_estimated_delivery_date"]:
    orders[c] = pd.to_datetime(orders[c]).dt.strftime(fmt)
reviews["review_answer_timestamp"] = pd.to_datetime(reviews["review_answer_timestamp"]).dt.strftime(fmt)
customers["signup_date"] = customers["signup_date"].dt.strftime("%Y-%m-%d")

files = {"customers": customers, "products": products.drop(columns="pick_w"), "orders": orders,
         "order_items": items, "payments": payments, "reviews": reviews}
for name, df in files.items():
    df.to_csv(RAW / f"{name}.csv", index=False)
    print(f"wrote data_raw/{name}.csv  ({len(df):,} rows)")
