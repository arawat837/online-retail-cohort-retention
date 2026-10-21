-- ==============================================================================
-- Seasonal Return Rate: Following Holiday Peak (Nov 2011)
-- File: sql/seasonal_return.sql
-- Description: Measures whether customers acquired during the 2010 holiday peak
--   (Nov 2010) return during the following holiday shopping peak (Nov 2011),
--   compared against customers acquired in non-holiday months (Jan-Oct 2010).
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
        CASE 
            WHEN cohort_str = '2010-11' THEN 'Nov 2010 Cohort'
            WHEN cohort_str >= '2010-01' AND cohort_str <= '2010-10' THEN 'Jan-Oct 2010 Cohorts'
            ELSE 'Other'
        END AS comp_group
    FROM customer_cohort
),
nov_2011_activity AS (
    SELECT DISTINCT "Customer ID" AS customer_id
    FROM read_parquet('data/clean/clean.parquet')
    WHERE strftime(date_trunc('month', InvoiceDate), '%Y-%m') = '2011-11'
)
SELECT 
    cg.comp_group,
    COUNT(DISTINCT cg.customer_id) AS n_customers,
    COUNT(DISTINCT na.customer_id) AS active_nov_2011,
    ROUND(COUNT(DISTINCT na.customer_id) * 100.0 / COUNT(DISTINCT cg.customer_id), 2) AS return_rate_pct
FROM cohort_groups cg
LEFT JOIN nov_2011_activity na ON cg.customer_id = na.customer_id
WHERE cg.comp_group IN ('Nov 2010 Cohort', 'Jan-Oct 2010 Cohorts')
GROUP BY cg.comp_group
ORDER BY 
    CASE WHEN cg.comp_group = 'Nov 2010 Cohort' THEN 1 ELSE 2 END;
