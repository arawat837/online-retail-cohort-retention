-- ==============================================================================
-- Fixed-Window KPIs: 90-Day Repeat Rate & 6-Month Customer Revenue
-- File: sql/fixed_window_kpis.sql
-- Description:
--   1. repeat_90d: Placed a 2nd distinct invoice within 90 days of first invoice.
--      Evaluated for customers acquired on or before 2011-09-10 (full 90-day window).
--   2. 6-Month Revenue: Revenue in months 0-5 of cohort. Evaluated for cohorts
--      Jan 2010 to Jun 2011. Reports mean and median for clean and deduplicated data.
-- ==============================================================================

-- Part 1: Repeat Purchase Rate within 90 Days
WITH cust_first AS (
    SELECT 
        "Customer ID" AS customer_id,
        MIN(InvoiceDate) AS first_invoice_date,
        strftime(date_trunc('month', MIN(InvoiceDate)), '%Y-%m') AS cohort_str
    FROM read_parquet('data/clean/clean.parquet')
    GROUP BY "Customer ID"
),
distinct_invoices AS (
    SELECT DISTINCT
        "Customer ID" AS customer_id,
        Invoice,
        MIN(InvoiceDate) AS invoice_date
    FROM read_parquet('data/clean/clean.parquet')
    GROUP BY "Customer ID", Invoice
),
cust_90d AS (
    SELECT 
        cf.customer_id,
        cf.cohort_str,
        CASE 
            WHEN cf.cohort_str IN ('2010-11', '2010-12') THEN 'Holiday Cohorts (Nov-Dec 2010)'
            WHEN cf.cohort_str >= '2010-01' AND cf.cohort_str <= '2011-09' THEN 'Other Eligible Cohorts (Jan 2010 - Sep 2011)'
            ELSE 'Excluded'
        END AS cohort_group,
        COUNT(DISTINCT CASE 
            WHEN di.invoice_date <= cf.first_invoice_date + INTERVAL 90 DAY 
            THEN di.Invoice 
        END) AS inv_count_90d
    FROM cust_first cf
    JOIN distinct_invoices di ON cf.customer_id = di.customer_id
    WHERE CAST(cf.first_invoice_date AS DATE) <= DATE '2011-09-10'
    GROUP BY cf.customer_id, cf.cohort_str, cf.first_invoice_date
)
SELECT 
    cohort_group,
    COUNT(DISTINCT customer_id) AS n_customers,
    COUNT(DISTINCT CASE WHEN inv_count_90d >= 2 THEN customer_id END) AS repeat_90d_customers,
    ROUND(COUNT(DISTINCT CASE WHEN inv_count_90d >= 2 THEN customer_id END) * 100.0 / COUNT(DISTINCT customer_id), 2) AS repeat_90d_rate_pct
FROM cust_90d
WHERE cohort_group IN ('Holiday Cohorts (Nov-Dec 2010)', 'Other Eligible Cohorts (Jan 2010 - Sep 2011)')
GROUP BY cohort_group
ORDER BY 
    CASE WHEN cohort_group LIKE 'Holiday%' THEN 1 ELSE 2 END;
