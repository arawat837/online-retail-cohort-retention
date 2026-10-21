# Customer Cohort Retention Analysis: Holiday vs. Non-Holiday Acquisition Cohorts

## Business Question
Do holiday-acquired customers (November–December 2010) return at lower rates than customers acquired in other months when measured in the same calendar months, and do they return during the subsequent holiday shopping peak?

---

## Dataset
* **Source:** [UCI Machine Learning Repository: Online Retail II Dataset](https://archive.ics.uci.edu/dataset/502/online+retail+ii) (`data/raw/online_retail_II.xlsx`).
* **License:** [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode).
* **Sheets Combined:** `Year 2009-2010` (525,461 rows) and `Year 2010-2011` (541,910 rows).
* **Total Raw Transactions:** 1,067,371 rows.
* **Temporal Coverage:** `2009-12-01 07:45:00` to `2011-12-09 12:50:00`.
* **Distinct Raw Customers:** 5,942 non-null customer IDs.

---

## Data Cleaning Story: The Cross-Sheet Overlap

### Discovery
During data quality auditing across invoice months (`outputs/monthly_duplicate_shares.csv`), an extreme anomaly emerged:
* Across every month except Dec 2010 in the two-year dataset, exact duplicate row shares hovered consistently between **0.80% and 2.33%** (e.g., Nov 2010: 1,407 / 60,312 = 2.33%, Jan 2011: 241 / 21,229 = 1.14%, Feb 2011: 221 / 19,927 = 1.11%, Aug 2011: 217 / 27,007 = 0.80%).
* In **December 2010**, however, the duplicate share spiked drastically to **36.87%** (14,991 duplicated rows out of 40,661 total rows in that month).
* Investigating duplicated transactions revealed that identical rows appeared across invoices between **December 1, 2010 and December 9, 2010**. For example, invoice `537833` (Customer ID 13270 on `2010-12-08 14:53:00`) appeared twice in `clean.parquet` with an identical row (StockCode `51008`, 200 units at £2.95 = £590.00), which was deduplicated to a single row in `clean_v2.parquet`.

### Root Cause
Inspecting the date ranges of each raw Excel sheet revealed the underlying source:
* Sheet 1 (`Year 2009-2010`) ends at `2010-12-09 20:01:00`.
* Sheet 2 (`Year 2010-2011`) begins at `2010-12-01 08:26:00`.
* A 9-day temporal overlap existed where both sheets recorded the identical set of transactions. Out of 397,885 clean rows in Sheet 2, exactly **14,504 rows** (occurring between Dec 1 and Dec 9, 2010) were exact identical duplicates of rows already present in Sheet 1.
* In contrast, the remaining 11,620 duplicate rows in the dataset were organic within-sheet duplicate entries distributed across other months.

### What It Affected
1. **Revenue KPIs Heavily Distorted in Dec 2010:** In the initial combined dataset (`clean.parquet`), the duplicated line items artificially doubled transaction revenue for orders placed in early December 2010. For the December 2010 cohort, the uncorrected 6-month mean revenue was £769.52 (artificially inflated by 28.31% over the true £599.74), median revenue was £447.66 (artificially inflated by 46.85% over the true £304.84), and Average Order Value (AOV) was £487.06 (artificially inflated by 20.46% over the true £404.35).
2. **Distinct Customer & Retention Metrics Unaffected:** Because customer identification, cohort assignment, calendar-month active counts, and repeat purchase determinations rely on distinct customer IDs, distinct invoice dates, or unique invoice numbers, they were completely unaffected by row-level duplicates: cohort size ($n=76$), Month-1 retention, calendar activity, and hypothesis test counts were **identical** between `clean.parquet` and `clean_v2.parquet`.

### Resolution (`clean_v2.parquet`)
In `clean_v2.parquet`, the 14,504 overlapping rows were dropped strictly from Sheet 2 (`2010-11`), retaining the original Sheet 1 entries. The 11,620 organic within-sheet duplicates were retained. Sensitivity testing comparing `clean_v2` against `clean_v2_dedup` (where all duplicates are removed) shows exact impacts per group:
* **Nov 2010 Cohort:** Mean 6-month revenue shifts from £686.99 to £681.74 (-0.76%), Median 6-month revenue shifts from £365.82 to £359.69 (-1.68%), and AOV shifts from £344.92 to £342.49 (-0.70%).
* **Dec 2010 Cohort:** Mean 6-month revenue shifts from £599.74 to £595.78 (-0.66%), Median 6-month revenue shifts from £304.84 to £302.08 (-0.91%), and AOV shifts from £404.35 to £401.35 (-0.74%).
* **Other Cohorts (Jan 2010 – Jun 2011):** Mean 6-month revenue shifts from £979.86 to £975.55 (-0.44%), Median 6-month revenue shifts from £523.05 to £517.85 (-0.99%), and AOV shifts from £416.24 to £414.68 (-0.37%).

The final production cleaned dataset contains **791,045 clean rows**.

---

## Data Cleaning Rules Summary
Applied sequentially to produce `data/clean/clean_v2.parquet` (audit logged in `data_quality_log.md`):
1. **Drop Missing Customer IDs:** Dropped 243,007 rows (22.77% of raw rows) representing guest checkouts without longitudinal identifiers. Cast `Customer ID` to 64-bit integer (`int64`).
2. **Drop Cancellation Invoices:** Dropped 18,744 rows where `Invoice` starts with "C" (representing order cancellations and returns).
3. **Filter Non-Positive Values:** Kept strictly `Quantity > 0` and `Price > 0`, removing 71 rows with zero/negative unit prices (damages, samples, or adjustments). Zero rows had non-positive quantities after Rule 2.
4. **Derive Line Revenue:** Computed `revenue = Quantity * Price`.
5. **Cross-Sheet Overlap Resolution:** Removed the 14,504 cross-sheet duplicate rows from Sheet 2 (`2010-11`) while retaining Sheet 1 and organic within-sheet duplicates (11,620 rows).

---

## Metric & KPI Definitions
* **Acquisition Cohort:** Calendar month of a customer's first valid purchase (`min(InvoiceDate)` truncated to month).
* **Month N (`month_n`):** Calendar months elapsed between cohort acquisition month and transaction month (`datediff('month', cohort_month, invoice_month)`).
* **Retained in Month N:** Customer has at least one valid invoice in `month_n`.
* **Cohort Month-1 Retention Rate:** Active customers in Month 1 divided by cohort size in Month 0 (`active_customers_m1 / n_customers_m0 * 100`).
* **Calendar-Month Activity Rate:** Active customers in a specific calendar month divided by the cumulative count of customers acquired strictly prior to that month. Saved to `outputs/calendar_activity.csv`.
* **90-Day Repeat Purchase Rate (`repeat_90d` - Primary Later-Calendar-Day Definition):** Percentage of customers placing a second distinct invoice on a strictly later calendar day within 90 days of their initial invoice (`invoice_date.dt.date > first_date.dt.date` and `diff_seconds <= 90 * 86400`). Evaluated for customers acquired on or before `2011-09-10` to ensure an unclipped 90-day observation window. (Secondary any-distinct invoice definition also reported).
* **6-Month Revenue per Customer (`clean_v2`):** Cumulative gross spend per customer during months 0 through 5 of cohort tenure. Evaluated for cohorts Jan 2010 through Jun 2011 (fully observed 6-month tenures) on `clean_v2.parquet`. Saved to `outputs/revenue_6m_fixed_window.csv`.
* **Active in Nov 2011:** At least one valid invoice dated in Nov 2011. This includes customers who also purchased in earlier months, so it measures activity, not return after a lapse.
* **Pooled Jun-Oct 2010:** Customers whose first purchase was in Jun-Oct 2010.
* **Other Eligible Cohorts:** First purchase Jan 2010 - Sep 2011, excluding Nov and Dec 2010, first purchase on or before 2011-09-10.

---

## Empirical Results

### 1. Multiple-Comparison Hypothesis Testing Table (All 8 Tests)
Evaluated with two-proportion z-tests and 95% Wilson confidence intervals against a Bonferroni-corrected threshold ($\alpha / 8 = 0.05 / 8 = 0.00625$). Sourced directly from `outputs/statistical_tests_bonferroni.csv`:

| Test ID | Test Description | Classification | Group 1 Rate ($n_1$) | Group 1 95% Wilson CI | Group 2 Rate ($n_2$) | Group 2 95% Wilson CI | $z$-statistic | $p$-value (display) | $p$-value (exact) | Bonferroni Threshold | Survives Correction? | Secondary Definition |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **a** | Nov 2010 in Dec 2010 vs. Pooled Jun–Oct 2010 | Primary | 17.54% (57/325) | [13.79%, 22.05%] | 13.97% (173/1238) | [12.15%, 16.02%] | 1.61 | 0.1065 | 0.106467 | 0.00625 | **N** | — |
| **b** | Nov 2010 in Jan 2011 vs. Pooled Jun–Oct 2010 | Primary | 9.23% (30/325) | [6.54%, 12.87%] | 10.74% (133/1238) | [9.14%, 12.59%] | -0.79 | 0.4272 | 0.427238 | 0.00625 | **N** | — |
| **c** | Dec 2010 in Jan 2011 vs. Pooled Jun–Oct 2010 | Primary | 9.21% (7/76) | [4.53%, 17.81%] | 10.74% (133/1238) | [9.14%, 12.59%] | -0.42 | 0.6742 | 0.674239 | 0.00625 | **N** | — |
| **d** | Seasonal Return (Nov 2011): Nov 2010 vs. Jan–Oct 2010 | Primary | 25.54% (83/325) | [21.10%, 30.55%] | 20.46% (611/2986) | [19.05%, 21.95%] | 2.14 | 0.0327 | 0.032747 | 0.00625 | **N** | — |
| **e** | `repeat_90d` (Later Day): Nov 2010 vs. Other Eligible | Primary | 30.15% (98/325) | [25.42%, 35.35%] | 42.42% (1665/3925) | [40.88%, 43.97%] | -4.31 | <0.0001 | 0.0000164 | 0.00625 | **Y** | Any-Distinct: 35.08% (114/325) vs 45.17% (1773/3925), $z = -3.52, p = 0.0004$ |
| **f** | `repeat_90d` (Later Day): Dec 2010 vs. Other Eligible | Primary | 15.79% (12/76) | [9.27%, 25.60%] | 42.42% (1665/3925) | [40.88%, 43.97%] | -4.66 | <0.0001 | 0.0000031 | 0.00625 | **Y** | Any-Distinct: 15.79% (12/76) vs 45.17% (1773/3925), $z = -5.10, p < 0.0001$ |
| **Post-hoc 1** | Nov 2010 vs. Oct 2010 (Later Day repeat_90d) | exploratory (chosen after seeing data) | 30.15% (98/325) | [25.42%, 35.35%] | 38.20% (144/377) | [33.43%, 43.20%] | -2.24 | 0.0254 | 0.025382 | 0.00625 | **N** | — |
| **Post-hoc 2** | Nov 2010 vs. Sep–Oct 2010 Pooled (Later Day repeat_90d) | exploratory (chosen after seeing data) | 30.15% (98/325) | [25.42%, 35.35%] | 40.16% (249/620) | [36.37%, 44.07%] | -3.03 | 0.0024 | 0.002433 | 0.00625 | **Y** | — |

---

### 2. 6-Month Cumulative Revenue per Customer (`clean_v2`)
Medians reported first, means reported second. Sourced directly from `outputs/revenue_kpis_comparison_v2.csv` and `outputs/bootstrap_median_revenue_ci.csv` (visualized in `outputs/median_revenue_6m_bootstrap.png`):

| Cohort Group | Customers ($n$) | Dataset Version | Median 6-Month Revenue (£) | 95% Bootstrap CI for Median (10,000 resamples, seed 42) | Mean 6-Month Revenue (£) | Average Order Value (AOV £) | Status / Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Nov 2010** | 325 | **clean_v2** | **£365.82** | [£319.75, £418.05] | **£686.99** | **£344.92** | Primary |
| Nov 2010 | 325 | clean | £375.50 | — | £724.26 | £356.77 | Contains cross-sheet overlap |
| Nov 2010 | 325 | dedup | £359.69 | — | £681.74 | £342.49 | All duplicates removed |
| Nov 2010 | 325 | clean_v2_dedup | £359.69 | — | £681.74 | £342.49 | Sensitivity check |
| **Dec 2010** | 76 | **clean_v2** | **£304.84** | [£261.76, £350.61] | **£599.74** | **£404.35** | Primary: resolves cross-sheet duplication |
| Dec 2010 | 76 | clean | £447.66 | — | £769.52 | £487.06 | Inflated by cross-sheet overlap rows (Dec 1-9, 2010) |
| Dec 2010 | 76 | dedup | £302.08 | — | £595.78 | £401.35 | All duplicates removed |
| Dec 2010 | 76 | clean_v2_dedup | £302.08 | — | £595.78 | £401.35 | Sensitivity check |
| **Other Cohorts (Jan 2010 – Jun 2011)** | 3,685 | **clean_v2** | **£523.05** | [£495.98, £543.72] | **£979.86** | **£416.24** | Primary |
| Other Cohorts (Jan 2010 – Jun 2011) | 3,685 | clean | £529.85 | — | £989.23 | £421.67 | Contains cross-sheet overlap |
| Other Cohorts (Jan 2010 – Jun 2011) | 3,685 | dedup | £517.85 | — | £975.55 | £414.68 | All duplicates removed |
| Other Cohorts (Jan 2010 – Jun 2011) | 3,685 | clean_v2_dedup | £517.85 | — | £975.55 | £414.68 | Sensitivity check |

---

### 3. Timing-Adjacent Benchmarks for `repeat_90d`
Sourced from `outputs/statistical_tests_bonferroni.csv` and visualized in `outputs/repeat_90d_benchmarks.png`:
* **Nov 2010 Cohort ($n=325$):** Primary later day = 30.15% (98 / 325) [95% Wilson CI: 25.42%, 35.35%]; Secondary any distinct = 35.08% (114 / 325) [95% Wilson CI: 30.09%, 40.41%].
* **Dec 2010 Cohort ($n=76$):** Primary later day = 15.79% (12 / 76) [95% Wilson CI: 9.27%, 25.60%]; Secondary any distinct = 15.79% (12 / 76) [95% Wilson CI: 9.27%, 25.60%].
* **Sep 2010 Cohort ($n=243$):** Primary later day = 43.21% (105 / 243) [95% Wilson CI: 37.17%, 49.46%]; Secondary any distinct = 46.09% (112 / 243) [95% Wilson CI: 39.95%, 52.36%].
* **Oct 2010 Cohort ($n=377$):** Primary later day = 38.20% (144 / 377) [95% Wilson CI: 33.43%, 43.20%]; Secondary any distinct = 40.58% (153 / 377) [95% Wilson CI: 35.75%, 45.60%].
* **Sep–Oct 2010 Pooled ($n=620$):** Primary later day = 40.16% (249 / 620) [95% Wilson CI: 36.37%, 44.07%]; Secondary any distinct = 42.74% (265 / 620) [95% Wilson CI: 38.90%, 46.68%].
* **Other Eligible Cohorts ($n=3,925$):** Primary later day = 42.42% (1,665 / 3,925) [95% Wilson CI: 40.88%, 43.97%]; Secondary any distinct = 45.17% (1,773 / 3,925) [95% Wilson CI: 43.62%, 46.73%].

---

### 4. Dec 2010 Cohort Breakdown by First-Purchase Week
* **Week 48 (`2010-12-01` to `2010-12-05`):** $n = 30$ | `repeat_90d` later day = 3 / 30 (10.00%) | any distinct = 3 / 30 (10.00%)
* **Week 49 (`2010-12-06` to `2010-12-12`):** $n = 23$ | `repeat_90d` later day = 4 / 23 (17.39%) | any distinct = 4 / 23 (17.39%)
* **Week 50 (`2010-12-13` to `2010-12-17`):** $n = 16$ | `repeat_90d` later day = 4 / 16 (25.00%) | any distinct = 4 / 16 (25.00%)
* **Week 51 (`2010-12-20` to `2010-12-23`):** $n = 7$ | `repeat_90d` later day = 1 / 7 (14.29%) | any distinct = 1 / 7 (14.29%)

---

## Limitations
1. **Left-Censoring (Dec 2009):** The dataset commences on December 1, 2009. The December 2009 cohort ($n=955$) combines pre-existing loyal customers with newly acquired customers, inflating early retention (Month 1: 35.29%). It is excluded from all baseline comparisons.
2. **Small Sample Size for Dec 2010 ($n=76$):** The Dec 2010 acquisition window ran 2010-12-01 to 2010-12-23 (the retailer closed 2010-12-24). This data cannot explain why the cohort is small.
3. **Data Truncation (2011-12-09):** The dataset terminates abruptly on December 9, 2011. Cohorts from October, November, and December 2011 have fewer than 3 months of observable follow-up and are excluded from retention conclusions.
4. **Operational Closure & Confounded Timing:** The retailer recorded zero transactions across 11 consecutive calendar days between December 24, 2010 and January 3, 2011 due to operational shutdown. The cohort whose 90-day window is closest to Nov 2010's is Oct 2010. Against Oct 2010 the repeat_90d gap is 8.1 points (p = 0.0254, does not survive the 8-test correction); against all other eligible cohorts it is 12.3 points. The shutdown and holiday timing cannot be separated.
5. **Tenure Asymmetry in Same-Month Testing:** In tests a–c, the Nov 2010 cohort is 1 month old in Dec 2010 (and 2 months old in Jan 2011), whereas the comparison pooled Jun–Oct 2010 cohorts are 2 to 6 months old in Dec 2010 (and 3 to 7 months old in Jan 2011). Comparing cohorts at unequal tenures conflates tenure-based dropoff with acquisition season.
6. **Multiple Comparisons:** Running 8 hypothesis tests simultaneously inflates the family-wise error rate. Under a Bonferroni correction threshold ($\alpha = 0.00625$), the seasonal return effect does not survive ($p = 0.0327$).
7. **Unequal Tenure in Seasonal Return Testing:** When evaluated in November 2011, the Nov 2010 cohort had 12 months of tenure, whereas benchmark Jan–Oct 2010 cohorts had 13 to 22 months of tenure.
8. **Concentrated Cross-Sheet Ingestion Duplicates:** Exactly 14,504 duplicate rows were concentrated in early December 2010 (Dec 1–9, 2010) due to workbook sheet overlap between `Year 2009-2010` and `Year 2010-2011`. This is resolved in `clean_v2.parquet`.
9. **Within-Sheet Duplicates Kept:** Exactly 11,620 within-sheet duplicate rows were kept. Removing them (`clean_v2_dedup`) shifts mean revenue by -0.76% for Nov 2010 (£686.99 to £681.74), -0.66% for Dec 2010 (£599.74 to £595.78), and -0.44% for Other cohorts (£979.86 to £975.55); median revenue by -1.68% for Nov 2010 (£365.82 to £359.69), -0.91% for Dec 2010 (£304.84 to £302.08), and -0.99% for Other cohorts (£523.05 to £517.85); and AOV by -0.70% for Nov 2010 (£344.92 to £342.49), -0.74% for Dec 2010 (£404.35 to £401.35), and -0.37% for Other cohorts (£416.24 to £414.68).
10. **Customer Type Distribution:** The UCI dataset page states: *"The company mainly sells unique all-occasion gift-ware. Many customers of the company are wholesalers."* Customer type (wholesaler vs. individual retail customer) is not a field in the data.
11. **No Causal Attribution:** Observational transaction logs without exposure controls or randomized intervention cannot isolate causal factors behind retention variance.
12. **AOV Variance:** AOV is lower for the Nov 2010 cohort; this data cannot explain why.

---

## How to Reproduce

### 1. Folder Layout
```
├── data/
│   ├── raw/
│   │   └── online_retail_II.xlsx         # Raw UCI dataset (untouched)
│   └── clean/
│       ├── clean.parquet                 # Rules 1-4 applied (with cross-sheet overlap)
│       ├── clean_dedup.parquet           # Drop-duplicates sensitivity baseline
│       └── clean_v2.parquet              # Primary cleaned dataset (overlap resolved)
├── sql/
│   ├── calendar_activity.sql             # Calendar-month activity query
│   ├── cohort_retention.sql              # Classic cohort retention matrix query
│   ├── fixed_window_kpis.sql             # 90-day repeat purchase query
│   ├── holiday_vs_nonholiday.sql         # Holiday vs. baseline comparison query
│   ├── kpi_metrics.sql                   # Revenue and order metrics query
│   ├── non_product_codes.sql             # Non-product StockCode audit query
│   ├── revenue_6m_fixed_window.sql       # 6-month gross customer revenue query
│   ├── same_month_comparison.sql         # Same-calendar-month comparison query
│   └── seasonal_return.sql               # November 2011 seasonal return query
├── scripts/
│   ├── 01_clean_data.py                  # Ingestion, cleaning rules, overlap resolution
│   ├── 02_run_analysis.py                # DuckDB execution, KPI computation, 8 tests
│   └── 03_generate_visualizations.py     # Production visualizations (PNG outputs)
├── outputs/
│   ├── bootstrap_median_revenue_ci.csv   # 10,000 bootstrap resamples for median revenue
│   ├── calendar_activity.csv             # Monthly active customer rates
│   ├── calendar_activity_trend.png       # Activity rate line chart with shutdown shading
│   ├── cohort_retention_full.csv         # Full cohort retention table
│   ├── cohort_retention_m0_6.csv         # Months 0-6 cohort retention matrix
│   ├── median_revenue_6m_bootstrap.png   # Median 6m revenue bar chart with 95% bootstrap CIs
│   ├── monthly_duplicate_shares.csv      # Monthly duplicate audit table
│   ├── post_hoc_tests.csv                # Exploratory post-hoc test results
│   ├── repeat_90d_benchmarks.png         # 90-day repeat purchase benchmark bar chart
│   ├── retention_heatmap.png             # Cohort retention heatmap (Jan 2010 - Sep 2011)
│   ├── revenue_6m_fixed_window.csv       # 6-month customer revenue summary
│   ├── revenue_kpis_comparison_v2.csv    # Revenue KPIs across clean, dedup, and clean_v2
│   ├── same_month_comparison.csv         # Same-month comparison table (Dec 2010, Jan 2011)
│   ├── same_month_comparison.png         # Same-month comparison bar chart with 95% Wilson CIs
│   ├── seasonal_return.csv               # Seasonal return table (Nov 2011)
│   ├── seasonal_return.png               # Seasonal return bar chart with 95% Wilson CIs
│   └── statistical_tests_bonferroni.csv  # Complete 8-test multiple-comparison suite
├── .gitignore                            # Ignores data/raw/ and data/clean/
├── data_quality_log.md                   # Complete data auditing and cleaning log
├── README.md                             # Project documentation and empirical findings
└── requirements.txt                      # Pinned Python package dependencies
```

### 2. Python Environment & Library Versions
The analysis was executed with **Python 3.13.1** (compatible with Python >= 3.10) using the following core libraries:
* `pandas`: 3.0.5
* `duckdb`: 1.5.6
* `openpyxl`: 3.1.5
* `pyarrow`: 26.0.0
* `statsmodels`: 0.15.0
* `matplotlib`: 3.11.1
* `seaborn`: 0.13.2
* `scipy`: 1.18.0
* `numpy`: 2.5.2

To install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Execution Run Order
Execute the three pipeline scripts sequentially from the repository root:
```bash
# Step 1: Clean raw data and generate clean_v2.parquet
python scripts/01_clean_data.py

# Step 2: Run DuckDB analytics, bootstrap CIs, and statistical tests
python scripts/02_run_analysis.py

# Step 3: Generate all publication-ready figures in outputs/
python scripts/03_generate_visualizations.py
```

---

## Recommendation
Holiday-acquired customers (Nov-Dec 2010) look weaker than other cohorts on second orders within 90 days (30% vs 42%) and on median six-month revenue (£366 vs £523), but they are not less active than other customers in the same calendar months, and the 90-day window overlaps an 11-day shutdown, so the gap may be seasonal timing rather than lower customer quality. I would recommend testing a follow-up offer timed to land after the January reopening before cutting holiday acquisition spend, because the evidence can’t separate those explanations. This analysis can’t tell us why these customers spend less, or whether they return the next holiday more often, which is only suggestive here.
