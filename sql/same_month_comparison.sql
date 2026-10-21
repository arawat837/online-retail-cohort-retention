-- ==============================================================================
-- Same-Month Activity Comparison (Dec 2010 and Jan 2011)
-- File: sql/same_month_comparison.sql
-- Description: Compares customer activity in specific calendar months across cohorts:
--   - Nov 2010 cohort (Month 1 in Dec 2010, Month 2 in Jan 2011)
--   - Dec 2010 cohort (Month 1 in Jan 2011; acquisition in Dec 2010)
--   - Pooled Jun-Oct 2010 cohorts (Mature cohorts observed in same calendar months)
-- ==============================================================================

WITH customer_cohort AS (
    SELECT 
        "Customer ID" AS customer_id,
        strftime(date_trunc('month', MIN(InvoiceDate)), '%Y-%m') AS cohort_str
    FROM read_parquet('data/clean/clean.parquet')
    GROUP BY "Customer ID"
),
cohort_groups AS (
    SELECT 
        customer_id,
        cohort_str,
        CASE 
            WHEN cohort_str = '2010-11' THEN 'Nov 2010 Cohort'
            WHEN cohort_str = '2010-12' THEN 'Dec 2010 Cohort'
            WHEN cohort_str IN ('2010-06', '2010-07', '2010-08', '2010-09', '2010-10') THEN 'Pooled Jun-Oct 2010 Cohorts'
            ELSE 'Other'
        END AS comp_group
    FROM customer_cohort
),
monthly_activity AS (
    SELECT DISTINCT
        "Customer ID" AS customer_id,
        strftime(date_trunc('month', InvoiceDate), '%Y-%m') AS activity_month
    FROM read_parquet('data/clean/clean.parquet')
    WHERE strftime(date_trunc('month', InvoiceDate), '%Y-%m') IN ('2010-12', '2011-01')
)
SELECT 
    cg.comp_group,
    COUNT(DISTINCT cg.customer_id) AS n_customers,
    -- Dec 2010 Activity
    COUNT(DISTINCT CASE WHEN ma.activity_month = '2010-12' THEN cg.customer_id END) AS active_dec_2010,
    ROUND(COUNT(DISTINCT CASE WHEN ma.activity_month = '2010-12' THEN cg.customer_id END) * 100.0 / COUNT(DISTINCT cg.customer_id), 2) AS pct_active_dec_2010,
    -- Jan 2011 Activity
    COUNT(DISTINCT CASE WHEN ma.activity_month = '2011-01' THEN cg.customer_id END) AS active_jan_2011,
    ROUND(COUNT(DISTINCT CASE WHEN ma.activity_month = '2011-01' THEN cg.customer_id END) * 100.0 / COUNT(DISTINCT cg.customer_id), 2) AS pct_active_jan_2011
FROM cohort_groups cg
LEFT JOIN monthly_activity ma ON cg.customer_id = ma.customer_id
WHERE cg.comp_group IN ('Nov 2010 Cohort', 'Dec 2010 Cohort', 'Pooled Jun-Oct 2010 Cohorts')
GROUP BY cg.comp_group
ORDER BY 
    CASE 
        WHEN cg.comp_group = 'Nov 2010 Cohort' THEN 1
        WHEN cg.comp_group = 'Dec 2010 Cohort' THEN 2
        ELSE 3
    END;
