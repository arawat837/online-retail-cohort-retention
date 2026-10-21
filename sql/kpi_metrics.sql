-- ==============================================================================
-- Cohort KPIs Calculation (Clean vs Deduplicated)
-- File: sql/kpi_metrics.sql
-- Description: Computes key customer lifecycle and monetization metrics per cohort:
--   - Cohort Size (n_customers)
--   - Month-1 Retention Rate (%)
--   - Repeat Purchase Rate (Customers with >= 2 distinct invoices / total customers)
--   - Average Order Value (AOV = total revenue / COUNT DISTINCT Invoice)
--   - Revenue per Customer in First 6 Months (months 0 to 5)
-- Computes both clean.parquet and clean_dedup.parquet side by side.
-- ==============================================================================

WITH customer_cohort AS (
    SELECT 
        "Customer ID" AS customer_id,
        date_trunc('month', MIN(InvoiceDate)) AS cohort_month
    FROM read_parquet('data/clean/clean.parquet')
    GROUP BY "Customer ID"
),
clean_invoices AS (
    SELECT 
        t."Customer ID" AS customer_id,
        t.Invoice,
        MIN(t.InvoiceDate) AS invoice_date,
        SUM(t.revenue) AS invoice_revenue,
        c.cohort_month,
        datediff('month', c.cohort_month, date_trunc('month', MIN(t.InvoiceDate))) AS month_n
    FROM read_parquet('data/clean/clean.parquet') t
    JOIN customer_cohort c ON t."Customer ID" = c.customer_id
    GROUP BY t."Customer ID", t.Invoice, c.cohort_month
),
dedup_invoices AS (
    SELECT 
        t."Customer ID" AS customer_id,
        t.Invoice,
        MIN(t.InvoiceDate) AS invoice_date,
        SUM(t.revenue) AS invoice_revenue,
        c.cohort_month,
        datediff('month', c.cohort_month, date_trunc('month', MIN(t.InvoiceDate))) AS month_n
    FROM read_parquet('data/clean/clean_dedup.parquet') t
    JOIN customer_cohort c ON t."Customer ID" = c.customer_id
    GROUP BY t."Customer ID", t.Invoice, c.cohort_month
),
customer_summary_clean AS (
    SELECT 
        customer_id,
        cohort_month,
        COUNT(DISTINCT Invoice) AS invoice_count,
        MAX(CASE WHEN month_n = 1 THEN 1 ELSE 0 END) AS is_active_m1,
        SUM(invoice_revenue) AS total_revenue,
        SUM(CASE WHEN month_n BETWEEN 0 AND 5 THEN invoice_revenue ELSE 0 END) AS rev_first_6m
    FROM clean_invoices
    GROUP BY customer_id, cohort_month
),
customer_summary_dedup AS (
    SELECT 
        customer_id,
        cohort_month,
        SUM(invoice_revenue) AS total_revenue_dedup,
        SUM(CASE WHEN month_n BETWEEN 0 AND 5 THEN invoice_revenue ELSE 0 END) AS rev_first_6m_dedup
    FROM dedup_invoices
    GROUP BY customer_id, cohort_month
)
SELECT 
    strftime(c.cohort_month, '%Y-%m') AS cohort,
    COUNT(DISTINCT c.customer_id) AS n_customers,
    -- Month 1 Retention
    COUNT(DISTINCT CASE WHEN c.is_active_m1 = 1 THEN c.customer_id END) AS m1_active_customers,
    ROUND(COUNT(DISTINCT CASE WHEN c.is_active_m1 = 1 THEN c.customer_id END) * 100.0 / COUNT(DISTINCT c.customer_id), 2) AS m1_retention_pct,
    -- Repeat Purchase Rate (>= 2 distinct invoices)
    COUNT(DISTINCT CASE WHEN c.invoice_count >= 2 THEN c.customer_id END) AS repeat_customers,
    ROUND(COUNT(DISTINCT CASE WHEN c.invoice_count >= 2 THEN c.customer_id END) * 100.0 / COUNT(DISTINCT c.customer_id), 2) AS repeat_purchase_rate_pct,
    -- AOV
    ROUND(SUM(c.total_revenue) / SUM(c.invoice_count), 2) AS aov_clean,
    ROUND(SUM(d.total_revenue_dedup) / SUM(c.invoice_count), 2) AS aov_dedup,
    ROUND((ROUND(SUM(d.total_revenue_dedup) / SUM(c.invoice_count), 2) - ROUND(SUM(c.total_revenue) / SUM(c.invoice_count), 2)) * 100.0 / ROUND(SUM(c.total_revenue) / SUM(c.invoice_count), 2), 2) AS aov_diff_pct,
    -- Revenue per Customer in First 6 Months (m0 to m5)
    ROUND(SUM(c.rev_first_6m) / COUNT(DISTINCT c.customer_id), 2) AS rev_per_cust_6m_clean,
    ROUND(SUM(d.rev_first_6m_dedup) / COUNT(DISTINCT c.customer_id), 2) AS rev_per_cust_6m_dedup,
    ROUND((ROUND(SUM(d.rev_first_6m_dedup) / COUNT(DISTINCT c.customer_id), 2) - ROUND(SUM(c.rev_first_6m) / COUNT(DISTINCT c.customer_id), 2)) * 100.0 / ROUND(SUM(c.rev_first_6m) / COUNT(DISTINCT c.customer_id), 2), 2) AS rev_per_cust_6m_diff_pct
FROM customer_summary_clean c
JOIN customer_summary_dedup d ON c.customer_id = d.customer_id
GROUP BY c.cohort_month
ORDER BY c.cohort_month;
