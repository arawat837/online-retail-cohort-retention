-- ==============================================================================
-- Holiday Cohorts vs Other Cohorts Comparison
-- File: sql/holiday_vs_nonholiday.sql
-- Description: Aggregates KPIs across cohort groups based on analytical rules:
--   - Dec 2009: Excluded (left-censored historical customer base)
--   - Oct 2011 - Dec 2011: Excluded (< 3 months observable follow-up)
--   - Holiday Cohorts: Nov 2010 and Dec 2010 only
--   - Other Eligible Cohorts: Jan 2010 - Sep 2011 (non-holiday)
-- Also breaks down Non-Holiday 2010 cohorts (Jan-Oct 2010) for seasonal parity.
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
customer_summary AS (
    SELECT 
        c.customer_id,
        c.cohort_month,
        strftime(c.cohort_month, '%Y-%m') AS cohort_str,
        COUNT(DISTINCT ci.Invoice) AS total_invoices,
        MAX(CASE WHEN ci.month_n = 1 THEN 1 ELSE 0 END) AS active_m1,
        SUM(ci.invoice_revenue) AS total_rev_clean,
        SUM(CASE WHEN ci.month_n BETWEEN 0 AND 5 THEN ci.invoice_revenue ELSE 0 END) AS rev_6m_clean,
        SUM(di.invoice_revenue) AS total_rev_dedup,
        SUM(CASE WHEN di.month_n BETWEEN 0 AND 5 THEN di.invoice_revenue ELSE 0 END) AS rev_6m_dedup
    FROM customer_cohort c
    LEFT JOIN clean_invoices ci ON c.customer_id = ci.customer_id
    LEFT JOIN dedup_invoices di ON c.customer_id = di.customer_id AND ci.Invoice = di.Invoice
    GROUP BY c.customer_id, c.cohort_month
),
cohort_categorized AS (
    SELECT 
        *,
        CASE 
            WHEN cohort_str = '2009-12' THEN 'Excluded: Dec 2009 (Left-Censored)'
            WHEN cohort_str IN ('2011-10', '2011-11', '2011-12') THEN 'Excluded: <3 Months Follow-Up'
            WHEN cohort_str IN ('2010-11', '2010-12') THEN 'Holiday Cohorts (Nov-Dec 2010)'
            ELSE 'Other Eligible Cohorts (Jan 2010 - Sep 2011)'
        END AS cohort_group
    FROM customer_summary
)
SELECT 
    cohort_group,
    COUNT(DISTINCT customer_id) AS n_customers,
    -- Month-1 Retention
    COUNT(DISTINCT CASE WHEN active_m1 = 1 THEN customer_id END) AS m1_retained_customers,
    ROUND(COUNT(DISTINCT CASE WHEN active_m1 = 1 THEN customer_id END) * 100.0 / COUNT(DISTINCT customer_id), 2) AS m1_retention_pct,
    -- Repeat Purchase Rate (>= 2 distinct invoices)
    COUNT(DISTINCT CASE WHEN total_invoices >= 2 THEN customer_id END) AS repeat_customers,
    ROUND(COUNT(DISTINCT CASE WHEN total_invoices >= 2 THEN customer_id END) * 100.0 / COUNT(DISTINCT customer_id), 2) AS repeat_purchase_rate_pct,
    -- AOV
    ROUND(SUM(total_rev_clean) / SUM(total_invoices), 2) AS aov_clean,
    ROUND(SUM(total_rev_dedup) / SUM(total_invoices), 2) AS aov_dedup,
    ROUND((ROUND(SUM(total_rev_dedup) / SUM(total_invoices), 2) - ROUND(SUM(total_rev_clean) / SUM(total_invoices), 2)) * 100.0 / ROUND(SUM(total_rev_clean) / SUM(total_invoices), 2), 2) AS aov_diff_pct,
    -- Revenue per Customer in First 6 Months (months 0 to 5)
    ROUND(SUM(rev_6m_clean) / COUNT(DISTINCT customer_id), 2) AS rev_per_cust_6m_clean,
    ROUND(SUM(rev_6m_dedup) / COUNT(DISTINCT customer_id), 2) AS rev_per_cust_6m_dedup,
    ROUND((ROUND(SUM(rev_6m_dedup) / COUNT(DISTINCT customer_id), 2) - ROUND(SUM(rev_6m_clean) / COUNT(DISTINCT customer_id), 2)) * 100.0 / ROUND(SUM(rev_6m_clean) / COUNT(DISTINCT customer_id), 2), 2) AS rev_per_cust_6m_diff_pct
FROM cohort_categorized
GROUP BY cohort_group
ORDER BY 
    CASE 
        WHEN cohort_group LIKE 'Holiday%' THEN 1
        WHEN cohort_group LIKE 'Other Eligible%' THEN 2
        ELSE 3
    END;
