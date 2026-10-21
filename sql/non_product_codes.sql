-- ==============================================================================
-- Non-Product StockCode Audit
-- File: sql/non_product_codes.sql
-- Description: Audits rows and revenue for specified operational/non-merchandise 
--   StockCodes and identifies non-standard product codes for portfolio review.
--   Note: Reported per instruction, NOT removed.
-- ==============================================================================

WITH total_dataset AS (
    SELECT 
        COUNT(*) AS total_rows,
        SUM(revenue) AS total_revenue
    FROM read_parquet('data/clean/clean.parquet')
),
specified_codes AS (
    SELECT 
        StockCode,
        COUNT(*) AS row_count,
        COUNT(DISTINCT Invoice) AS distinct_invoices,
        ROUND(SUM(revenue), 2) AS total_revenue,
        ROUND(SUM(revenue) * 100.0 / (SELECT total_revenue FROM total_dataset), 4) AS rev_share_pct
    FROM read_parquet('data/clean/clean.parquet')
    WHERE StockCode IN ('POST', 'DOT', 'M', 'D', 'CRUK', 'BANK CHARGES', 'AMAZONFEE', 'ADJUST', 'S', 'B', 'TEST001', 'TEST002')
    GROUP BY StockCode
),
specified_total AS (
    SELECT 
        'TOTAL SPECIFIED' AS StockCode,
        COUNT(*) AS row_count,
        COUNT(DISTINCT Invoice) AS distinct_invoices,
        ROUND(SUM(revenue), 2) AS total_revenue,
        ROUND(SUM(revenue) * 100.0 / (SELECT total_revenue FROM total_dataset), 4) AS rev_share_pct
    FROM read_parquet('data/clean/clean.parquet')
    WHERE StockCode IN ('POST', 'DOT', 'M', 'D', 'CRUK', 'BANK CHARGES', 'AMAZONFEE', 'ADJUST', 'S', 'B', 'TEST001', 'TEST002')
),
combined AS (
    SELECT * FROM specified_codes
    UNION ALL
    SELECT * FROM specified_total
)
SELECT 
    StockCode,
    row_count,
    distinct_invoices,
    total_revenue,
    rev_share_pct
FROM combined
ORDER BY 
    CASE WHEN StockCode = 'TOTAL SPECIFIED' THEN 2 ELSE 1 END,
    total_revenue DESC;
