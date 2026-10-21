-- ==============================================================================
-- 6-Month Revenue per Customer (Cohorts Jan 2010 to Jun 2011)
-- File: sql/revenue_6m_fixed_window.sql
-- Description: Measures cohort revenue during months 0 to 5 (first 6 months).
--   Evaluates mean and median for both clean and deduplicated datasets.
-- ==============================================================================

WITH cust_cohort AS (
    SELECT 
        "Customer ID" AS customer_id,
        date_trunc('month', MIN(InvoiceDate)) AS cohort_month,
        strftime(date_trunc('month', MIN(InvoiceDate)), '%Y-%m') AS cohort_str
    FROM read_parquet('data/clean/clean.parquet')
    GROUP BY "Customer ID"
),
clean_rev_6m AS (
    SELECT 
        t."Customer ID" AS customer_id,
        SUM(t.revenue) AS rev_6m_clean
    FROM read_parquet('data/clean/clean.parquet') t
    JOIN cust_cohort c ON t."Customer ID" = c.customer_id
    WHERE datediff('month', c.cohort_month, date_trunc('month', t.InvoiceDate)) BETWEEN 0 AND 5
    GROUP BY t."Customer ID"
),
dedup_rev_6m AS (
    SELECT 
        t."Customer ID" AS customer_id,
        SUM(t.revenue) AS rev_6m_dedup
    FROM read_parquet('data/clean/clean_dedup.parquet') t
    JOIN cust_cohort c ON t."Customer ID" = c.customer_id
    WHERE datediff('month', c.cohort_month, date_trunc('month', t.InvoiceDate)) BETWEEN 0 AND 5
    GROUP BY t."Customer ID"
),
customer_level AS (
    SELECT 
        c.customer_id,
        c.cohort_str,
        CASE 
            WHEN c.cohort_str IN ('2010-11', '2010-12') THEN 'Holiday Cohorts (Nov-Dec 2010)'
            ELSE 'Other Cohorts (Jan 2010 - Jun 2011)'
        END AS cohort_group,
        COALESCE(cr.rev_6m_clean, 0.0) AS rev_6m_clean,
        COALESCE(dr.rev_6m_dedup, 0.0) AS rev_6m_dedup
    FROM cust_cohort c
    LEFT JOIN clean_rev_6m cr ON c.customer_id = cr.customer_id
    LEFT JOIN dedup_rev_6m dr ON c.customer_id = dr.customer_id
    WHERE c.cohort_str >= '2010-01' AND c.cohort_str <= '2011-06'
)
SELECT 
    cohort_group,
    COUNT(*) AS n_customers,
    ROUND(AVG(rev_6m_clean), 2) AS mean_rev_6m_clean,
    ROUND(MEDIAN(rev_6m_clean), 2) AS median_rev_6m_clean,
    ROUND(AVG(rev_6m_dedup), 2) AS mean_rev_6m_dedup,
    ROUND(MEDIAN(rev_6m_dedup), 2) AS median_rev_6m_dedup
FROM customer_level
GROUP BY cohort_group
ORDER BY 
    CASE WHEN cohort_group LIKE 'Holiday%' THEN 1 ELSE 2 END;
