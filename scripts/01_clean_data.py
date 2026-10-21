import os
import pandas as pd
import numpy as np

def clean_data():
    raw_file = "data/raw/online_retail_II.xlsx"
    if not os.path.exists(raw_file):
        raise FileNotFoundError(f"Raw data file not found at {raw_file}")

    print("Step 1: Loading raw Excel sheets...")
    df1 = pd.read_excel(raw_file, sheet_name="Year 2009-2010")
    df1["source_sheet"] = "2009-10"

    df2 = pd.read_excel(raw_file, sheet_name="Year 2010-2011")
    df2["source_sheet"] = "2010-11"

    for d in [df1, df2]:
        d["Invoice"] = d["Invoice"].astype(str).str.strip()
        d["StockCode"] = d["StockCode"].astype(str).str.strip()

    df_raw = pd.concat([df1, df2], ignore_index=True)
    print(f"Total raw rows: {len(df_raw):,}")

    print("Step 2: Applying Rule 1 - Dropping missing Customer ID and casting to int64...")
    df_r1 = df_raw.dropna(subset=["Customer ID"]).copy()
    df_r1["Customer ID"] = df_r1["Customer ID"].astype(np.int64)

    print("Step 3: Applying Rule 2 - Dropping cancellation invoices starting with 'C'...")
    df_r2 = df_r1[~df_r1["Invoice"].str.startswith("C", na=False)].copy()

    print("Step 4: Applying Rule 3 - Keeping Quantity > 0 and Price > 0...")
    df_r3 = df_r2[(df_r2["Quantity"] > 0) & (df_r2["Price"] > 0)].copy()

    print("Step 5: Applying Rule 4 - Deriving line revenue...")
    df_clean = df_r3.copy()
    df_clean["revenue"] = df_clean["Quantity"] * df_clean["Price"]
    df_clean["Description"] = df_clean["Description"].astype("string")
    df_clean["Country"] = df_clean["Country"].astype("string")

    os.makedirs("data/clean", exist_ok=True)

    # Save clean.parquet (combined with overlap preserved)
    clean_v1_path = "data/clean/clean.parquet"
    df_clean.drop(columns=["source_sheet"]).to_parquet(clean_v1_path, index=False, engine="pyarrow")
    print(f"Saved {clean_v1_path} ({len(df_clean):,} rows)")

    # Save clean_dedup.parquet (all duplicates removed)
    orig_cols = ['Invoice', 'StockCode', 'Description', 'Quantity', 'InvoiceDate', 'Price', 'Customer ID', 'Country']
    df_dedup = df_clean.drop_duplicates(subset=orig_cols)
    clean_dedup_path = "data/clean/clean_dedup.parquet"
    df_dedup.drop(columns=["source_sheet"]).to_parquet(clean_dedup_path, index=False, engine="pyarrow")
    print(f"Saved {clean_dedup_path} ({len(df_dedup):,} rows)")

    # Step 6: Resolve cross-sheet overlap for clean_v2.parquet
    print("Step 6: Resolving cross-sheet overlap (2010-12-01 to 2010-12-09)...")
    overlap_cutoff = pd.to_datetime('2010-12-09 20:01:00')
    is_sheet2_overlap = (df_clean["source_sheet"] == "2010-11") & (df_clean["InvoiceDate"] <= overlap_cutoff)
    print(f"Removed {is_sheet2_overlap.sum():,} cross-sheet overlap rows from Sheet 2 ('2010-11').")

    df_clean_v2 = df_clean[~is_sheet2_overlap].copy()
    clean_v2_path = "data/clean/clean_v2.parquet"
    df_clean_v2.drop(columns=["source_sheet"]).to_parquet(clean_v2_path, index=False, engine="pyarrow")
    print(f"Saved {clean_v2_path} successfully ({len(df_clean_v2):,} rows).")

if __name__ == "__main__":
    clean_data()
