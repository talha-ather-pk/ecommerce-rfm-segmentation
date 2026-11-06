-- Harbor & Pine: business questions answered in SQL (SQLite 3.25+)
-- Run all of them with: python scripts/run_sql.py   (writes sql/results.md)
-- Revenue excludes canceled orders. Analysis date for recency = 2026-01-01.

-- name: 01_revenue_by_year
-- How fast is the business growing?
WITH yearly AS (
    SELECT strftime('%Y', order_purchase_timestamp) AS year,
           COUNT(*)                                  AS orders,
           COUNT(DISTINCT customer_id)               AS customers,
           ROUND(SUM(order_total), 0)                AS revenue
    FROM orders
    WHERE order_status <> 'canceled'
    GROUP BY 1
)
SELECT year, orders, customers, revenue,
       ROUND(revenue / orders, 2)                                              AS avg_order_value,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY year))
             / LAG(revenue) OVER (ORDER BY year), 1)                           AS revenue_growth_pct
FROM yearly
ORDER BY year;

-- name: 02_peak_months
-- Which months carry the year? (share of each year's revenue)
WITH m AS (
    SELECT strftime('%Y', order_purchase_timestamp) AS year,
           strftime('%m', order_purchase_timestamp) AS month,
           SUM(order_total)                         AS revenue
    FROM orders
    WHERE order_status <> 'canceled'
    GROUP BY 1, 2
), shares AS (
    SELECT year, month, revenue,
           100.0 * revenue / SUM(revenue) OVER (PARTITION BY year) AS pct_of_year
    FROM m
)
SELECT year,
       ROUND(SUM(CASE WHEN month IN ('11', '12') THEN revenue END), 0)     AS nov_dec_revenue,
       ROUND(SUM(CASE WHEN month IN ('11', '12') THEN pct_of_year END), 1) AS nov_dec_pct_of_year,
       ROUND(100.0 * 2 / 12, 1)                                            AS even_share_pct
FROM shares
GROUP BY year
ORDER BY year;

-- name: 03_repeat_rate_by_channel
-- What share of customers order more than once, by acquisition channel?
WITH per_customer AS (
    SELECT o.customer_id, c.acquisition_channel, COUNT(*) AS orders, SUM(o.order_total) AS revenue
    FROM orders o JOIN customers c USING (customer_id)
    WHERE o.order_status <> 'canceled'
    GROUP BY 1, 2
)
SELECT acquisition_channel,
       COUNT(*)                                             AS customers,
       ROUND(100.0 * AVG(orders > 1), 1)                    AS repeat_rate_pct,
       ROUND(AVG(orders), 2)                                AS avg_orders,
       ROUND(AVG(revenue), 2)                               AS avg_lifetime_revenue
FROM per_customer
GROUP BY 1
ORDER BY repeat_rate_pct DESC;

-- name: 04_days_to_second_order
-- For repeat customers, how long until the second order?
WITH ranked AS (
    SELECT customer_id, order_purchase_timestamp,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_purchase_timestamp) AS n
    FROM orders
    WHERE order_status <> 'canceled'
), gaps AS (
    SELECT julianday(b.order_purchase_timestamp) - julianday(a.order_purchase_timestamp) AS days
    FROM ranked a JOIN ranked b ON a.customer_id = b.customer_id AND a.n = 1 AND b.n = 2
)
SELECT CASE WHEN days <= 30 THEN '0-30 days' WHEN days <= 90 THEN '31-90 days'
            WHEN days <= 180 THEN '91-180 days' WHEN days <= 365 THEN '181-365 days'
            ELSE 'over a year' END                                   AS time_to_second_order,
       COUNT(*)                                                      AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)            AS pct
FROM gaps
GROUP BY 1
ORDER BY MIN(days);

-- name: 05_rfm_scores
-- RFM score per customer. R and M use quintiles (NTILE); F uses order-count bands
-- because most customers have one order and NTILE would split ties at random.
-- Saved to data_clean/customer_rfm.csv by run_sql.py.
WITH base AS (
    SELECT customer_id,
           CAST(julianday('2026-01-01') - julianday(MAX(order_purchase_timestamp)) AS INTEGER) AS recency_days,
           COUNT(*)                                       AS frequency,
           ROUND(SUM(order_total), 2)                     AS monetary,
           MIN(order_purchase_timestamp)                  AS first_order,
           MAX(order_purchase_timestamp)                  AS last_order
    FROM orders
    WHERE order_status <> 'canceled'
    GROUP BY customer_id
), scored AS (
    SELECT *,
           6 - NTILE(5) OVER (ORDER BY recency_days)      AS r_score,
           CASE WHEN frequency = 1 THEN 1 WHEN frequency = 2 THEN 2 WHEN frequency = 3 THEN 3
                WHEN frequency <= 5 THEN 4 ELSE 5 END     AS f_score,
           NTILE(5) OVER (ORDER BY monetary)              AS m_score
    FROM base
)
SELECT *,
       r_score || f_score || m_score AS rfm_code,
       CASE
           WHEN r_score >= 4 AND f_score >= 4 THEN 1
           WHEN r_score >= 3 AND f_score >= 3 THEN 2
           WHEN r_score >= 4 AND f_score = 2  THEN 3
           WHEN r_score >= 4 AND f_score = 1  THEN 4
           WHEN r_score = 3  AND f_score <= 2 THEN 5
           WHEN r_score <= 2 AND f_score >= 3 THEN 6
           WHEN r_score = 2  AND f_score <= 2 THEN 7
           ELSE 8
       END AS segment_order,   -- display order for reports
       CASE
           WHEN r_score >= 4 AND f_score >= 4 THEN 'Champions'
           WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal'
           WHEN r_score >= 4 AND f_score = 2  THEN 'Potential Loyalists'
           WHEN r_score >= 4 AND f_score = 1  THEN 'New Customers'
           WHEN r_score = 3  AND f_score <= 2 THEN 'Need Attention'
           WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk'
           WHEN r_score = 2  AND f_score <= 2 THEN 'Hibernating'
           ELSE 'Lost'
       END AS segment
FROM scored;

-- name: 06_rfm_segment_summary
-- How big is each segment and how much revenue does it hold?
SELECT segment,
       COUNT(*)                                                   AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)         AS pct_customers,
       ROUND(SUM(monetary), 0)                                    AS revenue,
       ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 1) AS pct_revenue,
       ROUND(AVG(recency_days), 0)                                AS avg_recency_days,
       ROUND(AVG(frequency), 2)                                   AS avg_orders,
       ROUND(AVG(monetary), 2)                                    AS avg_spend
FROM customer_rfm
GROUP BY segment
ORDER BY revenue DESC;

-- name: 07_late_rate_by_carrier_region
-- Where do deliveries arrive late?
SELECT o.carrier, c.region,
       COUNT(*)                                AS delivered_orders,
       ROUND(100.0 * AVG(o.is_late), 1)        AS late_pct,
       ROUND(AVG(CASE WHEN o.is_late THEN o.delay_days END), 1) AS avg_days_late
FROM orders o JOIN customers c USING (customer_id)
WHERE o.order_status = 'delivered'
GROUP BY 1, 2
ORDER BY late_pct DESC
LIMIT 8;

-- name: 08_review_score_by_delay
-- How does lateness change the review score?
SELECT CASE WHEN o.delay_days <= 0 THEN '1 On time'
            WHEN o.delay_days <= 3 THEN '2 1-3 days late'
            WHEN o.delay_days <= 7 THEN '3 4-7 days late'
            ELSE '4 8+ days late' END             AS delivery,
       COUNT(*)                                   AS reviews,
       ROUND(AVG(r.review_score), 2)              AS avg_score,
       ROUND(100.0 * AVG(r.review_score <= 2), 1) AS pct_1_or_2_stars
FROM orders o JOIN reviews r USING (order_id)
WHERE o.order_status = 'delivered'
GROUP BY 1
ORDER BY 1;

-- name: 09_first_delivery_vs_repeat
-- Do customers whose FIRST order arrived late come back less often?
-- Only first orders placed before July 2025, so every customer had 6+ months to return.
WITH ranked AS (
    SELECT o.*, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_purchase_timestamp) AS n,
           COUNT(*) OVER (PARTITION BY customer_id) AS total_orders
    FROM orders o
    WHERE order_status <> 'canceled'
)
SELECT CASE WHEN delay_days > 3 THEN 'Late by 4+ days'
            WHEN delay_days > 0 THEN 'Late by 1-3 days'
            ELSE 'On time' END                    AS first_delivery,
       COUNT(*)                                   AS customers,
       ROUND(100.0 * AVG(total_orders > 1), 1)    AS ordered_again_pct
FROM ranked
WHERE n = 1 AND order_status = 'delivered' AND order_purchase_timestamp < '2025-07-01'
GROUP BY 1
ORDER BY ordered_again_pct DESC;

-- name: 10_category_performance
-- Which categories make the money, and at what margin?
SELECT p.category,
       ROUND(SUM(i.line_revenue), 0)                              AS revenue,
       ROUND(100.0 * SUM(i.line_revenue) / SUM(SUM(i.line_revenue)) OVER (), 1) AS pct_revenue,
       ROUND(100.0 * SUM(i.line_margin) / SUM(i.line_revenue), 1) AS gross_margin_pct,
       ROUND(AVG(r.review_score), 2)                              AS avg_review
FROM order_items i
JOIN orders o   USING (order_id)
JOIN products p USING (product_id)
LEFT JOIN reviews r USING (order_id)
WHERE o.order_status <> 'canceled'
GROUP BY 1
ORDER BY revenue DESC;

-- name: 11_payment_mismatches
-- Orders where payments do not add up to the order total (for finance to check).
SELECT o.order_id, o.order_purchase_timestamp, o.order_total,
       ROUND(SUM(p.payment_value), 2)                  AS paid,
       ROUND(o.order_total - SUM(p.payment_value), 2)  AS short_by
FROM orders o JOIN payments p USING (order_id)
WHERE o.payment_mismatch = 1
GROUP BY o.order_id
ORDER BY short_by DESC
LIMIT 10;
