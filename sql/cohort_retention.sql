-- ==============================================================================
-- Cohort Retention Analysis
-- File: sql/cohort_retention.sql
-- Description: Calculates monthly cohort retention from month 0 to month N.
-- Definitions:
--   - Cohort: Month of a customer's first valid purchase (min InvoiceDate)
--   - month_n: Calendar months elapsed between cohort month and transaction month
--   - Retained in month N: Customer has at least one valid invoice in month N
--   - Retention Pct: (active_customers in month N / cohort_size in month 0) * 100
-- ==============================================================================

WITH customer_cohort AS (
    -- Step 1: Identify the acquisition month (cohort) for each distinct customer
    SELECT 
        "Customer ID" AS customer_id,
        date_trunc('month', MIN(InvoiceDate)) AS cohort_month
    FROM read_parquet('data/clean/clean.parquet')
    GROUP BY "Customer ID"
),
cohort_sizes AS (
    -- Step 2: Calculate baseline cohort size (month 0 denominator)
    SELECT 
        cohort_month,
        COUNT(DISTINCT customer_id) AS cohort_size
    FROM customer_cohort
    GROUP BY cohort_month
),
customer_monthly_activity AS (
    -- Step 3: Determine which months each customer made at least one valid purchase
    SELECT DISTINCT
        t."Customer ID" AS customer_id,
        c.cohort_month,
        datediff('month', c.cohort_month, date_trunc('month', t.InvoiceDate)) AS month_n
    FROM read_parquet('data/clean/clean.parquet') t
    JOIN customer_cohort c 
        ON t."Customer ID" = c.customer_id
),
retention_summary AS (
    -- Step 4: Aggregate active customers by cohort and month_n, compute retention %
    SELECT 
        ca.cohort_month,
        strftime(ca.cohort_month, '%Y-%m') AS cohort,
        ca.month_n,
        COUNT(DISTINCT ca.customer_id) AS active_customers,
        cs.cohort_size,
        ROUND(COUNT(DISTINCT ca.customer_id) * 100.0 / cs.cohort_size, 2) AS retention_pct
    FROM customer_monthly_activity ca
    JOIN cohort_sizes cs 
        ON ca.cohort_month = cs.cohort_month
    GROUP BY ca.cohort_month, cs.cohort_size, ca.month_n
)
SELECT 
    cohort,
    month_n,
    active_customers,
    cohort_size,
    retention_pct
FROM retention_summary
ORDER BY cohort, month_n;
