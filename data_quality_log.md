# Data Quality & Cleaning Log

## Overview
This log documents the sequential data cleaning transformations applied to the **UCI Online Retail II** dataset, tracking row counts, filtration logic, and data integrity metrics at each stage.

- **Source File:** `data/raw/online_retail_II.xlsx` (combined sheets: `Year 2009-2010` and `Year 2010-2011`)
- **Initial Total Row Count:** 1,067,371 rows
- **Output Clean File (v1):** `data/clean/clean.parquet` (805,549 rows)
- **Output Clean File (v2):** `data/clean/clean_v2.parquet` (791,045 rows)
- **Total Initial Rows Dropped:** 261,822 rows (24.5296% of raw rows)
- **Distinct Valid Customers Retained:** 5,878
- **Distinct Valid Invoices Retained:** 36,969
- **Cleaned Temporal Span:** `2009-12-01 07:45:00` to `2011-12-09 12:50:00`

---

## Applied Cleaning Rules (Sequential Audit Trail)

The cleaning rules were applied in strict sequential order as specified:

| Rule # | Cleaning Rule | Initial Rows | Rows Dropped | % Dropped (Relative) | Retained Rows | Notes / Rationale |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | **Drop rows with null Customer ID** | 1,067,371 | 243,007 | 22.7669% | 824,364 | Customer ID is mandatory for tracking longitudinal customer cohorts. Rows without customer IDs (guest checkouts) cannot be linked across visits. `Customer ID` was also cast to integer (`int64`). |
| **2** | **Drop invoices starting with "C"** | 824,364 | 18,744 | 2.2738% | 805,620 | Invoices prefixed with "C" represent cancellations and return adjustments rather than new purchase transactions. |
| **3** | **Keep only Quantity > 0 and Price > 0** | 805,620 | 71 | 0.0088% | 805,549 | Excludes non-positive quantities (0 rows at this stage) and zero/negative prices (71 rows) representing damages, samples, gifts, or administrative adjustments. |
| **4** | **Derive `revenue = Quantity * Price`** | 805,549 | 0 | 0.0000% | 805,549 | Calculated line-item gross transaction value in GBP for Monetization and Average Order Value (AOV) analyses. |

### Sequential Row Waterfall Summary
1. **Raw combined:** 1,067,371 rows
2. **After Rule 1 (Drop null `Customer ID`):** 824,364 rows (-243,007 rows)
3. **After Rule 2 (Drop "C" cancellations):** 805,620 rows (-18,744 rows)
4. **After Rule 3 (Keep `Quantity > 0` and `Price > 0`):** 805,549 rows (-71 rows)
5. **After Rule 4 (Add `revenue`):** 805,549 rows (0 rows dropped)

---

## Duplicate Rows Audit (Reported but NOT Removed in v1)

* **Exact Duplicate Rows in Raw Dataset:** **34,335 rows** (3.2168% of raw rows)
* **Exact Duplicate Rows in Cleaned Dataset (v1):** **26,124 rows** (3.2430% of cleaned rows)

---

## Cross-Sheet Overlap Audit & Creation of `clean_v2.parquet`

### Overlap Investigation
An investigation was conducted by tagging rows with their source workbook sheet (`2009-10` vs. `2010-11`) to determine the root cause of the 26,124 duplicate rows:
* **Sheet 1 (`Year 2009-2010`):** Spans `2009-12-01 07:45:00` to `2010-12-09 20:01:00` (407,664 clean rows).
* **Sheet 2 (`Year 2010-2011`):** Spans `2010-12-01 08:26:00` to `2011-12-09 12:50:00` (397,885 clean rows).
* **Confirmed Overlapping Window:** `2010-12-01 08:26:00` to `2010-12-09 20:01:00` (9 calendar days).
* **Row Counts in Overlap Window:**
  * Clean Sheet 1 rows in overlap: **14,504 rows**
  * Clean Sheet 2 rows in overlap: **14,504 rows**
  * Exact Match Count: **14,504 out of 14,504 rows** in Sheet 2 match an identical row in Sheet 1 across all 8 original columns.

### Duplicate Decomposition (of the 26,124 rows in `clean.parquet`)
* **Within Sheet 1 (`2009-10`):** 6,748 internal duplicate rows
* **Within Sheet 2 (`2010-11`):** 5,192 internal duplicate rows
* **Total Genuine Within-Sheet Duplicates:** **11,940 rows**
* **Cross-Sheet Duplicates (due to sheet overlap):** **14,184 rows**

### Creation of `data/clean/clean_v2.parquet`
* **Rule Applied:** Removed the 14,504 overlapping rows from sheet `2010-11` only (`InvoiceDate <= '2010-12-09 20:01:00'`), preserving the original `2009-10` records and preserving all 11,940 genuine within-sheet duplicates.
* **Output File:** `data/clean/clean_v2.parquet`
* **Row Count:** **791,045 rows** (805,549 - 14,504)
* **Impact Assessment:** Cohort sizes, retention tables, calendar-month activity, and distinct hypothesis test counts are **IDENTICAL** on `clean_v2.parquet`, while eliminating the artificial gross revenue inflation for the December 2010 period.

---

## Final Clean Dataset Schema (`data/clean/clean_v2.parquet`)

| Column Name | Clean Data Type | Non-Null Count | Sample Value | Description |
| :--- | :--- | :--- | :--- | :--- |
| `Invoice` | `object` / string | 791,045 | `"489434"` | Clean purchase invoice identifier |
| `StockCode` | `object` / string | 791,045 | `"85048"` | Alphanumeric product identifier |
| `Description` | `string` | 791,045 | `"15CM CHRISTMAS GLASS BALL 20 LIGHTS"` | Product description |
| `Quantity` | `int64` | 791,045 | `12` | Purchased item quantity (strictly > 0) |
| `InvoiceDate` | `datetime64[us]` | 791,045 | `2009-12-01 07:45:00` | Date and timestamp of purchase |
| `Price` | `float64` | 791,045 | `6.95` | Unit price in GBP (strictly > 0) |
| `Customer ID` | `int64` | 791,045 | `13085` | Unique customer identifier (integer) |
| `Country` | `string` | 791,045 | `"United Kingdom"` | Destination / customer country |
| `revenue` | `float64` | 791,045 | `83.40` | Line revenue (`Quantity * Price`) |
