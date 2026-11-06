"""
Harbor & Pine: generate the executive Power BI dashboard as a Power BI Project (PBIP).

Writes powerbi/HarborPine.pbip:
  HarborPine.SemanticModel/  star schema (2 facts, 3 conformed dimensions, measures table) in TMDL
  HarborPine.Report/         custom theme, sidebar navigation, 4 report pages, a drill-through page
                             and a tooltip page (PBIR JSON)

Open the .pbip in Power BI Desktop (Nov 2025 release or later) and click Refresh.
Run: python scripts/build_pbip.py   (from the project root)
"""
import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
NAME = "HarborPine"
SM = PBI / f"{NAME}.SemanticModel"
RP = PBI / f"{NAME}.Report"
DATA_FOLDER = str(ROOT / "data_clean") + "\\"
BASE_THEME = "CY26SU04"
THEME_SRC = Path(r"C:\Program Files\Microsoft Power BI Desktop\bin\WebView2Resources"
                 r"\minerva\sharedresources\BaseThemes") / f"{BASE_THEME}.json"
CUSTOM_THEME = "HarborPine_Executive.json"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
V_VISUAL, V_PAGE, V_REPORT = "2.4.0", "2.0.0", "3.0.0"

# =========================================================================
# Design system
# =========================================================================
NAVY = "#0B1F3A"        # sidebar, primary text on light
NAVY_2 = "#16314F"      # active nav item
INK = "#0F172A"
SLATE = "#64748B"
SLATE_2 = "#94A3B8"
MIST = "#CBD5E1"
LINE = "#E6E9F0"
CANVAS = "#F3F5F9"
WHITE = "#FFFFFF"
GOLD = "#C8A24A"
PRIMARY = "#1F4E79"     # main series
COMPARE = "#B8C2CF"     # prior year / comparison series
GOOD, WARN, BAD, NEUTRAL = "#0E7C86", "#D08C2E", "#B5523B", "#94A3B8"
DATA_COLORS = [PRIMARY, GOOD, GOLD, "#7A8CA5", BAD, "#5B8E7D", "#8C6BB1", WARN]
FONT, FONT_SB, FONT_LIGHT = "Segoe UI", "Segoe UI Semibold", "Segoe UI Light"


def gid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "harborpine-v2/" + "/".join(parts)))


def hid(*parts):
    return gid(*parts).replace("-", "")[:20]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path, obj):
    write(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


# =========================================================================
# Semantic model
# =========================================================================
S, I, D, DT, B = "string", "int64", "double", "dateTime", "boolean"
MTYPE = {S: "type text", I: "Int64.Type", D: "type number", DT: "type date", B: "logical"}


def cols(*spec):
    """(name, type[, hidden[, extra]]) -> column tuples. Every column summarizeBy none."""
    out = []
    for name, dtype, *rest in spec:
        hidden = bool(rest and rest[0])
        extra = dict(rest[1]) if len(rest) > 1 else {}
        if dtype == DT:
            extra.setdefault("formatString", "dd mmm yyyy")
        out.append((name, dtype, hidden, extra))
    return out


# columns loaded from CSV (source) and columns added in Power Query (derived)
TABLES = {
    "fact_orders": cols(
        ("order_id", S), ("customer_id", S, True), ("order_date", DT, True), ("order_status", S),
        ("carrier", S), ("payment_type", S), ("order_total", D, True), ("shipping_fee", D, True),
        ("items_revenue", D, True), ("items_margin", D, True), ("items_count", I, True),
        ("max_discount_pct", I, True), ("delivery_days", D, True), ("delay_days", I, True),
        ("is_late", B, True), ("delivery_band", S, False, {"sortByColumn": "delivery_band_order"}),
        ("delivery_band_order", I, True), ("review_score", I, True),
        ("customer_order_number", I, True), ("is_first_order", B, True),
        ("customer_has_repeat", B, True), ("payment_mismatch", B, True)),
    "fact_order_items": cols(
        ("order_id", S, True), ("order_item_id", I, True), ("customer_id", S, True),
        ("product_id", S, True), ("order_date", DT, True), ("order_status", S, True),
        ("quantity", I, True), ("unit_price", D, True), ("discount_pct", I, True),
        ("line_revenue", D, True), ("line_cost", D, True), ("line_margin", D, True)),
    "dim_customer": cols(
        ("customer_id", S, True), ("city", S), ("state_code", S),
        ("state_name", S, False, {"dataCategory": "StateOrProvince"}), ("region", S),
        ("acquisition_channel", S), ("signup_date", DT, True)),
    "dim_product": cols(
        ("product_id", S, True), ("product_name", S), ("category", S), ("list_price", D, True),
        ("unit_cost", D, True), ("weight_kg", D, True)),
    "dim_date": cols(
        ("date", DT, False, {"isKey": None}), ("year", I), ("quarter", S), ("month_num", I, True),
        ("month", S, False, {"sortByColumn": "month_num"}), ("year_month", S, True), ("weekday", S, True)),
}
DERIVED = {
    # RFM attributes merged onto the customer dimension (one row per customer, star schema)
    "dim_customer": cols(
        ("recency_days", I, True), ("frequency", I, True), ("monetary", D, True),
        ("r_score", I), ("f_score", I), ("m_score", I), ("rfm_code", S, True),
        ("segment_order", I, True), ("segment", S, False, {"sortByColumn": "segment_order"})),
    "dim_date": cols(
        ("month_start", DT, False, {"formatString": "mmm yyyy"}), ("month_key", I, True),
        ("month_label", S, False, {"sortByColumn": "month_key"})),
}
RFM_COLS = ["recency_days", "frequency", "monetary", "r_score", "f_score", "m_score", "rfm_code",
            "segment_order", "segment"]

RELATIONSHIPS = [
    ("fact_orders", "order_date", "dim_date", "date"),
    ("fact_orders", "customer_id", "dim_customer", "customer_id"),
    ("fact_order_items", "order_date", "dim_date", "date"),
    ("fact_order_items", "customer_id", "dim_customer", "customer_id"),
    ("fact_order_items", "product_id", "dim_product", "product_id"),
]

# ---------------------------------------------------------------- measures
CUR, CUR2, PCT, INT, DEC1, DEC2 = (r"\$#,0;(\$#,0);\$#,0", r"\$#,0.00;(\$#,0.00);\$#,0.00",
                                   "0.0%;-0.0%;0.0%", "#,0", "#,0.0", "#,0.00")
NOT_CANCELED = 'fact_orders[order_status] <> "canceled"'
DELIVERED = 'fact_orders[order_status] = "delivered"'
ITEM_OK = 'fact_order_items[order_status] <> "canceled"'
SCORED = "dim_customer[segment_order] <= 8"

MEASURES = []   # (name, dax, format, folder, hidden)


def m(name, dax, fmt=None, folder="", hidden=False):
    MEASURES.append((name, dax, fmt, folder, hidden))


# Sales ------------------------------------------------------------------
m("Revenue", f"CALCULATE ( SUM ( fact_orders[order_total] ), {NOT_CANCELED} )", CUR, "1 Sales")
m("Orders", f"CALCULATE ( COUNTROWS ( fact_orders ), {NOT_CANCELED} )", INT, "1 Sales")
m("Customers", f"CALCULATE ( DISTINCTCOUNT ( fact_orders[customer_id] ), {NOT_CANCELED} )", INT, "1 Sales")
m("Avg Order Value", "DIVIDE ( [Revenue], [Orders] )", CUR2, "1 Sales")
m("Canceled Orders", 'CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[order_status] = "canceled" )',
  INT, "1 Sales")
m("Revenue PY", "CALCULATE ( [Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )", CUR, "1 Sales")
m("Revenue YoY %", "DIVIDE ( [Revenue] - [Revenue PY], [Revenue PY] )", PCT, "1 Sales")
m("Revenue YTD", "TOTALYTD ( [Revenue], dim_date[date] )", CUR, "1 Sales")
m("Revenue Rolling 3M",
  "CALCULATE ( [Revenue], DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -3, MONTH ) )", CUR, "1 Sales")
m("Revenue Share of Total",
  "DIVIDE ( [Revenue], CALCULATE ( [Revenue], REMOVEFILTERS ( dim_customer[region] ) ) )", PCT, "1 Sales")
# Customers --------------------------------------------------------------
m("Repeat Customers", "COUNTROWS ( FILTER ( VALUES ( fact_orders[customer_id] ), [Orders] > 1 ) )",
  INT, "2 Customers")
m("Repeat Rate %", "DIVIDE ( [Repeat Customers], [Customers] )", PCT, "2 Customers")
m("Came Back %",
  f"VAR FirstOrders = CALCULATETABLE ( fact_orders, fact_orders[is_first_order] = TRUE (), {DELIVERED}, "
  "fact_orders[order_date] < DATE ( 2025, 7, 1 ) ) "
  "RETURN DIVIDE ( COUNTROWS ( FILTER ( FirstOrders, fact_orders[customer_has_repeat] = TRUE () ) ), "
  "COUNTROWS ( FirstOrders ) )", PCT, "2 Customers")
# RFM (lifetime, from the customer dimension) ---------------------------
m("Scored Customers", f"CALCULATE ( COUNTROWS ( dim_customer ), {SCORED} )", INT, "3 RFM")
m("Lifetime Revenue", f"CALCULATE ( SUM ( dim_customer[monetary] ), {SCORED} )", CUR, "3 RFM")
m("% of Customers",
  "DIVIDE ( [Scored Customers], CALCULATE ( [Scored Customers], "
  "REMOVEFILTERS ( dim_customer[segment], dim_customer[segment_order] ) ) )", PCT, "3 RFM")
m("% of Revenue",
  "DIVIDE ( [Lifetime Revenue], CALCULATE ( [Lifetime Revenue], "
  "REMOVEFILTERS ( dim_customer[segment], dim_customer[segment_order] ) ) )", PCT, "3 RFM")
m("Avg Recency Days", f"CALCULATE ( AVERAGE ( dim_customer[recency_days] ), {SCORED} )", "#,0", "3 RFM")
m("Avg Orders per Customer", f"CALCULATE ( AVERAGE ( dim_customer[frequency] ), {SCORED} )", DEC2, "3 RFM")
m("Avg Lifetime Spend", "DIVIDE ( [Lifetime Revenue], [Scored Customers] )", CUR, "3 RFM")
m("Top Segments Revenue Share",
  'CALCULATE ( [% of Revenue], dim_customer[segment] IN { "Champions", "Loyal" } )', PCT, "3 RFM")
# Delivery & reviews -----------------------------------------------------
m("Delivered Orders", f"CALCULATE ( COUNTROWS ( fact_orders ), {DELIVERED} )", INT, "4 Delivery")
m("Late Orders", f"CALCULATE ( COUNTROWS ( fact_orders ), {DELIVERED}, fact_orders[is_late] = TRUE () )",
  INT, "4 Delivery")
m("Late Rate %", "DIVIDE ( [Late Orders], [Delivered Orders] )", PCT, "4 Delivery")
m("Avg Delivery Days", f"CALCULATE ( AVERAGE ( fact_orders[delivery_days] ), {DELIVERED} )", DEC1, "4 Delivery")
m("Avg Review Score", "AVERAGE ( fact_orders[review_score] )", DEC2, "4 Delivery")
m("Low Reviews %",
  "DIVIDE ( CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[review_score] <= 2, "
  "NOT ISBLANK ( fact_orders[review_score] ) ), "
  "CALCULATE ( COUNTROWS ( fact_orders ), NOT ISBLANK ( fact_orders[review_score] ) ) )", PCT, "4 Delivery")
m("Payment Mismatches", "CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[payment_mismatch] = TRUE () )",
  INT, "4 Delivery")
# Products ---------------------------------------------------------------
m("Item Revenue", f"CALCULATE ( SUM ( fact_order_items[line_revenue] ), {ITEM_OK} )", CUR, "5 Products")
m("Gross Margin", f"CALCULATE ( SUM ( fact_order_items[line_margin] ), {ITEM_OK} )", CUR, "5 Products")
m("Gross Margin %", "DIVIDE ( [Gross Margin], [Item Revenue] )", PCT, "5 Products")
m("Units Sold", f"CALCULATE ( SUM ( fact_order_items[quantity] ), {ITEM_OK} )", INT, "5 Products")
m("Item Revenue PY", "CALCULATE ( [Item Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )", CUR, "5 Products")
m("Category Revenue Share",
  "DIVIDE ( [Item Revenue], CALCULATE ( [Item Revenue], REMOVEFILTERS ( dim_product ) ) )", PCT, "5 Products")
m("Product Rank",
  "IF ( ISINSCOPE ( dim_product[product_name] ), "
  "RANKX ( ALLSELECTED ( dim_product[product_name], dim_product[category] ), [Item Revenue], , DESC, DENSE ) )", "#,0", "5 Products")

# Year-over-year comparison for KPI tiles ----------------------------------
# Compares the LATEST year in the current selection with the year before it, so the tile
# says exactly which years it compares ("▲ 32.2%  2025 vs 2024").
m("Selected Year", "MAX ( dim_date[year] )", "0", "9 Helpers", hidden=True)
COMPARE_KPIS = [  # (measure, kind, lower is better, unit)
    ("Revenue", "pct", False, ""), ("Orders", "pct", False, ""), ("Customers", "pct", False, ""),
    ("Avg Order Value", "pct", False, ""), ("Repeat Rate %", "pts", False, ""),
    ("Late Rate %", "pts", True, ""), ("Avg Delivery Days", "abs", True, " days"),
    ("Avg Review Score", "abs", False, ""), ("Low Reviews %", "pts", True, ""),
    ("Item Revenue", "pct", False, ""), ("Gross Margin", "pct", False, ""),
    ("Gross Margin %", "pts", False, ""), ("Units Sold", "pct", False, ""),
]
for base, kind, lower_better, unit in COMPARE_KPIS:
    cur, prev = f"{base} (Latest Year)", f"{base} (Prior Year)"
    m(cur, f"VAR y = [Selected Year] RETURN CALCULATE ( [{base}], REMOVEFILTERS ( dim_date ), dim_date[year] = y )",
      None, "6 Year over year", hidden=True)
    m(prev, f"VAR y = [Selected Year] - 1 RETURN CALCULATE ( [{base}], REMOVEFILTERS ( dim_date ), dim_date[year] = y )",
      None, "6 Year over year", hidden=True)
    if kind == "pct":
        delta, fmt = f"DIVIDE ( [{cur}] - [{prev}], [{prev}] )", "▲ 0.0%;▼ 0.0%;● 0.0%"
    elif kind == "pts":
        delta, fmt = f"( [{cur}] - [{prev}] ) * 100", "▲ 0.0 pts;▼ 0.0 pts;● 0.0 pts"
    else:
        delta = f"[{cur}] - [{prev}]"
        fmt = ("▲ 0.00;▼ 0.00;● 0.00" if not unit else f"▲ 0.0{unit};▼ 0.0{unit};● 0.0{unit}")
    m(f"{base} vs PY", delta, PCT if kind == "pct" else DEC1, "6 Year over year")
    m(f"{base} vs PY Label",
      f'IF ( ISBLANK ( [{prev}] ) || ISBLANK ( [{cur}] ), "No prior year to compare", '
      f'FORMAT ( [{base} vs PY], "{fmt}" ) & "   " & [Selected Year] & " vs " & ( [Selected Year] - 1 ) )',
      None, "6 Year over year")
    good, bad = (BAD, GOOD) if lower_better else (GOOD, BAD)
    m(f"{base} vs PY Color",
      f'IF ( ISBLANK ( [{prev}] ) || ISBLANK ( [{cur}] ), "{NEUTRAL}", '
      f'IF ( [{base} vs PY] >= 0, "{good}", "{bad}" ) )', None, "8 Formatting", hidden=True)
m("Item Revenue Change vs PY", "[Item Revenue (Latest Year)] - [Item Revenue (Prior Year)]", CUR,
  "6 Year over year")

# Dynamic text -----------------------------------------------------------
def _sel(colref, all_text):
    return (f'IF ( ISFILTERED ( {colref} ), CONCATENATEX ( VALUES ( {colref} ), {colref}, ", ", {colref}, ASC ), '
            f'"{all_text}" )')


m("Filter Context",
  f'{_sel("dim_date[year]", "2023 – 2025")} & "   ·   " & {_sel("dim_customer[region]", "All regions")} & '
  f'"   ·   " & {_sel("dim_customer[acquisition_channel]", "All channels")} & "   ·   " & '
  f'{_sel("dim_customer[segment]", "All segments")}', None, "7 Dynamic text")
m("Blank Text", '""', None, "9 Helpers", hidden=True)
m("Note Lifetime", '"Lifetime, to Dec 2025"', None, "9 Helpers", hidden=True)
m("Note First Orders", '"First orders before Jul 2025"', None, "9 Helpers", hidden=True)
m("Note Share", '"Of all product revenue"', None, "9 Helpers", hidden=True)
m("Title Trend",
  '"Revenue by month vs prior year   ·   " & [Revenue vs PY Label]', None, "7 Dynamic text")
m("Title Waterfall",
  '"What moved revenue in " & [Selected Year] & "?  Change vs " & ( [Selected Year] - 1 ) & " by category"',
  None, "7 Dynamic text")
m("Title Category",
  'SELECTEDVALUE ( dim_product[category], "Multiple categories" ) & "  ·  category detail"', None, "7 Dynamic text")
m("Title Category Trend",
  '"Monthly revenue: " & SELECTEDVALUE ( dim_product[category], "selected categories" ) & " vs prior year"',
  None, "7 Dynamic text")
m("Title Tooltip", 'FORMAT ( MAX ( dim_date[month_start] ), "mmmm yyyy" )', None, "7 Dynamic text")

# Conditional formatting ---------------------------------------------------
m("Review Color", f'SWITCH ( TRUE (), ISBLANK ( [Avg Review Score] ), "{NEUTRAL}", [Avg Review Score] < 3, '
  f'"{BAD}", [Avg Review Score] < 4, "{WARN}", "{GOOD}" )', None, "8 Formatting", hidden=True)
m("Came Back Color", f'SWITCH ( TRUE (), [Came Back %] < 0.15, "{BAD}", [Came Back %] < 0.27, "{WARN}", '
  f'"{GOOD}" )', None, "8 Formatting", hidden=True)
m("Late Color", f'SWITCH ( TRUE (), [Late Rate %] >= 0.2, "{BAD}", [Late Rate %] >= 0.12, "{WARN}", '
  f'"{GOOD}" )', None, "8 Formatting", hidden=True)
m("Late Heat", 'SWITCH ( TRUE (), ISBLANK ( [Late Rate %] ), BLANK (), [Late Rate %] >= 0.2, "#F3D7CF", '
  '[Late Rate %] >= 0.12, "#F7E6CC", "#D3ECEE" )', None, "8 Formatting", hidden=True)
m("Margin Color", f'SWITCH ( TRUE (), [Gross Margin %] < 0.4, "{BAD}", [Gross Margin %] < 0.47, "{WARN}", '
  f'"{GOOD}" )', None, "8 Formatting", hidden=True)
m("YoY Color", f'SWITCH ( TRUE (), ISBLANK ( [Revenue vs PY] ), "{NEUTRAL}", [Revenue vs PY] >= 0, "{GOOD}", '
  f'"{BAD}" )', None, "8 Formatting", hidden=True)
m("Item YoY Color", f'SWITCH ( TRUE (), ISBLANK ( [Item Revenue vs PY] ), "{NEUTRAL}", [Item Revenue vs PY] >= 0, '
  f'"{GOOD}", "{BAD}" )', None, "8 Formatting", hidden=True)
m("RF Heat", 'VAR v = [Avg Lifetime Spend] RETURN SWITCH ( TRUE (), ISBLANK ( v ), BLANK (), v >= 700, "#0B1F3A", '
  'v >= 400, "#1F4E79", v >= 250, "#5C88B5", v >= 150, "#B7CCE3", "#EAF0F7" )', None, "8 Formatting", hidden=True)
m("RF Heat Font", 'IF ( [Avg Lifetime Spend] >= 250, "#FFFFFF", "#0F172A" )', None, "8 Formatting", hidden=True)


def q(name):
    return name if name.replace("_", "").isalnum() else f"'{name}'"


def col_tmdl(table, name, dtype, hidden, extra):
    out = [f"\tcolumn {q(name)}", f"\t\tdataType: {dtype}"]
    if hidden:
        out.append("\t\tisHidden")
    for k, v in extra.items():
        out.append(f"\t\t{k}" if v is None else f"\t\t{k}: {v}")
    if dtype == I and "formatString" not in extra:
        out.append("\t\tformatString: 0")
    out += [f"\t\tlineageTag: {gid(table, name)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {name}",
            "", "\t\tannotation SummarizationSetBy = User", ""]
    return out


def m_csv(table, columns):
    types = ", ".join(f'{{"{n}", {MTYPE[t]}}}' for n, t, _, _ in columns if t != B)
    bools = [n for n, t, _, _ in columns if t == B]
    steps = [
        f'Source = Csv.Document(File.Contents(DataFolder & "{table}.csv"), '
        '[Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv])',
        "Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])",
        'Blanks = Table.TransformColumns(Promoted, {}, each if _ = "" then null else _)',
        f'Typed = Table.TransformColumnTypes(Blanks, {{{types}}}, "en-US")',
    ]
    last = "Typed"
    if bools:
        conv = ", ".join(f'{{"{b}", each if _ = null then null else _ = "True", type logical}}' for b in bools)
        steps.append(f"Logicals = Table.TransformColumns(Typed, {{{conv}}})")
        last = "Logicals"
    return steps, last


def m_partition(table):
    steps, last = m_csv(table, TABLES[table])
    if table == "dim_customer":
        rfm_types = {c: t for c, t, _, _ in DERIVED["dim_customer"]}
        names = ", ".join(f'"{c}"' for c in RFM_COLS)
        types = ", ".join(f'{{"{c}", {MTYPE[rfm_types[c]]}}}' for c in RFM_COLS)
        steps += [
            f'Joined = Table.NestedJoin({last}, {{"customer_id"}}, RFM_Staging, {{"customer_id"}}, "rfm", '
            "JoinKind.LeftOuter)",
            f"Expanded = Table.ExpandTableColumn(Joined, \"rfm\", {{{names}}})",
            f'Retyped = Table.TransformColumnTypes(Expanded, {{{types}}})',
            'NoOrder = Table.ReplaceValue(Retyped, null, "No completed order", Replacer.ReplaceValue, {"segment"})',
            'NoOrderSort = Table.ReplaceValue(NoOrder, null, 9, Replacer.ReplaceValue, {"segment_order"})',
        ]
        last = "NoOrderSort"
    if table == "dim_date":
        steps += [
            f"MonthStart = Table.AddColumn({last}, \"month_start\", each Date.StartOfMonth([date]), type date)",
            'MonthKey = Table.AddColumn(MonthStart, "month_key", each Date.Year([date]) * 100 + Date.Month([date]), '
            "Int64.Type)",
            'MonthLabel = Table.AddColumn(MonthKey, "month_label", each Date.ToText([date], "MMM yyyy", "en-US"), '
            "type text)",
        ]
        last = "MonthLabel"
    return ["let"] + [f"    {s}," for s in steps[:-1]] + [f"    {steps[-1]}", "in", f"    {last}"]


def tmdl_table(table):
    out = [f"table {table}", f"\tlineageTag: {gid(table)}", ""]
    if table == "dim_date":
        out.insert(1, "\tdataCategory: Time")
    for c in TABLES[table] + DERIVED.get(table, []):
        out += col_tmdl(table, *c)
    out += [f"\tpartition {table} = m", "\t\tmode: import", "\t\tsource ="]
    out += ["\t\t\t\t" + line for line in m_partition(table)]
    out += ["", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(out)


def tmdl_measures():
    out = ["table _Measures", f"\tlineageTag: {gid('_Measures')}", ""]
    for name, dax, fmt, folder, hidden in MEASURES:
        out.append(f"\tmeasure {q(name)} = {dax}")
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        if hidden:
            out.append("\t\tisHidden")
        out += [f"\t\tdisplayFolder: {folder}", f"\t\tlineageTag: {gid('m', name)}", ""]
    out += ["\tcolumn Value", "\t\tdataType: string", "\t\tisHidden", f"\t\tlineageTag: {gid('_Measures', 'Value')}",
            "\t\tsummarizeBy: none", "\t\tsourceColumn: Value", "",
            "\t\tannotation SummarizationSetBy = Automatic", "",
            "\tpartition _Measures = m", "\t\tmode: import", "\t\tsource =",
            '\t\t\t\t#table(type table [Value = text], {})', "",
            "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(out)


def build_semantic_model():
    if SM.exists():
        shutil.rmtree(SM)
    write_json(SM / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}})
    write_json(SM / ".platform", {
        "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": gid("sm")}})
    d = SM / "definition"
    write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n\n")
    tables = ["_Measures", *TABLES]
    write(d / "model.tmdl", "\n".join([
        "model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures", "\tsourceQueryCulture: en-US", "\tdataAccessOptions",
        "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
        f"annotation PBI_QueryOrder = {json.dumps(['DataFolder', 'RFM_Staging', *tables])}", "",
        "annotation __PBI_TimeIntelligenceEnabled = 0", "",
        *[f"ref table {t}" for t in tables], ""]))
    rfm_types = {c: t for c, t, _, _ in DERIVED["dim_customer"]}
    rfm_cols = [("customer_id", S, False, {})] + [(c, rfm_types[c], False, {}) for c in RFM_COLS]
    rsteps, rlast = m_csv("customer_rfm", rfm_cols)
    rfm_m = ["let"] + [f"    {s}," for s in rsteps] + \
            [f"    Kept = Table.SelectColumns({rlast}, {{{', '.join(chr(34) + c[0] + chr(34) for c in rfm_cols)}}})",
             "in", "    Kept"]
    write(d / "expressions.tmdl", "\n".join([
        f'expression DataFolder = "{DATA_FOLDER}" meta [IsParameterQuery = true, Type = "Text", '
        "IsParameterQueryRequired = true]",
        f"\tlineageTag: {gid('DataFolder')}", "", "\tannotation PBI_ResultType = Text", "",
        "/// RFM scores from sql/analysis.sql (query 05); merged into dim_customer, not loaded on its own",
        "expression RFM_Staging =",
        *["\t\t" + line for line in rfm_m],
        f"\tlineageTag: {gid('RFM_Staging')}", "", "\tannotation PBI_ResultType = Table", ""]))
    rels = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rels += [f"relationship {gid('rel', ft, fc, tt)}"]
        if tc == "date":
            rels += ["\tjoinOnDateBehavior: datePartOnly"]
        rels += [f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {tt}.{tc}", ""]
    write(d / "relationships.tmdl", "\n".join(rels))
    write(d / "tables" / "_Measures.tmdl", tmdl_measures())
    for t in TABLES:
        write(d / "tables" / f"{t}.tmdl", tmdl_table(t))


# =========================================================================
# Theme
# =========================================================================
def sc(c):
    return {"solid": {"color": c}}


THEME = {
    "name": "Harbor & Pine Executive",
    "dataColors": DATA_COLORS,
    "foreground": INK, "foregroundNeutralSecondary": SLATE, "foregroundNeutralTertiary": SLATE_2,
    "background": WHITE, "backgroundLight": "#F6F8FB", "backgroundNeutral": LINE,
    "tableAccent": PRIMARY, "good": GOOD, "neutral": WARN, "bad": BAD,
    "maximum": PRIMARY, "center": "#7FA3C7", "minimum": "#EAF0F7", "null": "#F1F3F7",
    "hyperlink": PRIMARY, "visitedHyperlink": PRIMARY,
    "textClasses": {
        "callout": {"fontSize": 24, "fontFace": FONT_SB, "color": INK},
        "title": {"fontSize": 11, "fontFace": FONT_SB, "color": INK},
        "header": {"fontSize": 10, "fontFace": FONT_SB, "color": "#334155"},
        "label": {"fontSize": 9, "fontFace": FONT, "color": "#475569"},
    },
    "visualStyles": {
        "*": {"*": {
            "background": [{"show": True, "color": sc(WHITE), "transparency": 0}],
            "border": [{"show": True, "color": sc(LINE), "radius": 12, "width": 1}],
            "dropShadow": [{"show": True, "color": sc(NAVY), "position": "Outer", "preset": "Custom",
                            "transparency": 90, "shadowBlur": 14, "shadowDistance": 3, "shadowSpread": 0,
                            "angle": 90}],
            "padding": [{"top": 12, "bottom": 10, "left": 14, "right": 14}],
            "title": [{"show": True, "fontColor": sc(INK), "fontSize": 11, "fontFamily": FONT_SB,
                       "titleWrap": True}],
            "subTitle": [{"fontColor": sc(SLATE), "fontSize": 9, "fontFamily": FONT}],
            "categoryAxis": [{"showAxisTitle": False, "gridlineStyle": "dotted", "labelColor": sc(SLATE),
                              "fontSize": 9, "concatenateLabels": False}],
            "valueAxis": [{"showAxisTitle": False, "gridlineStyle": "dotted", "gridlineColor": sc(LINE),
                           "labelColor": sc(SLATE), "fontSize": 9}],
            "legend": [{"show": True, "position": "TopLeft", "labelColor": sc("#475569"), "fontSize": 9,
                        "showTitle": False}],
            "labels": [{"color": sc("#334155"), "fontSize": 9}],
            "lineStyles": [{"strokeWidth": 3}],
            "outspacePane": [{"backgroundColor": sc(WHITE), "foregroundColor": sc(INK), "transparency": 0,
                              "border": True, "borderColor": sc(LINE)}],
        }},
        "page": {"*": {"background": [{"color": sc(CANVAS), "transparency": 0}],
                       "outspace": [{"color": sc("#E7EBF1"), "transparency": 0}]}},
        "card": {"*": {"labels": [{"color": sc(INK), "fontSize": 24, "fontFamily": FONT_SB}],
                       "categoryLabels": [{"show": False}],
                       "title": [{"alignment": "center", "fontSize": 9, "fontColor": sc(SLATE),
                                  "fontFamily": FONT_SB}]}},
        "tableEx": {"*": {
            "grid": [{"gridVertical": False, "gridHorizontal": True, "gridHorizontalColor": sc("#EEF1F6"),
                      "outlineColor": sc(LINE), "rowPadding": 5}],
            "columnHeaders": [{"fontColor": sc("#475569"), "backColor": sc("#F6F8FB"), "fontFamily": FONT_SB,
                               "fontSize": 9, "wordWrap": True}],
            "values": [{"fontColorPrimary": sc("#1E293B"), "backColorPrimary": sc(WHITE),
                        "fontColorSecondary": sc("#1E293B"), "backColorSecondary": sc("#FAFBFD"), "fontSize": 9}],
            "total": [{"fontFamily": FONT_SB, "backColor": sc("#F6F8FB"), "fontColor": sc(INK)}]}},
        "pivotTable": {"*": {
            "grid": [{"gridVertical": False, "gridHorizontal": True, "gridHorizontalColor": sc("#EEF1F6"),
                      "outlineColor": sc(LINE), "rowPadding": 5}],
            "columnHeaders": [{"fontColor": sc("#475569"), "backColor": sc("#F6F8FB"), "fontFamily": FONT_SB,
                               "fontSize": 9}],
            "rowHeaders": [{"fontColor": sc("#1E293B"), "fontSize": 9, "showExpandCollapseButtons": False,
                            "legacyStyleDisabled": True}],
            "values": [{"fontColorPrimary": sc("#1E293B"), "backColorPrimary": sc(WHITE),
                        "backColorSecondary": sc(WHITE), "fontSize": 9}],
            "subTotals": [{"fontFamily": FONT_SB, "backgroundColor": sc("#F6F8FB")}]}},
        "slicer": {"*": {
            "header": [{"show": True, "fontColor": sc(MIST), "textSize": 8, "fontFamily": FONT_SB,
                        "outline": "None"}],
            "items": [{"fontColor": sc(INK), "background": sc(WHITE), "textSize": 9, "outline": "None"}],
            "background": [{"show": False}], "border": [{"show": False}], "dropShadow": [{"show": False}],
            "padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0}]}},
        "textbox": {"*": {"background": [{"show": False}], "border": [{"show": False}],
                          "dropShadow": [{"show": False}], "padding": [{"top": 0, "bottom": 0, "left": 0,
                                                                         "right": 0}]}},
        "actionButton": {"*": {"background": [{"show": False}], "border": [{"show": False}],
                               "dropShadow": [{"show": False}], "visualHeader": [{"show": False}]}},
    },
}


# =========================================================================
# Report helpers (PBIR)
# =========================================================================
def lit(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def lit_int(v):
    return {"expr": {"Literal": {"Value": f"{v}L"}}}


def col(table, column):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def mea(name):
    assert any(x[0] == name for x in MEASURES), f"unknown measure {name}"
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": name}}


def ref(field):
    k = next(iter(field))
    return f"{field[k]['Expression']['SourceRef']['Entity']}.{field[k]['Property']}"


def proj(field, display=None):
    p = {"field": field, "queryRef": ref(field), "nativeQueryRef": field[next(iter(field))]["Property"]}
    if display:
        p["displayName"] = display
    return p


def solid(color):
    """Colour from a hex string or from a measure (conditional formatting)."""
    return {"solid": {"color": lit(color) if isinstance(color, str) else {"expr": color}}}


def text_or_measure(v):
    return lit(v) if isinstance(v, str) else {"expr": v}


def plain_container(**over):
    """No card chrome: for elements that sit on the sidebar or overlay a tile."""
    o = {"background": [{"properties": {"show": lit(False)}}],
         "border": [{"properties": {"show": lit(False)}}],
         "dropShadow": [{"properties": {"show": lit(False)}}],
         "visualHeader": [{"properties": {"show": lit(False)}}],
         "title": [{"properties": {"show": lit(False)}}],
         "padding": [{"properties": {"top": lit(0), "bottom": lit(0), "left": lit(0), "right": lit(0)}}]}
    o.update(over)
    return o


class Page:
    def __init__(self, key, title, kind=None, width=1280, height=720):
        self.key, self.name, self.title = key, hid("page", key), title
        self.kind, self.width, self.height = kind, width, height
        self.visuals = []

    def add(self, vid, x, y, w, h, visual, extra=None):
        v = {"$schema": f"{SCHEMA}/item/report/definition/visualContainer/{V_VISUAL}/schema.json",
             "name": hid(self.key, vid),
             "position": {"x": round(x, 2), "y": round(y, 2), "z": len(self.visuals) * 100,
                          "height": round(h, 2), "width": round(w, 2), "tabOrder": len(self.visuals) * 100},
             "visual": visual}
        if extra:
            v.update(extra)
        self.visuals.append(v)


def visual(vtype, roles=None, title=None, subtitle=None, sort=None, objects=None, container=None,
           tooltip_page=None):
    v = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if roles:
        v["query"] = {"queryState": {r: {"projections": [proj(f) if "Column" in f or "Measure" in f
                                                         else proj(*f) for f in fs]}
                                     for r, fs in roles.items()}}
        if sort:
            v["query"]["sortDefinition"] = {"sort": [{"field": f, "direction": d} for f, d in sort],
                                            "isDefaultSort": False}
    if objects:
        v["objects"] = objects
    vco = dict(container or {})
    if title is not None:
        vco.setdefault("title", [{"properties": {"show": lit(True), "text": text_or_measure(title)}}])
    if subtitle:
        vco["subTitle"] = [{"properties": {"show": lit(True), "text": lit(subtitle)}}]
    if tooltip_page:
        vco["visualTooltip"] = [{"properties": {"show": lit(True), "type": lit("ReportPage"),
                                                "section": lit(tooltip_page)}}]
    if vco:
        v["visualContainerObjects"] = vco
    return v


def textbox(paragraphs, container=None, align="left"):
    """paragraphs: list of lists of (text, size, color, bold) runs."""
    paras = []
    for runs in paragraphs:
        paras.append({"horizontalTextAlignment": align, "textRuns": [{"value": t, "textStyle": {
            "fontSize": f"{size}pt", "color": color, "fontFamily": FONT_SB if bold else FONT,
            **({"fontWeight": "bold"} if bold else {})}} for t, size, color, bold in runs]})
    return {"visualType": "textbox", "drillFilterOtherVisuals": True,
            "objects": {"general": [{"properties": {"paragraphs": paras}}]},
            "visualContainerObjects": container or plain_container()}


def panel(color, radius=0):
    """A coloured rectangle (sidebar, accents) made from an empty textbox container."""
    return {"visualType": "textbox", "drillFilterOtherVisuals": True,
            "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": ""}]}]}}]},
            "visualContainerObjects": plain_container(
                background=[{"properties": {"show": lit(True), "color": solid(color), "transparency": lit(0)}}],
                border=[{"properties": {"show": lit(radius > 0), "color": solid(color), "radius": lit(radius)}}])}


def card(measure, *, size=24, color=INK, display=None, millions=False, exact=False, title=None,
         container=None, font=FONT_SB):
    lab = {"color": solid(color), "fontSize": lit(size), "fontFamily": lit(font)}
    if millions:
        lab.update(labelDisplayUnits=lit(1000000), labelPrecision=lit_int(2))
    elif exact:
        lab.update(labelDisplayUnits=lit(1))
    return visual("card", {"Values": [(mea(measure), display)] if display else [mea(measure)]}, title=title,
                  objects={"labels": [{"properties": lab}],
                           "categoryLabels": [{"properties": {"show": lit(False)}}]},
                  container=container)


def series_colors(colors):
    return [{"properties": {"fill": solid(c)}, "selector": {"metadata": ref(mea(n))}} for n, c in colors]


def measure_fill(name):
    return [{"properties": {"fill": solid(mea(name))},
             "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]


def cf(measure_ref, *, back=None, font=None):
    """Conditional formatting on one value column of a table/matrix (field-value rule)."""
    props = {}
    if back:
        props["backColor"] = solid(mea(back))
    if font:
        props["fontColor"] = solid(mea(font))
    return {"properties": props,
            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": measure_ref}}


def labels(show=True, **extra):
    extra.setdefault("labelPosition", "OutsideEnd")
    return [{"properties": {"show": lit(show), **{k: (lit(v) if not isinstance(v, dict) else v)
                                                   for k, v in extra.items()}}}]


# =========================================================================
# Layout
# =========================================================================
W, H = 1280, 720
SIDEBAR_W = 208
X0, X1 = 224, 1264          # content area
GAP = 12
NAV = [("summary", "Executive Summary"), ("customers", "Customers & RFM"),
       ("delivery", "Delivery & Experience"), ("products", "Products")]
SLICERS = [(col("dim_date", "year"), "YEAR", "year"),
           (col("dim_customer", "region"), "REGION", "region"),
           (col("dim_customer", "acquisition_channel"), "ACQUISITION CHANNEL", "channel"),
           (col("dim_customer", "segment"), "RFM SEGMENT", "segment")]
PAGE_NAMES = {k: hid("page", k) for k, _ in NAV}
PAGE_NAMES["category"] = hid("page", "category")
PAGE_NAMES["tooltip"] = hid("page", "tooltip")


def sidebar(p, active):
    p.add("sb_bg", 0, 0, SIDEBAR_W, H, panel(NAVY))
    p.add("sb_brand", 20, 22, 180, 52, textbox([
        [("HARBOR & PINE", 13, GOLD, True)],
        [("Executive Analytics", 9, SLATE_2, False)]]))
    p.add("sb_rule", 20, 82, 168, 1, panel("#22395A"))
    p.add("sb_navlabel", 20, 94, 168, 16, textbox([[("DASHBOARDS", 7, "#7C8DA6", True)]]))
    for i, (key, label) in enumerate(NAV):
        y = 114 + i * 40
        is_active = key == active
        if is_active:
            p.add(f"nav_bg_{key}", 12, y, 184, 34, panel(NAVY_2, radius=8))
            p.add(f"nav_mark_{key}", 12, y + 8, 3, 18, panel(GOLD, radius=1))
        p.add(f"nav_label_{key}", 28, y + 8, 160, 20, textbox(
            [[(label, 10, WHITE if is_active else "#A9B6C9", is_active)]]))
        p.add(f"nav_{key}", 12, y, 184, 34, {
            "visualType": "actionButton", "drillFilterOtherVisuals": True,
            "objects": {
                "icon": [{"properties": {"show": lit(False)}}, {"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
                "text": [{"properties": {"show": lit(False)}}, {"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
                "fill": [{"properties": {"show": lit(False)}}, {"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
                "outline": [{"properties": {"show": lit(False)}}, {"properties": {"show": lit(False)}, "selector": {"id": "default"}}]},
            "visualContainerObjects": {
                **plain_container(),
                "visualLink": [{"properties": {"show": lit(True), "type": lit("PageNavigation"),
                                               "navigationSection": lit(PAGE_NAMES[key])}}]}})
    p.add("sb_rule2", 20, 284, 168, 1, panel("#22395A"))
    p.add("sb_filterlabel", 20, 296, 168, 16, textbox([[("FILTERS", 7, "#7C8DA6", True)]]))
    for i, (f, label, g) in enumerate(SLICERS):
        y = 316 + i * 62
        v = visual("slicer", {"Values": [(f, label)]}, objects={
            "data": [{"properties": {"mode": lit("Dropdown")}}],
            "header": [{"properties": {"show": lit(True), "fontColor": solid(MIST), "textSize": lit(8),
                                       "fontFamily": lit(FONT_SB)}}],
            "items": [{"properties": {"fontColor": solid(INK), "background": solid(WHITE), "textSize": lit(9)}}]},
            container=plain_container())
        v["syncGroup"] = {"groupName": g, "fieldChanges": True, "filterChanges": True}
        p.add(f"slicer_{g}", 20, y, 168, 54, v)
    p.add("sb_foot", 20, 650, 176, 56, textbox([
        [("Synthetic data · Jan 2023 – Dec 2025", 7, "#7C8DA6", False)],
        [("Ctrl + click a menu item in Desktop", 7, "#7C8DA6", False)],
        [("Right-click a category to drill through", 7, "#7C8DA6", False)]]))


def header(p, title):
    p.add("hdr_title", X0, 14, 620, 34, textbox([[(title, 18, INK, True)]]))
    p.add("hdr_context", X0, 46, 900, 22, visual(
        "card", {"Values": [mea("Blank Text")]},
        objects={"labels": [{"properties": {"fontSize": lit(1), "color": solid(CANVAS)}}],
                 "categoryLabels": [{"properties": {"show": lit(False)}}]},
        container=plain_container(title=[{"properties": {
            "show": lit(True), "text": {"expr": mea("Filter Context")}, "fontColor": solid(SLATE),
            "fontSize": lit(9), "fontFamily": lit(FONT), "alignment": lit("left")}}])))


def frame():
    """White rounded card with shadow (the tile background)."""
    return {"visualType": "textbox", "drillFilterOtherVisuals": True,
            "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": ""}]}]}}]},
            "visualContainerObjects": plain_container(
                background=[{"properties": {"show": lit(True), "color": solid(WHITE), "transparency": lit(0)}}],
                border=[{"properties": {"show": lit(True), "color": solid(LINE), "radius": lit(12)}}],
                dropShadow=[{"properties": {"show": lit(True), "color": solid(NAVY), "position": lit("Outer"),
                                            "preset": lit("Custom"), "transparency": lit(90), "shadowBlur": lit(14),
                                            "shadowDistance": lit(3), "shadowSpread": lit(0), "angle": lit(90)}}])}


def kpi_tiles(p, tiles, y=76, h=104):
    """tiles: (value measure, label, sub-measure, sub-colour measure or hex, number style)."""
    n = len(tiles)
    w = (X1 - X0 - (n - 1) * GAP) / n
    for i, (val, label, sub, sub_color, style) in enumerate(tiles):
        x = X0 + i * (w + GAP)
        p.add(f"kpi_{i}_frame", x, y, w, h, frame())
        p.add(f"kpi_{i}_rule", x + w / 2 - 14, y + 12, 28, 3, panel(GOLD))
        p.add(f"kpi_{i}_label", x + 8, y + 20, w - 16, 18,
              textbox([[(label.upper(), 7.5, SLATE, True)]], align="center"))
        p.add(f"kpi_{i}_value", x + 6, y + 38, w - 12, 40, card(
            val, size=22, millions=style == "M", exact=style == "N", container=plain_container()))
        is_hex = sub_color.startswith("#")
        sub_card = card(sub, size=8.5, font=FONT_SB, color=sub_color if is_hex else SLATE,
                        container=plain_container())
        if not is_hex:          # colour from a measure: teal = better, terracotta = worse
            sub_card["objects"]["labels"][0]["properties"]["color"] = solid(mea(sub_color))
        p.add(f"kpi_{i}_sub", x + 6, y + 78, w - 12, 20, sub_card)


# =========================================================================
# Pages
# =========================================================================
def page_summary():
    p = Page("summary", "Executive Summary")
    sidebar(p, "summary")
    header(p, "Executive Summary")
    kpi_tiles(p, [
        ("Revenue", "Revenue", "Revenue vs PY Label", "Revenue vs PY Color", "M"),
        ("Orders", "Orders", "Orders vs PY Label", "Orders vs PY Color", "N"),
        ("Customers", "Customers", "Customers vs PY Label", "Customers vs PY Color", "N"),
        ("Avg Order Value", "Avg order value", "Avg Order Value vs PY Label", "Avg Order Value vs PY Color", ""),
        ("Repeat Rate %", "Customers who reordered", "Repeat Rate % vs PY Label", "Repeat Rate % vs PY Color", "")])
    p.add("trend", X0, 192, 676, 262, visual(
        "lineChart", {"Category": [(col("dim_date", "month_start"), "Month")],
                      "Y": [(mea("Revenue"), "Revenue"), (mea("Revenue PY"), "Prior year")]},
        title=mea("Title Trend"), subtitle="Is growth holding up month by month?",
        objects={"dataPoint": series_colors([("Revenue", PRIMARY), ("Revenue PY", COMPARE)]),
                 "lineStyles": [{"properties": {"strokeWidth": lit(3)}},
                                {"properties": {"lineStyle": lit("dashed"), "strokeWidth": lit(2)},
                                 "selector": {"metadata": ref(mea("Revenue PY"))}}],
                 "categoryAxis": [{"properties": {"axisType": lit("Scalar")}}]},
        tooltip_page=PAGE_NAMES["tooltip"]))
    p.add("waterfall", X0 + 676 + GAP, 192, X1 - X0 - 676 - GAP, 262, visual(
        "waterfallChart", {"Category": [(col("dim_product", "category"), "Category")],
                           "Y": [(mea("Item Revenue Change vs PY"), "Change vs prior year")]},
        title=mea("Title Waterfall"), subtitle="Which categories drove the change?",
        sort=[(mea("Item Revenue Change vs PY"), "Descending")],
        objects={"sentimentColors": [{"properties": {"increaseFill": solid(GOOD), "decreaseFill": solid(BAD),
                                                     "totalFill": solid(PRIMARY)}}],
                 "labels": labels(True, labelDisplayUnits=1000, labelPrecision=lit_int(0))}))
    region_vals = [(mea("Revenue"), "Revenue"), (mea("Revenue Share of Total"), "Share"),
                   (mea("Revenue vs PY"), "vs PY"), (mea("Late Rate %"), "Late %"),
                   (mea("Avg Review Score"), "Review")]
    p.add("regions", X0, 466, 520, 238, visual(
        "pivotTable", {"Rows": [(col("dim_customer", "region"), "Region")], "Values": region_vals},
        title="Regional performance", subtitle="Where is revenue growing, and where is service weakest?",
        sort=[(mea("Revenue"), "Descending")],
        objects={"values": [cf(ref(mea("Revenue vs PY")), font="YoY Color"),
                            cf(ref(mea("Late Rate %")), back="Late Heat"),
                            cf(ref(mea("Avg Review Score")), font="Review Color")]}))
    insights = [
        [("KEY INSIGHTS", 8, GOLD, True), ("   ·   all data, 2023 – 2025", 8, SLATE_2, False)],
        [("", 4, INK, False)],
        [("Growth is volume-led. ", 9.5, INK, True),
         ("Revenue rose 55% in 2024 and 32% in 2025 while the average order stayed near $105.", 9.5, "#334155", False)],
        [("A quarter of customers return. ", 9.5, INK, True),
         ("25% order again, 60% of them within 90 days of their first order.", 9.5, "#334155", False)],
        [("Value is concentrated. ", 9.5, INK, True),
         ("Champions + Loyal are 7.9% of customers but 24.7% of revenue.", 9.5, "#334155", False)],
        [("Late first orders lose customers. ", 9.5, INK, True),
         ("Only 7.1% return after a first order 4+ days late, vs 31.1% when on time.", 9.5, "#334155", False)],
        [("Economy shipping is the weak link. ", 9.5, INK, True),
         ("Late 23.5% of the time vs 11.3% for Standard.", 9.5, "#334155", False)],
    ]
    p.add("insights_bg", X0 + 520 + GAP, 466, X1 - X0 - 520 - GAP, 238, panel(NAVY, radius=12))
    p.add("insights", X0 + 520 + GAP + 20, 480, X1 - X0 - 520 - GAP - 40, 214, textbox(
        [[(t, s, (WHITE if c == INK else (MIST if c == "#334155" else c)), b) for t, s, c, b in para]
         for para in insights]))
    return p


def page_customers():
    p = Page("customers", "Customers & RFM")
    sidebar(p, "customers")
    header(p, "Customers & RFM Segments")
    kpi_tiles(p, [
        ("Scored Customers", "Customers scored", "Note Lifetime", SLATE, "N"),
        ("Avg Lifetime Spend", "Avg lifetime spend", "Note Lifetime", SLATE, ""),
        ("Avg Orders per Customer", "Avg orders per customer", "Note Lifetime", SLATE, ""),
        ("Top Segments Revenue Share", "Champions + Loyal revenue", "Note Lifetime", SLATE, ""),
        ("Came Back %", "Returned after 1st order", "Note First Orders", SLATE, "")])
    SEG = (col("dim_customer", "segment"), "Segment")
    p.add("share", X0, 192, 500, 262, visual(
        "clusteredColumnChart", {"Category": [SEG], "Y": [(mea("% of Customers"), "% of customers"),
                                                       (mea("% of Revenue"), "% of revenue")],
                              "Tooltips": [mea("Avg Lifetime Spend"), mea("Scored Customers")]},
        title="Share of customers vs share of revenue", subtitle="Which segments punch above their weight?",
        sort=[(col("dim_customer", "segment"), "Ascending")],
        objects={"dataPoint": series_colors([("% of Customers", COMPARE), ("% of Revenue", PRIMARY)]),
                 "labels": labels(True, labelPrecision=lit_int(1), fontSize=8)}))
    p.add("heat", X0 + 500 + GAP, 192, X1 - X0 - 500 - GAP, 262, visual(
        "pivotTable", {"Rows": [(col("dim_customer", "r_score"), "Recency score (5 = recent)")],
                       "Columns": [(col("dim_customer", "f_score"), "Frequency score")],
                       "Values": [(mea("Avg Lifetime Spend"), "Avg spend")]},
        title="Average lifetime spend by recency and frequency score",
        subtitle="Recent, frequent buyers are worth 8x a one-off buyer",
        sort=[(col("dim_customer", "r_score"), "Descending")],
        objects={"values": [cf(ref(mea("Avg Lifetime Spend")), back="RF Heat", font="RF Heat Font")]}))
    p.add("profile", X0, 466, 620, 238, visual(
        "tableEx", {"Values": [SEG, (mea("Scored Customers"), "Customers"), (mea("% of Customers"), "% cust."),
                               (mea("Lifetime Revenue"), "Revenue"), (mea("% of Revenue"), "% rev."),
                               (mea("Avg Recency Days"), "Days since last order"),
                               (mea("Avg Orders per Customer"), "Orders"), (mea("Avg Lifetime Spend"), "Avg spend")]},
        title="Segment profile", subtitle="Who to reward (Champions), grow (Potential) and win back (At Risk)",
        sort=[(col("dim_customer", "segment"), "Ascending")]))
    p.add("channels", X0 + 620 + GAP, 466, X1 - X0 - 620 - GAP, 238, visual(
        "clusteredBarChart", {"Category": [(col("dim_customer", "acquisition_channel"), "Channel")],
                              "Y": [(mea("Repeat Rate %"), "Ordered again")],
                              "Tooltips": [mea("Avg Lifetime Spend"), mea("Customers")]},
        title="Repeat rate by acquisition channel", subtitle="Which channels bring customers who come back?",
        sort=[(mea("Repeat Rate %"), "Descending")],
        objects={"dataPoint": [{"properties": {"fill": solid(PRIMARY)}}], "labels": labels(True)}))
    return p


def page_delivery():
    p = Page("delivery", "Delivery & Experience")
    sidebar(p, "delivery")
    header(p, "Delivery & Customer Experience")
    kpi_tiles(p, [
        ("Late Rate %", "Delivered late", "Late Rate % vs PY Label", "Late Rate % vs PY Color", ""),
        ("Avg Delivery Days", "Avg days to deliver", "Avg Delivery Days vs PY Label", "Avg Delivery Days vs PY Color", ""),
        ("Avg Review Score", "Avg review score", "Avg Review Score vs PY Label", "Avg Review Score vs PY Color", ""),
        ("Low Reviews %", "1- and 2-star reviews", "Low Reviews % vs PY Label", "Low Reviews % vs PY Color", ""),
        ("Came Back %", "Returned after 1st order", "Note First Orders", SLATE, "")])
    BAND = (col("fact_orders", "delivery_band"), "Delivery")
    w3 = (X1 - X0 - 2 * GAP) / 3
    p.add("score", X0, 192, w3, 262, visual(
        "clusteredColumnChart", {"Category": [BAND], "Y": [(mea("Avg Review Score"), "Avg review")]},
        title="Review score by delivery delay", subtitle="What does each late day cost in stars?",
        sort=[(col("fact_orders", "delivery_band"), "Ascending")],
        objects={"dataPoint": measure_fill("Review Color"), "labels": labels(True, labelPrecision=lit_int(2))}))
    p.add("cameback", X0 + w3 + GAP, 192, w3, 262, visual(
        "clusteredColumnChart", {"Category": [BAND], "Y": [(mea("Came Back %"), "Ordered again")]},
        title="Return rate by first-order delay", subtitle="Does a late first order lose the customer?",
        sort=[(col("fact_orders", "delivery_band"), "Ascending")],
        objects={"dataPoint": measure_fill("Came Back Color"), "labels": labels(True)}))
    p.add("carrier", X0 + 2 * (w3 + GAP), 192, w3, 262, visual(
        "clusteredBarChart", {"Category": [(col("fact_orders", "carrier"), "Carrier")],
                              "Y": [(mea("Late Rate %"), "Late %")], "Tooltips": [mea("Delivered Orders")]},
        title="Late-delivery rate by carrier", subtitle="Which carrier misses its promise?",
        sort=[(mea("Late Rate %"), "Descending")],
        objects={"dataPoint": measure_fill("Late Color"), "labels": labels(True)}))
    p.add("trend", X0, 466, 620, 238, visual(
        "lineChart", {"Category": [(col("dim_date", "month_start"), "Month")],
                      "Series": [(col("fact_orders", "carrier"), "Carrier")], "Y": [(mea("Late Rate %"), "Late %")]},
        title="Late-delivery rate by month and carrier", subtitle="Is it getting better, and when does it spike?",
        objects={"categoryAxis": [{"properties": {"axisType": lit("Scalar")}}],
                 "lineStyles": [{"properties": {"strokeWidth": lit(2)}}]},
        tooltip_page=PAGE_NAMES["tooltip"]))
    p.add("matrix", X0 + 620 + GAP, 466, X1 - X0 - 620 - GAP, 238, visual(
        "pivotTable", {"Rows": [(col("fact_orders", "carrier"), "Carrier")],
                       "Columns": [(col("dim_customer", "region"), "Region")],
                       "Values": [(mea("Late Rate %"), "Late %")]},
        title="Late-delivery heatmap", subtitle="Carrier × region hot spots",
        objects={"values": [cf(ref(mea("Late Rate %")), back="Late Heat")]}))
    return p


def page_products():
    p = Page("products", "Products")
    sidebar(p, "products")
    header(p, "Product & Category Performance")
    kpi_tiles(p, [
        ("Item Revenue", "Product revenue", "Item Revenue vs PY Label", "Item Revenue vs PY Color", "M"),
        ("Gross Margin", "Gross margin", "Gross Margin vs PY Label", "Gross Margin vs PY Color", "M"),
        ("Gross Margin %", "Gross margin %", "Gross Margin % vs PY Label", "Gross Margin % vs PY Color", ""),
        ("Units Sold", "Units sold", "Units Sold vs PY Label", "Units Sold vs PY Color", "N")])
    CAT = (col("dim_product", "category"), "Category")
    p.add("scatter", X0, 192, 500, 262, visual(
        "scatterChart", {"Category": [CAT], "X": [(mea("Item Revenue"), "Revenue")],
                         "Y": [(mea("Gross Margin %"), "Gross margin %")], "Size": [mea("Units Sold")]},
        title="Revenue vs margin by category", subtitle="Which categories earn their volume? Right-click to drill through",
        objects={"dataPoint": measure_fill("Margin Color"),
                 "categoryLabels": [{"properties": {"show": lit(True), "color": solid("#334155"),
                                                    "fontSize": lit(8)}}]}))
    vals = [(mea("Item Revenue"), "Revenue"), (mea("Category Revenue Share"), "Share"),
            (mea("Item Revenue vs PY"), "vs PY"), (mea("Gross Margin %"), "Margin %"), (mea("Units Sold"), "Units")]
    p.add("catmatrix", X0 + 500 + GAP, 192, X1 - X0 - 500 - GAP, 262, visual(
        "pivotTable", {"Rows": [CAT], "Values": vals},
        title="Category scorecard", subtitle="Growth and margin side by side",
        sort=[(mea("Item Revenue"), "Descending")],
        objects={"values": [cf(ref(mea("Item Revenue vs PY")), font="Item YoY Color"),
                            cf(ref(mea("Gross Margin %")), font="Margin Color")]}))
    p.add("ranking", X0, 466, X1 - X0, 238, visual(
        "tableEx", {"Values": [(mea("Product Rank"), "#"), (col("dim_product", "product_name"), "Product"), CAT,
                               (mea("Units Sold"), "Units"), (mea("Item Revenue"), "Revenue"),
                               (mea("Gross Margin %"), "Margin %"), (mea("Item Revenue vs PY"), "vs PY")]},
        title="Product ranking", subtitle="Best sellers by revenue, with margin and growth",
        sort=[(mea("Item Revenue"), "Descending")],
        objects={"values": [cf(ref(mea("Gross Margin %")), font="Margin Color"),
                            cf(ref(mea("Item Revenue vs PY")), font="Item YoY Color")],
                 "columnWidth": [{"properties": {"value": lit(w)}, "selector": {"metadata": r}}
                                 for r, w in [(ref(mea("Product Rank")), 50),
                                              (ref(col("dim_product", "product_name")), 330),
                                              (ref(col("dim_product", "category")), 200),
                                              (ref(mea("Units Sold")), 90), (ref(mea("Item Revenue")), 110),
                                              (ref(mea("Gross Margin %")), 100),
                                              (ref(mea("Item Revenue vs PY")), 90)]]}))
    return p


def page_category():
    p = Page("category", "Category Detail", kind="Drillthrough")
    sidebar(p, None)
    p.add("hdr_title", X0 + 48, 14, 700, 34, card("Title Category", size=1, container=plain_container(
        title=[{"properties": {"show": lit(True), "text": {"expr": mea("Title Category")}, "fontColor": solid(INK),
                               "fontSize": lit(18), "fontFamily": lit(FONT_SB), "alignment": lit("left")}}])))
    p.visuals[-1]["visual"]["objects"]["labels"][0]["properties"]["color"] = solid(CANVAS)
    p.add("back", X0, 16, 36, 30, {
        "visualType": "actionButton", "drillFilterOtherVisuals": True,
        "objects": {"icon": [{"properties": {"shapeType": lit("back"), "lineColor": solid(PRIMARY),
                                             "lineWeight": lit(2)}, "selector": {"id": "default"}}],
                    "fill": [{"properties": {"show": lit(True), "fillColor": solid(WHITE)}, "selector": {"id": "default"}}],
                    "outline": [{"properties": {"show": lit(False)}}, {"properties": {"show": lit(False)}, "selector": {"id": "default"}}]},
        "visualContainerObjects": {**plain_container(
            border=[{"properties": {"show": lit(True), "color": solid(LINE), "radius": lit(8)}}]),
            "visualLink": [{"properties": {"show": lit(True), "type": lit("Back")}}]}})
    header_ctx = Page("tmp", "")
    header(header_ctx, "")
    ctx = header_ctx.visuals[1]
    ctx["name"] = hid("category", "hdr_context")
    p.visuals.append(ctx)
    kpi_tiles(p, [
        ("Item Revenue", "Category revenue", "Item Revenue vs PY Label", "Item Revenue vs PY Color", "M"),
        ("Category Revenue Share", "Share of product revenue", "Note Share", SLATE, ""),
        ("Gross Margin %", "Gross margin %", "Gross Margin % vs PY Label", "Gross Margin % vs PY Color", ""),
        ("Units Sold", "Units sold", "Units Sold vs PY Label", "Units Sold vs PY Color", "N")])
    p.add("trend", X0, 192, 676, 262, visual(
        "lineChart", {"Category": [(col("dim_date", "month_start"), "Month")],
                      "Y": [(mea("Item Revenue"), "Revenue"), (mea("Item Revenue PY"), "Prior year")]},
        title=mea("Title Category Trend"), subtitle="Monthly product revenue for this category",
        objects={"dataPoint": series_colors([("Item Revenue", PRIMARY), ("Item Revenue PY", COMPARE)]),
                 "lineStyles": [{"properties": {"strokeWidth": lit(3)}},
                                {"properties": {"lineStyle": lit("dashed"), "strokeWidth": lit(2)},
                                 "selector": {"metadata": ref(mea("Item Revenue PY"))}}],
                 "categoryAxis": [{"properties": {"axisType": lit("Scalar")}}]}))
    p.add("regions", X0 + 676 + GAP, 192, X1 - X0 - 676 - GAP, 262, visual(
        "clusteredBarChart", {"Category": [(col("dim_customer", "region"), "Region")],
                              "Y": [(mea("Item Revenue"), "Revenue")], "Tooltips": [mea("Gross Margin %")]},
        title="Revenue by region", subtitle="Where this category sells",
        sort=[(mea("Item Revenue"), "Descending")],
        objects={"dataPoint": [{"properties": {"fill": solid(PRIMARY)}}],
                 "labels": labels(True, labelDisplayUnits=1000, labelPrecision=lit_int(0))}))
    p.add("ranking", X0, 466, X1 - X0, 238, visual(
        "tableEx", {"Values": [(mea("Product Rank"), "#"), (col("dim_product", "product_name"), "Product"),
                               (mea("Units Sold"), "Units"), (mea("Item Revenue"), "Revenue"),
                               (mea("Gross Margin %"), "Margin %"), (mea("Item Revenue vs PY"), "vs PY")]},
        title="Products in this category", subtitle="Ranked by revenue",
        sort=[(mea("Item Revenue"), "Descending")],
        objects={"values": [cf(ref(mea("Gross Margin %")), font="Margin Color"),
                            cf(ref(mea("Item Revenue vs PY")), font="Item YoY Color")],
                 "columnWidth": [{"properties": {"value": lit(w)}, "selector": {"metadata": r}}
                                 for r, w in [(ref(mea("Product Rank")), 50),
                                              (ref(col("dim_product", "product_name")), 420),
                                              (ref(mea("Units Sold")), 110), (ref(mea("Item Revenue")), 130),
                                              (ref(mea("Gross Margin %")), 120),
                                              (ref(mea("Item Revenue vs PY")), 110)]]}))
    return p


def page_tooltip():
    p = Page("tooltip", "Tooltip · Month", kind="Tooltip", width=320, height=220)
    p.add("bg", 0, 0, 320, 220, panel(WHITE))
    p.add("title", 14, 10, 292, 30, card("Title Tooltip", size=1, container=plain_container(
        title=[{"properties": {"show": lit(True), "text": {"expr": mea("Title Tooltip")}, "fontColor": solid(INK),
                               "fontSize": lit(12), "fontFamily": lit(FONT_SB), "alignment": lit("left")}}])))
    p.visuals[-1]["visual"]["objects"]["labels"][0]["properties"]["color"] = solid(WHITE)
    for i, (mname, label, style) in enumerate([("Revenue", "REVENUE", "M"), ("Orders", "ORDERS", "N"),
                                               ("Avg Order Value", "AVG ORDER", ""), ("Late Rate %", "LATE", "")]):
        x, y = 14 + (i % 2) * 150, 46 + (i // 2) * 84
        p.add(f"t{i}", x, y, 142, 76, card(mname, size=16, millions=style == "M", exact=style == "N",
                                            title=label))
    return p


def build_report():
    if RP.exists():
        shutil.rmtree(RP)
    write_json(RP / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    write_json(RP / ".platform", {
        "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": gid("report")}})
    base = RP / "StaticResources" / "SharedResources" / "BaseThemes" / f"{BASE_THEME}.json"
    base.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(THEME_SRC, base)
    write_json(RP / "StaticResources" / "RegisteredResources" / CUSTOM_THEME, THEME)
    write_json(PBI / "theme" / CUSTOM_THEME, THEME)        # standalone copy, importable in any report
    version = {"visual": V_VISUAL, "report": V_REPORT, "page": V_PAGE}
    d = RP / "definition"
    write_json(d / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    write_json(d / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/{V_REPORT}/schema.json",
        "themeCollection": {
            "baseTheme": {"name": BASE_THEME, "reportVersionAtImport": version, "type": "SharedResources"},
            "customTheme": {"name": CUSTOM_THEME, "reportVersionAtImport": version, "type": "RegisteredResources"}},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": CUSTOM_THEME, "path": CUSTOM_THEME, "type": "CustomTheme"}]}],
        "objects": {"outspacePane": [{"properties": {"expanded": lit(False)}}]},
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True,
                     "exportDataMode": "AllowSummarized"}})
    pages = [page_summary(), page_customers(), page_delivery(), page_products(), page_category(), page_tooltip()]
    write_json(d / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name})
    for p in pages:
        page = {"$schema": f"{SCHEMA}/item/report/definition/page/{V_PAGE}/schema.json",
                "name": p.name, "displayName": p.title, "displayOption": "FitToPage",
                "height": p.height, "width": p.width}
        if p.kind == "Drillthrough":
            fname, pname = hid("filter", "category"), hid("param", "category")
            page.update({
                "type": "Drillthrough", "visibility": "HiddenInViewMode",
                "pageBinding": {"name": hid("binding", "category"), "type": "Drillthrough",
                                "parameters": [{"name": pname, "boundFilter": fname,
                                                "fieldExpr": col("dim_product", "category")}]},
                "filterConfig": {"filters": [{"name": fname, "field": col("dim_product", "category"),
                                              "type": "Categorical"}]}})
        elif p.kind == "Tooltip":
            page.update({"type": "Tooltip", "visibility": "HiddenInViewMode",
                         "pageBinding": {"name": hid("binding", "tooltip"), "type": "Tooltip",
                                         "parameters": []}})
        write_json(d / "pages" / p.name / "page.json", page)
        for v in p.visuals:
            write_json(d / "pages" / p.name / "visuals" / v["name"] / "visual.json", v)
    return pages


if __name__ == "__main__":
    build_semantic_model()
    pages = build_report()
    write_json(PBI / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}})
    write(PBI / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print(f"wrote {PBI / (NAME + '.pbip')}")
    print(f"  model : {len(TABLES) + 1} tables, {len(MEASURES)} measures "
          f"({sum(1 for x in MEASURES if not x[4])} visible), {len(RELATIONSHIPS)} relationships")
    print(f"  report: {len(pages)} pages, {sum(len(p.visuals) for p in pages)} visuals")
