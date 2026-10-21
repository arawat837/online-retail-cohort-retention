-- ==============================================================================
-- Calendar-Month Activity (Existing Customer Repeat Rate)
-- File: sql/calendar_activity.sql
-- Description: For each calendar month from Jan 2010 to Nov 2011, computes:
--   - acquired_before: Customers acquired strictly prior to the calendar month
--   - active_customers: Distinct customers from that prior base purchasing in that month
--   - activity_rate_pct: active_customers / acquired_before * 100
-- ==============================================================================

WITH customer_cohort AS (
    SELECT 
        "Customer ID" AS customer_id,
        date_trunc('month', MIN(InvoiceDate)) AS cohort_month
    FROM read_parquet('data/clean/clean.parquet')
    GROUP BY "Customer ID"
),
calendar_months AS (
    SELECT UNNEST(GENERATE_SERIES(DATE '2010-01-01', DATE '2011-11-01', INTERVAL 1 MONTH)) AS cal_month
),
monthly_metrics AS (
    SELECT 
        strftime(m.cal_month, '%Y-%m') AS calendar_month,
        COUNT(DISTINCT c.customer_id) AS acquired_before,
        COUNT(DISTINCT CASE 
            WHEN t.Invoice IS NOT NULL THEN c.customer_id 
        END) AS active_customers,
        ROUND(
            COUNT(DISTINCT CASE WHEN t.Invoice IS NOT NULL THEN c.customer_id END) * 100.0 / 
            COUNT(DISTINCT c.customer_id), 
            2
        ) AS activity_rate_pct
    FROM calendar_months m
    JOIN customer_cohort c 
        ON c.cohort_month < m.cal_month
    LEFT JOIN read_parquet('data/clean/clean.parquet') t 
        ON c.customer_id = t."Customer ID" 
        AND date_trunc('month', t.InvoiceDate) = m.cal_month
    GROUP BY m.cal_month
    ORDER BY m.cal_month
)
SELECT * FROM monthly_metrics;
