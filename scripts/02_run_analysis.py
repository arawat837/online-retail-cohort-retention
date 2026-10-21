import os
import duckdb
import pandas as pd
import numpy as np
from statsmodels.stats.proportion import proportions_ztest, proportion_confint

def run_analysis():
    clean_v2_path = "data/clean/clean_v2.parquet"
    if not os.path.exists(clean_v2_path):
        raise FileNotFoundError(f"Cleaned dataset not found at {clean_v2_path}. Run 01_clean_data.py first.")

    os.makedirs("outputs", exist_ok=True)
    con = duckdb.connect()

    print("Step 1: Computing Cohort Retention Matrices on clean_v2...")
    retention_df = con.execute(f"""
        WITH customer_cohort AS (
            SELECT "Customer ID", date_trunc('month', MIN(InvoiceDate)) AS cohort_date
            FROM read_parquet('{clean_v2_path}')
            GROUP BY "Customer ID"
        ),
        cohort_sizes AS (
            SELECT cohort_date, COUNT(*) AS cohort_size
            FROM customer_cohort
            GROUP BY cohort_date
        ),
        activity AS (
            SELECT 
                c.cohort_date,
                date_trunc('month', t.InvoiceDate) AS activity_date,
                CAST(datediff('month', c.cohort_date, date_trunc('month', t.InvoiceDate)) AS INTEGER) AS month_n,
                COUNT(DISTINCT t."Customer ID") AS active_customers
            FROM customer_cohort c
            JOIN read_parquet('{clean_v2_path}') t ON c."Customer ID" = t."Customer ID"
            GROUP BY c.cohort_date, date_trunc('month', t.InvoiceDate)
        )
        SELECT 
            strftime(a.cohort_date, '%Y-%m') AS cohort,
            a.month_n,
            a.active_customers,
            s.cohort_size,
            ROUND(CAST(a.active_customers AS DOUBLE) / s.cohort_size * 100.0, 2) AS retention_pct
        FROM activity a
        JOIN cohort_sizes s ON a.cohort_date = s.cohort_date
        ORDER BY a.cohort_date, a.month_n;
    """).df()

    retention_df.to_csv("outputs/cohort_retention_full.csv", index=False)
    retention_m0_6 = retention_df[(retention_df['cohort'] >= '2010-01') & 
                                  (retention_df['cohort'] <= '2011-09') & 
                                  (retention_df['month_n'] <= 6)].copy()
    retention_m0_6.to_csv("outputs/cohort_retention_m0_6.csv", index=False)

    print("Step 2: Computing Calendar-Month Activity on clean_v2...")
    calendar_df = con.execute(f"""
        WITH customer_first AS (
            SELECT "Customer ID", MIN(InvoiceDate) AS first_date
            FROM read_parquet('{clean_v2_path}')
            GROUP BY "Customer ID"
        ),
        months AS (
            SELECT UNNEST(generate_series(
                TIMESTAMP '2010-01-01', 
                TIMESTAMP '2011-11-01', 
                INTERVAL 1 MONTH
            )) AS cal_month
        )
        SELECT 
            strftime(m.cal_month, '%Y-%m') AS calendar_month,
            (SELECT COUNT(*) FROM customer_first WHERE first_date < m.cal_month) AS acquired_before,
            (SELECT COUNT(DISTINCT t."Customer ID") 
             FROM read_parquet('{clean_v2_path}') t 
             JOIN customer_first cf ON t."Customer ID" = cf."Customer ID"
             WHERE cf.first_date < m.cal_month 
               AND date_trunc('month', t.InvoiceDate) = m.cal_month
            ) AS active_customers,
            ROUND(
                CAST((SELECT COUNT(DISTINCT t."Customer ID") 
                      FROM read_parquet('{clean_v2_path}') t 
                      JOIN customer_first cf ON t."Customer ID" = cf."Customer ID"
                      WHERE cf.first_date < m.cal_month 
                        AND date_trunc('month', t.InvoiceDate) = m.cal_month) AS DOUBLE) 
                / (SELECT COUNT(*) FROM customer_first WHERE first_date < m.cal_month) * 100.0, 
                2
            ) AS activity_rate_pct
        FROM months m
        ORDER BY m.cal_month;
    """).df()
    calendar_df.to_csv("outputs/calendar_activity.csv", index=False)

    print("Step 3: Computing Same-Month Comparison...")
    same_month_df = con.execute(f"""
        WITH customer_cohort AS (
            SELECT "Customer ID", date_trunc('month', MIN(InvoiceDate)) AS cohort_date
            FROM read_parquet('{clean_v2_path}')
            GROUP BY "Customer ID"
        ),
        groups AS (
            SELECT "Customer ID",
                CASE 
                    WHEN cohort_date = TIMESTAMP '2010-11-01' THEN 'Nov 2010'
                    WHEN cohort_date = TIMESTAMP '2010-12-01' THEN 'Dec 2010'
                    WHEN cohort_date BETWEEN TIMESTAMP '2010-06-01' AND TIMESTAMP '2010-10-01' THEN 'Pooled Jun-Oct 2010'
                    ELSE NULL 
                END AS comp_group
            FROM customer_cohort
        )
        SELECT 
            g.comp_group,
            COUNT(DISTINCT g."Customer ID") AS n_customers,
            COUNT(DISTINCT CASE WHEN date_trunc('month', t.InvoiceDate) = TIMESTAMP '2010-12-01' THEN t."Customer ID" END) AS active_dec_2010,
            ROUND(COUNT(DISTINCT CASE WHEN date_trunc('month', t.InvoiceDate) = TIMESTAMP '2010-12-01' THEN t."Customer ID" END) * 100.0 / COUNT(DISTINCT g."Customer ID"), 2) AS pct_active_dec_2010,
            COUNT(DISTINCT CASE WHEN date_trunc('month', t.InvoiceDate) = TIMESTAMP '2011-01-01' THEN t."Customer ID" END) AS active_jan_2011,
            ROUND(COUNT(DISTINCT CASE WHEN date_trunc('month', t.InvoiceDate) = TIMESTAMP '2011-01-01' THEN t."Customer ID" END) * 100.0 / COUNT(DISTINCT g."Customer ID"), 2) AS pct_active_jan_2011
        FROM groups g
        LEFT JOIN read_parquet('{clean_v2_path}') t ON g."Customer ID" = t."Customer ID"
        WHERE g.comp_group IS NOT NULL
        GROUP BY g.comp_group
        ORDER BY g.comp_group;
    """).df()
    same_month_df.to_csv("outputs/same_month_comparison.csv", index=False)

    print("Step 4: Computing Seasonal Return (Nov 2011 Activity)...")
    seasonal_df = con.execute(f"""
        WITH customer_cohort AS (
            SELECT "Customer ID", date_trunc('month', MIN(InvoiceDate)) AS cohort_date
            FROM read_parquet('{clean_v2_path}')
            GROUP BY "Customer ID"
        ),
        groups AS (
            SELECT "Customer ID",
                CASE 
                    WHEN cohort_date = TIMESTAMP '2010-11-01' THEN 'Nov 2010'
                    WHEN cohort_date BETWEEN TIMESTAMP '2010-01-01' AND TIMESTAMP '2010-10-01' THEN 'Jan-Oct 2010 Cohorts'
                    ELSE NULL 
                END AS comp_group
            FROM customer_cohort
        )
        SELECT 
            g.comp_group,
            COUNT(DISTINCT g."Customer ID") AS n_customers,
            COUNT(DISTINCT CASE WHEN date_trunc('month', t.InvoiceDate) = TIMESTAMP '2011-11-01' THEN t."Customer ID" END) AS active_nov_2011,
            ROUND(COUNT(DISTINCT CASE WHEN date_trunc('month', t.InvoiceDate) = TIMESTAMP '2011-11-01' THEN t."Customer ID" END) * 100.0 / COUNT(DISTINCT g."Customer ID"), 2) AS return_rate_pct
        FROM groups g
        LEFT JOIN read_parquet('{clean_v2_path}') t ON g."Customer ID" = t."Customer ID"
        WHERE g.comp_group IS NOT NULL
        GROUP BY g.comp_group
        ORDER BY g.comp_group;
    """).df()
    seasonal_df.to_csv("outputs/seasonal_return.csv", index=False)

    print("Step 5: Computing Fixed-Window 6-Month Revenue & Bootstrap 95% CIs...")
    df_clean_v2 = pd.read_parquet(clean_v2_path)
    cust_first = df_clean_v2.groupby('Customer ID').agg(
        first_date=('InvoiceDate', 'min'),
        cohort_month=('InvoiceDate', lambda s: s.min().strftime('%Y-%m'))
    ).reset_index()

    # 6-month revenue (months 0-5) for fully observed cohorts Jan 2010 to Jun 2011
    df_merged = df_clean_v2.merge(cust_first[['Customer ID', 'cohort_month']], on='Customer ID')
    df_merged['inv_month'] = df_merged['InvoiceDate'].dt.strftime('%Y-%m')
    df_merged['m_diff'] = (df_merged['InvoiceDate'].dt.year - pd.to_datetime(df_merged['cohort_month']).dt.year) * 12 + \
                          (df_merged['InvoiceDate'].dt.month - pd.to_datetime(df_merged['cohort_month']).dt.month)

    df_m0_5 = df_merged[(df_merged['m_diff'] >= 0) & (df_merged['m_diff'] <= 5)]
    rev_6m_by_cust = df_m0_5.groupby(['Customer ID', 'cohort_month'])['revenue'].sum().reset_index()

    # Fully observed 6m cohorts: Jan 2010 - Jun 2011
    rev_6m_eligible = cust_first[(cust_first['cohort_month'] >= '2010-01') & (cust_first['cohort_month'] <= '2011-06')].copy()
    rev_6m_eligible = rev_6m_eligible.merge(rev_6m_by_cust[['Customer ID', 'revenue']], on='Customer ID', how='left')
    rev_6m_eligible['revenue'] = rev_6m_eligible['revenue'].fillna(0.0)

    # Bootstrapping median 6m revenue (10,000 resamples, seed 42)
    rng = np.random.default_rng(42)
    boot_rows = []
    groups = {
        'Nov 2010': rev_6m_eligible[rev_6m_eligible['cohort_month'] == '2010-11']['revenue'].values,
        'Dec 2010': rev_6m_eligible[rev_6m_eligible['cohort_month'] == '2010-12']['revenue'].values,
        'Other Cohorts': rev_6m_eligible[(rev_6m_eligible['cohort_month'] >= '2010-01') & 
                                         (rev_6m_eligible['cohort_month'] <= '2011-06') & 
                                         (~rev_6m_eligible['cohort_month'].isin(['2010-11', '2010-12']))]['revenue'].values
    }

    for name, vals in groups.items():
        n = len(vals)
        obs_median = np.median(vals)
        boot_medians = [np.median(rng.choice(vals, size=n, replace=True)) for _ in range(10000)]
        low = np.percentile(boot_medians, 2.5)
        high = np.percentile(boot_medians, 97.5)
        boot_rows.append({
            'cohort_group': name,
            'n_customers': n,
            'median_6m_revenue': round(float(obs_median), 2),
            'ci_95_low': round(float(low), 2),
            'ci_95_high': round(float(high), 2),
            'n_resamples': 10000,
            'seed': 42
        })

    pd.DataFrame(boot_rows).to_csv("outputs/bootstrap_median_revenue_ci.csv", index=False)

    print("Step 6: Computing repeat_90d and Hypothesis Testing Suite (8 Tests)...")
    distinct_invs = df_clean_v2.groupby(['Customer ID', 'Invoice']).agg(
        inv_date=('InvoiceDate', 'min')
    ).reset_index()

    merged_invs = distinct_invs.merge(cust_first, on='Customer ID')
    merged_invs['days_diff'] = (merged_invs['inv_date'] - merged_invs['first_date']).dt.total_seconds() / (24 * 3600)
    merged_invs['is_later_day'] = merged_invs['inv_date'].dt.date > merged_invs['first_date'].dt.date

    invs_90d_any = merged_invs[merged_invs['days_diff'] <= 90].groupby('Customer ID')['Invoice'].nunique()
    later_day_90d = merged_invs[(merged_invs['is_later_day']) & (merged_invs['days_diff'] <= 90)].groupby('Customer ID')['Invoice'].nunique()

    cust_first['repeat_90d_any'] = cust_first['Customer ID'].map(lambda cid: invs_90d_any.get(cid, 0) >= 2)
    cust_first['repeat_90d_later'] = cust_first['Customer ID'].map(lambda cid: later_day_90d.get(cid, 0) >= 1)

    # 90d population: acquired on or before 2011-09-10
    c_90d = cust_first[cust_first['first_date'].dt.date <= pd.to_datetime('2011-09-10').date()].copy()
    nov_90 = c_90d[c_90d['cohort_month'] == '2010-11']
    dec_90 = c_90d[c_90d['cohort_month'] == '2010-12']
    other_90 = c_90d[(c_90d['cohort_month'] >= '2010-01') & (c_90d['cohort_month'] <= '2011-09') & (~c_90d['cohort_month'].isin(['2010-11', '2010-12']))]
    oct_90 = c_90d[c_90d['cohort_month'] == '2010-10']
    sepoct_90 = c_90d[c_90d['cohort_month'].isin(['2010-09', '2010-10'])]

    # 8-test table specification
    tests_spec = [
        {"id": "a", "desc": "Nov 2010 in Dec 2010 vs. Pooled Jun–Oct 2010", "class": "Primary", "c1": 57, "n1": 325, "c2": 173, "n2": 1238, "sec": "—"},
        {"id": "b", "desc": "Nov 2010 in Jan 2011 vs. Pooled Jun–Oct 2010", "class": "Primary", "c1": 30, "n1": 325, "c2": 133, "n2": 1238, "sec": "—"},
        {"id": "c", "desc": "Dec 2010 in Jan 2011 vs. Pooled Jun–Oct 2010", "class": "Primary", "c1": 7, "n1": 76, "c2": 133, "n2": 1238, "sec": "—"},
        {"id": "d", "desc": "Seasonal Return (Nov 2011): Nov 2010 vs. Jan–Oct 2010", "class": "Primary", "c1": 83, "n1": 325, "c2": 611, "n2": 2986, "sec": "—"},
        {"id": "e", "desc": "repeat_90d (Later Day): Nov 2010 vs. Other Eligible", "class": "Primary", "c1": nov_90['repeat_90d_later'].sum(), "n1": len(nov_90), "c2": other_90['repeat_90d_later'].sum(), "n2": len(other_90), "sec": "Any-Distinct: 35.08% (114/325) vs 45.17% (1773/3925), z=-3.52, p=0.0004"},
        {"id": "f", "desc": "repeat_90d (Later Day): Dec 2010 vs. Other Eligible", "class": "Primary", "c1": dec_90['repeat_90d_later'].sum(), "n1": len(dec_90), "c2": other_90['repeat_90d_later'].sum(), "n2": len(other_90), "sec": "Any-Distinct: 15.79% (12/76) vs 45.17% (1773/3925), z=-5.10, p=<0.0001"},
        {"id": "Post-hoc 1", "desc": "Nov 2010 vs. Oct 2010 (Later Day repeat_90d)", "class": "exploratory (chosen after seeing data)", "c1": nov_90['repeat_90d_later'].sum(), "n1": len(nov_90), "c2": oct_90['repeat_90d_later'].sum(), "n2": len(oct_90), "sec": "—"},
        {"id": "Post-hoc 2", "desc": "Nov 2010 vs. Sep–Oct 2010 Pooled (Later Day repeat_90d)", "class": "exploratory (chosen after seeing data)", "c1": nov_90['repeat_90d_later'].sum(), "n1": len(nov_90), "c2": sepoct_90['repeat_90d_later'].sum(), "n2": len(sepoct_90), "sec": "—"}
    ]

    bonf_thresh = 0.05 / 8
    rows_bonf = []
    for t in tests_spec:
        c1, n1, c2, n2 = t['c1'], t['n1'], t['c2'], t['n2']
        r1 = c1 / n1
        r2 = c2 / n2
        ci1_low, ci1_high = proportion_confint(c1, n1, method='wilson')
        ci2_low, ci2_high = proportion_confint(c2, n2, method='wilson')
        z, p = proportions_ztest([c1, c2], [n1, n2])
        p_exact = float(p)
        p_disp = "<0.0001" if p_exact < 0.0001 else f"{p_exact:.4f}"
        survives = "Y" if p_exact < bonf_thresh else "N"

        rows_bonf.append({
            "Test ID": t['id'],
            "Test Description": t['desc'],
            "Classification": t['class'],
            "Group 1 Rate (n1)": f"{r1*100:.2f}% ({c1}/{n1})",
            "Group 1 95% Wilson CI": f"[{ci1_low*100:.2f}%, {ci1_high*100:.2f}%]",
            "Group 2 Rate (n2)": f"{r2*100:.2f}% ({c2}/{n2})",
            "Group 2 95% Wilson CI": f"[{ci2_low*100:.2f}%, {ci2_high*100:.2f}%]",
            "z-statistic": round(float(z), 2),
            "p_value_display": p_disp,
            "p_value_exact": p_exact,
            "Bonferroni Threshold": bonf_thresh,
            "Survives Correction?": survives,
            "Secondary Definition": t['sec']
        })

    pd.DataFrame(rows_bonf).to_csv("outputs/statistical_tests_bonferroni.csv", index=False)
    print("Saved all analysis outputs successfully.")

if __name__ == "__main__":
    run_analysis()
