"""
Harbor & Pine: generate the Power BI dashboard as a Power BI Project (PBIP).

Writes powerbi/HarborPine.pbip with
  HarborPine.SemanticModel/  two fact tables, customer/product/date/RFM tables, DAX measures (TMDL)
  HarborPine.Report/         4 report pages (PBIR JSON)
Open the .pbip in Power BI Desktop, click Refresh, then File > Save as .pbix if a
single file is needed.

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

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
V_VISUAL, V_PAGE, V_REPORT = "2.4.0", "2.0.0", "3.0.0"

BLUE, RED, ORANGE, GREEN, DARK, GREY = "#2563EB", "#C0392B", "#E67E22", "#1E8449", "#111827", "#6B7280"


def gid(*parts):
    """Deterministic GUID so re-running the script gives a stable diff."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "superstore/" + "/".join(parts)))


def hid(*parts):
    return gid(*parts).replace("-", "")[:20]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path, obj):
    write(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


# =========================================================================
# Semantic model (TMDL)
# =========================================================================
# (name, tmdl dataType, M type, hidden, extra properties)
S, I, D, DT, B = "string", "int64", "double", "dateTime", "boolean"
MTYPE = {S: "type text", I: "Int64.Type", D: "type number", DT: "type date", B: "logical"}


def cols(*spec):
    out = []
    for item in spec:
        name, dtype, *rest = item
        hidden = bool(rest and rest[0])
        extra = rest[1] if len(rest) > 1 else {}
        if dtype == DT and "formatString" not in extra:
            extra = {"formatString": "Short Date", **extra}
        out.append((name, dtype, MTYPE[dtype], hidden, extra))
    return out


TABLES = {
    "fact_orders": cols(
        ("order_id", S), ("customer_id", S, True), ("order_date", DT), ("order_status", S),
        ("carrier", S), ("payment_type", S), ("order_total", D, True), ("shipping_fee", D, True),
        ("items_revenue", D, True), ("items_margin", D, True), ("items_count", I, True),
        ("max_discount_pct", I, True), ("delivery_days", D, True), ("delay_days", I, True),
        ("is_late", B), ("delivery_band", S, False, {"sortByColumn": "delivery_band_order"}),
        ("delivery_band_order", I, True),
        ("review_score", I), ("customer_order_number", I, True), ("is_first_order", B),
        ("customer_has_repeat", B), ("payment_mismatch", B)),
    "fact_order_items": cols(
        ("order_id", S, True), ("order_item_id", I, True), ("customer_id", S, True),
        ("product_id", S, True), ("order_date", DT, True), ("order_status", S, True),
        ("quantity", I, True), ("unit_price", D, True), ("discount_pct", I, True),
        ("line_revenue", D, True), ("line_cost", D, True), ("line_margin", D, True)),
    "dim_customer": cols(
        ("customer_id", S, True), ("city", S), ("state_code", S),
        ("state_name", S, False, {"dataCategory": "StateOrProvince"}), ("region", S),
        ("acquisition_channel", S), ("signup_date", DT)),
    "dim_product": cols(
        ("product_id", S, True), ("product_name", S), ("category", S), ("list_price", D, True),
        ("unit_cost", D, True), ("weight_kg", D, True)),
    "dim_date": cols(
        ("date", DT, False, {"isKey": None}), ("year", I), ("quarter", S), ("month_num", I, True),
        ("month", S, False, {"sortByColumn": "month_num"}), ("year_month", S), ("weekday", S)),
    "customer_rfm": cols(
        ("customer_id", S, True), ("recency_days", I, True), ("frequency", I, True),
        ("monetary", D, True), ("first_order", S, True), ("last_order", S, True),
        ("r_score", I), ("f_score", I), ("m_score", I), ("rfm_code", S), ("segment_order", I, True),
        ("segment", S, False, {"sortByColumn": "segment_order"})),
}

SEGMENTS = ["Champions", "Loyal", "Potential Loyalists", "New Customers", "Need Attention",
            "At Risk", "Hibernating", "Lost"]
CALC_COLUMNS = {}  # sort orders come from the data (a calculated sort column would be circular)

CUR, CUR2, PCT, INT, DEC1, DEC2 = (r"\$#,0;(\$#,0);\$#,0", r"\$#,0.00;(\$#,0.00);\$#,0.00",
                                   "0.0%;-0.0%;0.0%", "#,0", "#,0.0", "#,0.00")
NOT_CANCELED = 'fact_orders[order_status] <> "canceled"'
DELIVERED = 'fact_orders[order_status] = "delivered"'
ITEM_OK = 'fact_order_items[order_status] <> "canceled"'
MEASURES = [  # (table, name, DAX, formatString, display folder)
    ("fact_orders", "Revenue", f"CALCULATE ( SUM ( fact_orders[order_total] ), {NOT_CANCELED} )", CUR, "Sales"),
    ("fact_orders", "Orders", f"CALCULATE ( COUNTROWS ( fact_orders ), {NOT_CANCELED} )", INT, "Sales"),
    ("fact_orders", "Customers",
     f"CALCULATE ( DISTINCTCOUNT ( fact_orders[customer_id] ), {NOT_CANCELED} )", INT, "Sales"),
    ("fact_orders", "Avg Order Value", "DIVIDE ( [Revenue], [Orders] )", CUR2, "Sales"),
    ("fact_orders", "Revenue PY", "CALCULATE ( [Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )", CUR, "Sales"),
    ("fact_orders", "Revenue YoY %", "DIVIDE ( [Revenue] - [Revenue PY], [Revenue PY] )", PCT, "Sales"),
    ("fact_orders", "Canceled Orders",
     'CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[order_status] = "canceled" )', INT, "Sales"),
    ("fact_orders", "Repeat Customers",
     "COUNTROWS ( FILTER ( VALUES ( fact_orders[customer_id] ), [Orders] > 1 ) )", INT, "Customers"),
    ("fact_orders", "Repeat Rate %", "DIVIDE ( [Repeat Customers], [Customers] )", PCT, "Customers"),
    ("fact_orders", "Came Back %",
     f"VAR FirstOrders = CALCULATETABLE ( fact_orders, fact_orders[is_first_order] = TRUE (), {DELIVERED}, "
     "fact_orders[order_date] < DATE ( 2025, 7, 1 ) ) "
     "RETURN DIVIDE ( COUNTROWS ( FILTER ( FirstOrders, fact_orders[customer_has_repeat] = TRUE () ) ), "
     "COUNTROWS ( FirstOrders ) )", PCT, "Customers"),
    ("fact_orders", "Delivered Orders", f"CALCULATE ( COUNTROWS ( fact_orders ), {DELIVERED} )", INT, "Delivery"),
    ("fact_orders", "Late Orders",
     f"CALCULATE ( COUNTROWS ( fact_orders ), {DELIVERED}, fact_orders[is_late] = TRUE () )", INT, "Delivery"),
    ("fact_orders", "Late Rate %", "DIVIDE ( [Late Orders], [Delivered Orders] )", PCT, "Delivery"),
    ("fact_orders", "Avg Delivery Days",
     f"CALCULATE ( AVERAGE ( fact_orders[delivery_days] ), {DELIVERED} )", DEC1, "Delivery"),
    ("fact_orders", "Avg Review Score", "AVERAGE ( fact_orders[review_score] )", DEC2, "Reviews"),
    ("fact_orders", "Low Reviews %",
     "DIVIDE ( CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[review_score] <= 2, "
     "NOT ISBLANK ( fact_orders[review_score] ) ), "
     "CALCULATE ( COUNTROWS ( fact_orders ), NOT ISBLANK ( fact_orders[review_score] ) ) )", PCT, "Reviews"),
    ("fact_orders", "Payment Mismatches",
     "CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[payment_mismatch] = TRUE () )", INT, "Finance"),
    ("fact_orders", "Review Color",
     f'SWITCH ( TRUE (), [Avg Review Score] < 3, "{RED}", [Avg Review Score] < 4, "{ORANGE}", "{BLUE}" )',
     None, "Formatting"),
    ("fact_orders", "Came Back Color",
     f'SWITCH ( TRUE (), [Came Back %] < 0.15, "{RED}", [Came Back %] < 0.27, "{ORANGE}", "{BLUE}" )',
     None, "Formatting"),
    ("fact_orders", "Late Color",
     f'SWITCH ( TRUE (), [Late Rate %] >= 0.2, "{RED}", [Late Rate %] >= 0.12, "{ORANGE}", "{BLUE}" )',
     None, "Formatting"),
    ("fact_order_items", "Item Revenue", f"CALCULATE ( SUM ( fact_order_items[line_revenue] ), {ITEM_OK} )",
     CUR, "Products"),
    ("fact_order_items", "Gross Margin", f"CALCULATE ( SUM ( fact_order_items[line_margin] ), {ITEM_OK} )",
     CUR, "Products"),
    ("fact_order_items", "Gross Margin %", "DIVIDE ( [Gross Margin], [Item Revenue] )", PCT, "Products"),
    ("fact_order_items", "Units Sold", f"CALCULATE ( SUM ( fact_order_items[quantity] ), {ITEM_OK} )",
     INT, "Products"),
    ("fact_order_items", "Margin Color",
     f'SWITCH ( TRUE (), [Gross Margin %] < 0.4, "{RED}", [Gross Margin %] < 0.47, "{ORANGE}", "{BLUE}" )',
     None, "Formatting"),
    ("customer_rfm", "Scored Customers", "COUNTROWS ( customer_rfm )", INT, "RFM"),
    ("customer_rfm", "Lifetime Revenue", "SUM ( customer_rfm[monetary] )", CUR, "RFM"),
    ("customer_rfm", "% of Customers",
     "DIVIDE ( [Scored Customers], CALCULATE ( [Scored Customers], ALL ( customer_rfm ) ) )", PCT, "RFM"),
    ("customer_rfm", "% of Revenue",
     "DIVIDE ( [Lifetime Revenue], CALCULATE ( [Lifetime Revenue], ALL ( customer_rfm ) ) )", PCT, "RFM"),
    ("customer_rfm", "Avg Recency Days", "AVERAGE ( customer_rfm[recency_days] )", "#,0", "RFM"),
    ("customer_rfm", "Avg Orders per Customer", "AVERAGE ( customer_rfm[frequency] )", DEC2, "RFM"),
    ("customer_rfm", "Avg Lifetime Spend", "DIVIDE ( [Lifetime Revenue], [Scored Customers] )", CUR, "RFM"),
    ("customer_rfm", "Top Segments Revenue Share",
     'CALCULATE ( [% of Revenue], customer_rfm[segment] IN { "Champions", "Loyal" } )', PCT, "RFM"),
]

RELATIONSHIPS = [
    ("fact_orders", "order_date", "dim_date", "date"),
    ("fact_orders", "customer_id", "dim_customer", "customer_id"),
    ("fact_orders", "customer_id", "customer_rfm", "customer_id"),
    ("fact_order_items", "order_date", "dim_date", "date"),
    ("fact_order_items", "customer_id", "dim_customer", "customer_id"),
    ("fact_order_items", "customer_id", "customer_rfm", "customer_id"),
    ("fact_order_items", "product_id", "dim_product", "product_id"),
]

MEASURE_HOME = {name: t for t, name, *_ in MEASURES}


def q(name):
    """Quote a TMDL object name when needed."""
    return name if name.replace("_", "").isalnum() else f"'{name}'"


def tmdl_table(table):
    cols = TABLES[table]
    out = [f"table {table}", f"\tlineageTag: {gid(table)}", ""]
    if table == "dim_date":
        out[1:1] = ["\tdataCategory: Time"]
    for mt, name, dax, fmt, folder in MEASURES:
        if mt == table:
            out.append(f"\tmeasure {q(name)} = {dax}")
            if fmt:
                out.append(f"\t\tformatString: {fmt}")
            out += [f"\t\tdisplayFolder: {folder}", f"\t\tlineageTag: {gid(table, 'm', name)}", ""]
    for name, dtype, _, hidden, extra in cols:
        out += [f"\tcolumn {name}", f"\t\tdataType: {dtype}"]
        if hidden:
            out.append("\t\tisHidden")
        for k, v in extra.items():
            out.append(f"\t\t{k}" if v is None else f"\t\t{k}: {v}")
        if "formatString" not in extra and dtype == "int64":
            out.append("\t\tformatString: 0")
        summ = "sum" if dtype in ("double",) else "none"
        out += [f"\t\tlineageTag: {gid(table, name)}", f"\t\tsummarizeBy: {summ}",
                f"\t\tsourceColumn: {name}", "", "\t\tannotation SummarizationSetBy = Automatic", ""]
    for name, dtype, dax, extra in CALC_COLUMNS.get(table, []):
        out += [f"\tcolumn {name} = {dax}", f"\t\tdataType: {dtype}"]
        for k, v in extra.items():
            out.append(f"\t\t{k}" if v is None else f"\t\t{k}: {v}")
        out += [f"\t\tlineageTag: {gid(table, name)}", "\t\tsummarizeBy: none", "",
                "\t\tannotation SummarizationSetBy = Automatic", ""]

    types = ", ".join(f'{{"{n}", {m}}}' for n, _, m, _, _ in cols if m != "logical")
    bools = [n for n, _, m, _, _ in cols if m == "logical"]
    m = [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "{table}.csv"), '
        '[Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        '    Blanks = Table.TransformColumns(Promoted, {}, each if _ = "" then null else _),',
        f'    Typed = Table.TransformColumnTypes(Blanks, {{{types}}}, "en-US")'
        + ("," if bools else ""),
    ]
    if bools:
        conv = ", ".join(f'{{"{b}", each if _ = null then null else _ = "True", type logical}}' for b in bools)
        m.append(f"    Logicals = Table.TransformColumns(Typed, {{{conv}}})")
    m += ["in", "    Logicals" if bools else "    Typed"]
    out += [f"\tpartition {table} = m", "\t\tmode: import", "\t\tsource ="]
    out += ["\t\t\t\t" + line for line in m]
    out += ["", "\tannotation PBI_ResultType = Table", ""]
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
    order = json.dumps(["DataFolder", *TABLES])
    write(d / "model.tmdl", "\n".join([
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {order}",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        *[f"ref table {t}" for t in TABLES],
        "",
    ]))
    write(d / "expressions.tmdl", "\n".join([
        f'expression DataFolder = "{DATA_FOLDER}" meta [IsParameterQuery = true, Type = "Text", '
        "IsParameterQueryRequired = true]",
        f"\tlineageTag: {gid('DataFolder')}",
        "",
        "\tannotation PBI_ResultType = Text",
        "",
    ]))
    rels = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rels += [f"relationship {gid('rel', ft, fc, tt)}"]
        if fc == "order_date":
            rels += ["\tjoinOnDateBehavior: datePartOnly"]
        rels += [f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {tt}.{tc}", ""]
    write(d / "relationships.tmdl", "\n".join(rels))
    for t in TABLES:
        write(d / "tables" / f"{t}.tmdl", tmdl_table(t))


# =========================================================================
# Report (PBIR)
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


AXES_CLEAN = {"categoryAxis": [{"properties": {"showAxisTitle": lit(False)}}],
              "valueAxis": [{"properties": {"showAxisTitle": lit(False)}}]}


def col(table, column):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def mea(name, table=None):
    table = table or MEASURE_HOME[name]
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def ref(field):
    k = next(iter(field))
    return f"{field[k]['Expression']['SourceRef']['Entity']}.{field[k]['Property']}"


def proj(field, display=None):
    p = {"field": field, "queryRef": ref(field), "nativeQueryRef": field[next(iter(field))]["Property"]}
    if display:
        p["displayName"] = display
    return p


def solid(color):
    return {"solid": {"color": lit(color) if isinstance(color, str) else {"expr": color}}}


class Page:
    def __init__(self, key, title, subtitle):
        self.key, self.name = key, hid("page", key)
        self.title, self.subtitle = title, subtitle
        self.visuals = []

    def add(self, vid, x, y, w, h, visual):
        self.visuals.append({
            "$schema": f"{SCHEMA}/item/report/definition/visualContainer/{V_VISUAL}/schema.json",
            "name": hid(self.key, vid),
            "position": {"x": x, "y": y, "z": len(self.visuals) * 1000, "height": h, "width": w,
                         "tabOrder": len(self.visuals) * 1000},
            "visual": visual,
        })


def container(title=None, border=True):
    o = {}
    if title:
        o["title"] = [{"properties": {"show": lit(True), "text": lit(title),
                                      "fontColor": solid(DARK), "fontSize": lit(11), "bold": lit(True)}}]
    else:
        o["title"] = [{"properties": {"show": lit(False)}}]
    o["background"] = [{"properties": {"show": lit(True), "color": solid("#FFFFFF")}}]
    if border:
        o["border"] = [{"properties": {"show": lit(True), "color": solid("#E5E7EB"), "radius": lit(6)}}]
    o["visualHeader"] = [{"properties": {"show": lit(False)}}]
    return o


def textbox(text, size=11, bold=False, color=DARK):
    return {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": text, "textStyle": {
            "fontSize": f"{size}pt", "color": color, **({"fontWeight": "bold"} if bold else {})}}]}]}}]},
        "visualContainerObjects": {"background": [{"properties": {"show": lit(False)}}],
                                   "visualHeader": [{"properties": {"show": lit(False)}}]},
        "drillFilterOtherVisuals": True}


def chart(vtype, roles, title, sort=None, objects=None, border=True):
    v = {"visualType": vtype,
         "query": {"queryState": {r: {"projections": [proj(f) if isinstance(f, dict) else proj(*f)
                                                      for f in fs]} for r, fs in roles.items()}},
         "objects": {**(AXES_CLEAN if vtype in AXIS_VISUALS else {}), **(objects or {})},
         "visualContainerObjects": container(title, border),
         "drillFilterOtherVisuals": True}
    if sort:
        v["query"]["sortDefinition"] = {"sort": [{"field": f, "direction": d} for f, d in sort],
                                        "isDefaultSort": False}
    return v


AXIS_VISUALS = {"lineChart", "clusteredBarChart", "clusteredColumnChart", "scatterChart"}
def card(measure, label):
    lab = {"color": solid(DARK), "fontSize": lit(24)}
    if measure in MILLIONS:
        lab.update(labelDisplayUnits=lit(1000000), labelPrecision=lit_int(2))
    elif measure in EXACT:
        lab.update(labelDisplayUnits=lit(1))
    return chart("card", {"Values": [(mea(measure), label)]}, None, objects={
        "labels": [{"properties": lab}],
        "categoryLabels": [{"properties": {"show": lit(True), "color": solid(GREY), "fontSize": lit(10)}}]})


def slicer(field, label, group):
    v = chart("slicer", {"Values": [(field, label)]}, label, objects={
        "data": [{"properties": {"mode": lit("Dropdown")}}],
        "header": [{"properties": {"show": lit(False)}}]})
    v["syncGroup"] = {"groupName": group, "fieldChanges": True, "filterChanges": True}
    return v


def single_fill(color):
    return {"dataPoint": [{"properties": {"fill": solid(color)}}]}


def labels_on():
    return {"labels": [{"properties": {"show": lit(True)}}]}


MILLIONS = {"Revenue", "Lifetime Revenue", "Item Revenue", "Gross Margin"}
EXACT = {"Orders", "Customers", "Scored Customers", "Units Sold"}
ALL_SLICERS = [(col("dim_date", "year"), "Year", "year"),
               (col("dim_customer", "region"), "Region", "region"),
               (col("dim_customer", "acquisition_channel"), "Channel", "channel"),
               (col("customer_rfm", "segment"), "RFM segment", "segment")]


def fill(measure):
    return {"dataPoint": [{"properties": {"fill": solid(mea(measure))},
                           "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]}


def page_frame(p, slicers=ALL_SLICERS):
    p.add("title", 16, 4, 640, 48, textbox(p.title, 20, True))
    p.add("subtitle", 16, 48, 640, 30, textbox(p.subtitle, 10, False, GREY))
    x0 = 1264 - len(slicers) * 150 + 8
    for i, (f, label, g) in enumerate(slicers):
        p.add(f"slicer_{g}", x0 + i * 150, 10, 142, 60, slicer(f, label, g))


def kpi_row(p, kpis):
    n = len(kpis)
    cw = (1280 - 32 - (n - 1) * 12) / n
    for i, (m, label) in enumerate(kpis):
        p.add(f"kpi_{i}", 16 + i * (cw + 12), 82, cw, 92, card(m, label))


def build_pages():
    pages = []
    CAT = (col("dim_product", "category"), "Category")

    # ---- 1. Sales overview -------------------------------------------------
    p = Page("overview", "Sales Overview",
             "Revenue +55% in 2024 and +32% in 2025; Nov-Dec is about a quarter of each year.")
    page_frame(p)
    kpi_row(p, [("Revenue", "Revenue"), ("Orders", "Orders"), ("Customers", "Customers"),
                ("Avg Order Value", "Avg order value"), ("Repeat Rate %", "Customers who ordered again")])
    p.add("trend", 16, 186, 820, 250, chart(
        "lineChart", {"Category": [(col("dim_date", "year_month"), "Month")], "Y": [mea("Revenue")]},
        "Revenue by month", sort=[(col("dim_date", "year_month"), "Ascending")],
        objects=single_fill(BLUE)))
    p.add("category", 848, 186, 416, 250, chart(
        "clusteredBarChart", {"Category": [CAT], "Y": [mea("Item Revenue")],
                              "Tooltips": [mea("Gross Margin %")]},
        "Revenue by category (colour = margin)", sort=[(mea("Item Revenue"), "Descending")],
        objects=fill("Margin Color")))
    p.add("channel", 16, 448, 620, 262, chart(
        "clusteredBarChart", {"Category": [(col("dim_customer", "acquisition_channel"), "Channel")],
                              "Y": [mea("Repeat Rate %")], "Tooltips": [mea("Customers")]},
        "Share of customers who ordered again, by acquisition channel",
        sort=[(mea("Repeat Rate %"), "Descending")], objects={**single_fill(BLUE), **labels_on()}))
    p.add("region", 648, 448, 616, 262, chart(
        "clusteredBarChart", {"Category": [(col("dim_customer", "region"), "Region")],
                              "Y": [mea("Revenue")], "Tooltips": [mea("Late Rate %")]},
        "Revenue by region", sort=[(mea("Revenue"), "Descending")],
        objects={**single_fill(GREY), **labels_on()}))
    pages.append(p)

    # ---- 2. RFM segments ------------------------------------------------------
    p = Page("segments", "Customer Segments (RFM)",
             "Champions + Loyal: 8% of customers, 25% of revenue. Lifetime figures to Dec 2025.")
    page_frame(p, [ALL_SLICERS[3]])
    kpi_row(p, [("Scored Customers", "Customers scored"), ("Avg Lifetime Spend", "Avg lifetime spend"),
                ("Avg Orders per Customer", "Avg orders per customer"),
                ("Top Segments Revenue Share", "Revenue from Champions + Loyal")])
    SEG = (col("customer_rfm", "segment"), "Segment")
    p.add("share", 16, 186, 620, 524, chart(
        "clusteredBarChart", {"Category": [SEG], "Y": [mea("% of Customers"), mea("% of Revenue")]},
        "Share of customers vs share of revenue", sort=[(col("customer_rfm", "segment"), "Ascending")],
        objects={"dataPoint": [{"properties": {"fill": solid(GREY)},
                                "selector": {"metadata": "customer_rfm.% of Customers"}},
                               {"properties": {"fill": solid(BLUE)},
                                "selector": {"metadata": "customer_rfm.% of Revenue"}}],
                 **labels_on()}))
    p.add("table", 648, 186, 616, 262, chart(
        "tableEx", {"Values": [SEG, (mea("Scored Customers"), "Customers"), (mea("Lifetime Revenue"), "Revenue"),
                               (mea("Avg Recency Days"), "Days since last order"),
                               (mea("Avg Orders per Customer"), "Orders"), (mea("Avg Lifetime Spend"), "Avg spend")]},
        "Segment profile", sort=[(col("customer_rfm", "segment"), "Ascending")]))
    p.add("rf", 648, 460, 616, 250, chart(
        "pivotTable", {"Rows": [(col("customer_rfm", "r_score"), "Recency score")],
                       "Columns": [(col("customer_rfm", "f_score"), "Frequency score")],
                       "Values": [(mea("Avg Lifetime Spend"), "Avg spend")]},
        "Average spend by recency (rows) and frequency (columns) score",
        sort=[(col("customer_rfm", "r_score"), "Descending")]))
    pages.append(p)

    # ---- 3. Delivery & reviews -------------------------------------------------
    p = Page("delivery", "Delivery & Reviews",
             "Every day late costs review stars, and a first order 4+ days late cuts the return rate to under a quarter.")
    page_frame(p)
    kpi_row(p, [("Late Rate %", "Delivered after promised date"), ("Avg Delivery Days", "Avg days to deliver"),
                ("Avg Review Score", "Avg review score"), ("Low Reviews %", "1- and 2-star reviews")])
    BAND = (col("fact_orders", "delivery_band"), "Delivery")
    p.add("score", 16, 186, 620, 262, chart(
        "clusteredColumnChart", {"Category": [BAND], "Y": [mea("Avg Review Score")]},
        "Average review score by delivery delay", sort=[(col("fact_orders", "delivery_band"), "Ascending")],
        objects={**fill("Review Color"), **labels_on()}))
    p.add("cameback", 648, 186, 616, 262, chart(
        "clusteredColumnChart", {"Category": [BAND], "Y": [(mea("Came Back %"), "Ordered again")]},
        "Customers who ordered again, by how late their FIRST order was",
        sort=[(col("fact_orders", "delivery_band"), "Ascending")],
        objects={**fill("Came Back Color"), **labels_on()}))
    p.add("matrix", 16, 460, 620, 250, chart(
        "pivotTable", {"Rows": [(col("fact_orders", "carrier"), "Carrier")],
                       "Columns": [(col("dim_customer", "region"), "Region")],
                       "Values": [(mea("Late Rate %"), "Late %")]},
        "Late-delivery rate by carrier and region"))
    p.add("carrier", 648, 460, 616, 250, chart(
        "clusteredBarChart", {"Category": [(col("fact_orders", "carrier"), "Carrier")],
                              "Y": [mea("Late Rate %")], "Tooltips": [mea("Delivered Orders")]},
        "Late-delivery rate by carrier", sort=[(mea("Late Rate %"), "Descending")],
        objects={**fill("Late Color"), **labels_on()}))
    pages.append(p)

    # ---- 4. Products ------------------------------------------------------------
    p = Page("products", "Products",
             "Furniture: 15% of revenue at a 31.5% margin, the lowest of any category, and the weakest reviews.")
    page_frame(p)
    kpi_row(p, [("Item Revenue", "Product revenue"), ("Gross Margin", "Gross margin"),
                ("Gross Margin %", "Gross margin %"), ("Units Sold", "Units sold")])
    p.add("catrev", 16, 186, 620, 262, chart(
        "clusteredBarChart", {"Category": [CAT], "Y": [mea("Item Revenue")], "Tooltips": [mea("Gross Margin %")]},
        "Revenue by category", sort=[(mea("Item Revenue"), "Descending")],
        objects={**single_fill(BLUE), **labels_on()}))
    p.add("catmargin", 648, 186, 616, 262, chart(
        "clusteredBarChart", {"Category": [CAT], "Y": [mea("Gross Margin %")]},
        "Gross margin % by category", sort=[(mea("Gross Margin %"), "Descending")],
        objects={**fill("Margin Color"), **labels_on()}))
    p.add("top", 16, 460, 1248, 250, chart(
        "tableEx", {"Values": [(col("dim_product", "product_name"), "Product"), CAT,
                               mea("Units Sold"), (mea("Item Revenue"), "Revenue"), mea("Gross Margin %")]},
        "Products ranked by revenue", sort=[(mea("Item Revenue"), "Descending")]))
    pages.append(p)
    return pages


def build_report():
    if RP.exists():
        shutil.rmtree(RP)
    write_json(RP / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    write_json(RP / ".platform", {
        "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": gid("report")}})
    theme_dst = RP / "StaticResources" / "SharedResources" / "BaseThemes" / f"{BASE_THEME}.json"
    theme_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(THEME_SRC, theme_dst)

    d = RP / "definition"
    write_json(d / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"})
    write_json(d / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/{V_REPORT}/schema.json",
        "themeCollection": {"baseTheme": {
            "name": BASE_THEME,
            "reportVersionAtImport": {"visual": V_VISUAL, "report": V_REPORT, "page": V_PAGE},
            "type": "SharedResources"}},
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources", "items": [
            {"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json", "type": "BaseTheme"}]}],
        "objects": {"outspacePane": [{"properties": {"expanded": lit(False)}}]},
        "settings": {"useStylableVisualContainerHeader": True,
                     "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True}})
    pages = build_pages()
    write_json(d / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name})
    for p in pages:
        pd_ = d / "pages" / p.name
        write_json(pd_ / "page.json", {
            "$schema": f"{SCHEMA}/item/report/definition/page/{V_PAGE}/schema.json",
            "name": p.name, "displayName": p.title, "displayOption": "FitToPage",
            "height": 720, "width": W_PAGE,
            "objects": {"background": [{"properties": {"color": solid("#F3F4F6"),
                                                        "transparency": lit(0)}}]}})
        for v in p.visuals:
            write_json(pd_ / "visuals" / v["name"] / "visual.json", v)
    return pages


W_PAGE = 1280

if __name__ == "__main__":
    build_semantic_model()
    pages = build_report()
    write_json(PBI / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}})
    write(PBI / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print(f"wrote {PBI / (NAME + '.pbip')}")
    print(f"  semantic model: {len(TABLES)} tables, {len(MEASURES)} measures, "
          f"{len(RELATIONSHIPS)} relationships")
    print(f"  report: {len(pages)} pages, {sum(len(p.visuals) for p in pages)} visuals")
