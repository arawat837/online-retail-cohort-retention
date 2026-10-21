import os
import textwrap
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def generate_visualizations():
    os.makedirs("outputs", exist_ok=True)
    plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.family': 'sans-serif'})

    # --------------------------------------------------------------------------
    # 1. repeat_90d_benchmarks.png
    # --------------------------------------------------------------------------
    print("Generating Chart 1: repeat_90d_benchmarks.png...")
    labels_90 = [
        "Nov 2010\n(n = 325)",
        "Dec 2010\n(n = 76)",
        "Oct 2010\n(n = 377)",
        "Sep–Oct 2010\n(nearest timing)\n(n = 620)",
        "Other eligible\n(n = 3,925)"
    ]
    rates_90 = [30.15, 15.79, 38.20, 40.16, 42.42]
    ci_low_90 = [25.42, 9.27, 33.43, 36.37, 40.88]
    ci_high_90 = [35.35, 25.60, 43.20, 44.07, 43.97]

    yerr_low_90 = [r - low for r, low in zip(rates_90, ci_low_90)]
    yerr_high_90 = [high - r for r, high in zip(rates_90, ci_high_90)]

    fig, ax = plt.subplots(figsize=(10, 6))
    colors_90 = ['#1f77b4', '#d62728', '#ff7f0e', '#2ca02c', '#7f7f7f']
    bars_90 = ax.bar(range(len(rates_90)), rates_90, yerr=[yerr_low_90, yerr_high_90],
                     capsize=7, color=colors_90, edgecolor='black', width=0.52,
                     error_kw={'elinewidth': 1.6, 'capthick': 1.6})

    for bar, r, low, high in zip(bars_90, rates_90, ci_low_90, ci_high_90):
        x = bar.get_x() + bar.get_width() / 2.
        ax.text(x, high + 1.2,
                f"{r:.2f}%\n[{low:.2f}%, {high:.2f}%]",
                ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_xticks(range(len(labels_90)))
    ax.set_xticklabels(labels_90, fontsize=9.5)
    ax.set_ylabel("Customers with a 2nd invoice on a later day within 90 days (%)", fontsize=10.5, labelpad=8)
    ax.set_title("90-Day Repeat Purchase Rate (Primary Later-Calendar-Day Definition)", fontsize=12, fontweight='bold', pad=15)
    ax.set_ylim(0, 53)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    caption_90 = (
        "Caption: Primary later-calendar-day repeat purchase within 90 days. Population limited to customers acquired on or before 2011-09-10.\n"
        "Test e (Nov 2010 vs Other): z = -4.31, p < 0.0001; Test f (Dec 2010 vs Other): z = -4.66, p < 0.0001 (both survive threshold 0.00625 for 8 tests).\n"
        "Nov 2010 vs Oct 2010 alone (p = 0.0254, exploratory) does not survive the 8-test threshold (0.00625).\n"
        "The shutdown and holiday timing cannot be separated."
    )
    plt.figtext(0.5, 0.015, caption_90, ha="center", fontsize=8.2, style="italic")
    plt.tight_layout(rect=[0, 0.09, 1, 1])
    plt.savefig("outputs/repeat_90d_benchmarks.png", dpi=300, bbox_inches="tight")
    plt.close()

    # --------------------------------------------------------------------------
    # 2. retention_heatmap.png
    # --------------------------------------------------------------------------
    print("Generating Chart 2: retention_heatmap.png...")
    ret_df = pd.read_csv("outputs/cohort_retention_m0_6.csv")
    pivot_df = ret_df.pivot(index="cohort", columns="month_n", values="retention_pct")
    cohort_sizes = ret_df[ret_df["month_n"] == 0].set_index("cohort")["cohort_size"]

    # Mask every cell where cohort_month + month_n >= 2011-12
    mask = pd.DataFrame(False, index=pivot_df.index, columns=pivot_df.columns)
    for cohort in pivot_df.index:
        c_dt = pd.to_datetime(cohort + '-01')
        for m_n in pivot_df.columns:
            act_dt = c_dt + pd.DateOffset(months=int(m_n))
            if act_dt >= pd.to_datetime('2011-12-01'):
                mask.loc[cohort, m_n] = True

    pivot_df.index = [f"{c} (n={cohort_sizes.loc[c]:,})" for c in pivot_df.index]
    mask.index = pivot_df.index

    plt.figure(figsize=(10, 8.5))
    sns.heatmap(
        pivot_df, 
        annot=True, 
        fmt=".1f", 
        cmap="YlGnBu", 
        mask=mask,
        vmin=0, 
        vmax=40, 
        cbar_kws={'label': 'Retention Rate (%)'}, 
        linewidths=0.5
    )
    plt.title("Cohort Retention Rate (%): Cohorts Jan 2010 – Sep 2011 (Months 0–6)", fontsize=12, pad=15, fontweight='bold')
    plt.xlabel("Month Number (Months Since Acquisition)", fontsize=10, labelpad=8)
    plt.ylabel("Acquisition Cohort (n Customers)", fontsize=10, labelpad=8)
    
    caption_heat = (
        "Caption: Cells in Dec 2011 omitted: data ends 2011-12-09. Dec 2009 cohort excluded due to left-censoring.\n"
        "Oct-Dec 2011 cohorts excluded due to <3 months observable follow-up. Color scale capped at 40% (Month 0 annotated at 100.0%)."
    )
    plt.figtext(0.5, 0.015, caption_heat, ha="center", fontsize=8.5, style="italic")
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig("outputs/retention_heatmap.png", dpi=300, bbox_inches="tight")
    plt.close()

    # --------------------------------------------------------------------------
    # 3. same_month_comparison.png
    # --------------------------------------------------------------------------
    print("Generating Chart 3: same_month_comparison.png...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.8), sharey=True)

    # Panel 1: December 2010 Activity
    p1_labels = ["Nov 2010\n(n = 325)", "Pooled Jun–Oct 2010\n(n = 1,238)"]
    p1_rates = [17.54, 13.97]
    p1_ci_low = [13.79, 12.15]
    p1_ci_high = [22.05, 16.02]
    p1_colors = ['#1f77b4', '#7f7f7f']
    p1_err = [[r - l for r, l in zip(p1_rates, p1_ci_low)], [h - r for r, h in zip(p1_rates, p1_ci_high)]]

    bars1 = ax1.bar(range(len(p1_rates)), p1_rates, yerr=p1_err, capsize=6, color=p1_colors, edgecolor='black', width=0.45)
    for bar, r, ci_high in zip(bars1, p1_rates, p1_ci_high):
        x = bar.get_x() + bar.get_width() / 2.
        ax1.text(x, ci_high + 0.8, f"{r:.2f}%", ha="center", va="bottom", fontsize=9.5, fontweight="bold")
    ax1.set_xticks(range(len(p1_labels)))
    ax1.set_xticklabels(p1_labels, fontsize=9.5)
    ax1.set_title("Panel A: Dec 2010 Activity (Test a)", fontsize=11, fontweight='bold')
    ax1.set_ylabel("Active Customer Rate in Calendar Month (%)", fontsize=10.5)
    ax1.set_ylim(0, 26.5)
    ax1.grid(axis='y', linestyle='--', alpha=0.5)

    # Panel 2: January 2011 Activity
    p2_labels = ["Nov 2010\n(n = 325)", "Dec 2010\n(n = 76)", "Pooled Jun–Oct 2010\n(n = 1,238)"]
    p2_rates = [9.23, 9.21, 10.74]
    p2_ci_low = [6.54, 4.53, 9.14]
    p2_ci_high = [12.87, 17.81, 12.59]
    p2_colors = ['#1f77b4', '#d62728', '#7f7f7f']
    p2_err = [[r - l for r, l in zip(p2_rates, p2_ci_low)], [h - r for r, h in zip(p2_rates, p2_ci_high)]]

    bars2 = ax2.bar(range(len(p2_rates)), p2_rates, yerr=p2_err, capsize=6, color=p2_colors, edgecolor='black', width=0.45)
    for bar, r, ci_high in zip(bars2, p2_rates, p2_ci_high):
        x = bar.get_x() + bar.get_width() / 2.
        ax2.text(x, ci_high + 0.8, f"{r:.2f}%", ha="center", va="bottom", fontsize=9.5, fontweight="bold")
    ax2.set_xticks(range(len(p2_labels)))
    ax2.set_xticklabels(p2_labels, fontsize=9.5)
    ax2.set_title("Panel B: Jan 2011 Activity (Tests b & c)", fontsize=11, fontweight='bold')
    ax2.grid(axis='y', linestyle='--', alpha=0.5)

    fig.suptitle("Same-Month Retention Comparison with 95% Wilson CIs", fontsize=12.5, fontweight='bold', y=0.98)
    caption_sm = (
        "Caption: No invoices 2010-12-24 to 2011-01-03. Two-proportion z-test p-values: Test a = 0.1065, Test b = 0.4272, Test c = 0.6742 (none survive correction).\n"
        "Fixed cohort colors: Nov 2010 (blue), Dec 2010 (red), Pooled Jun–Oct 2010 baseline (gray). Error bars represent 95% Wilson CIs."
    )
    plt.figtext(0.5, 0.015, caption_sm, ha="center", fontsize=8.5, style="italic")
    plt.tight_layout(rect=[0, 0.07, 1, 0.95])
    plt.savefig("outputs/same_month_comparison.png", dpi=300, bbox_inches="tight")
    plt.close()

    # --------------------------------------------------------------------------
    # 4. seasonal_return.png
    # --------------------------------------------------------------------------
    print("Generating Chart 4: seasonal_return.png...")
    labels_sr = ["Nov 2010 Cohort\n(n = 325)", "Jan–Oct 2010 Cohorts\n(n = 2,986)"]
    rates_sr = [25.54, 20.46]
    ci_low_sr = [21.10, 19.05]
    ci_high_sr = [30.55, 21.95]
    err_low_sr = [r - l for r, l in zip(rates_sr, ci_low_sr)]
    err_high_sr = [h - r for r, h in zip(rates_sr, ci_high_sr)]

    plt.figure(figsize=(7, 6))
    bars_sr = plt.bar([0, 1], rates_sr, yerr=[err_low_sr, err_high_sr], capsize=7, color=['#1f77b4', '#7f7f7f'], edgecolor='black', width=0.48)
    for bar, r, ci_high in zip(bars_sr, rates_sr, ci_high_sr):
        x = bar.get_x() + bar.get_width() / 2.
        plt.text(x, ci_high + 0.8, f"{r:.2f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")
    plt.xticks([0, 1], labels_sr, fontsize=10)
    plt.ylabel("Return Rate in Nov 2011 (%)", fontsize=10.5)
    plt.title("Seasonal Return in November 2011 Peak (Test d)\nwith 95% Wilson Confidence Intervals", fontsize=12, fontweight='bold', pad=12)
    plt.ylim(0, 36)
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    
    caption_sr = (
        "Caption: Comparing activity during subsequent holiday peak (Nov 2011). Two-proportion z = 2.14, p = 0.0327.\n"
        "Does not survive Bonferroni multiple-comparison threshold (alpha = 0.00625, 8 tests).\n"
        "Nov 2010 cohort has 12 months' tenure; comparison cohorts 13-22."
    )
    plt.figtext(0.5, 0.015, caption_sr, ha="center", fontsize=8.2, style="italic")
    plt.tight_layout(rect=[0, 0.07, 1, 1])
    plt.savefig("outputs/seasonal_return.png", dpi=300, bbox_inches="tight")
    plt.close()

    # --------------------------------------------------------------------------
    # 5. calendar_activity_trend.png
    # --------------------------------------------------------------------------
    print("Generating Chart 5: calendar_activity_trend.png...")
    cal_df = pd.read_csv("outputs/calendar_activity.csv")
    months_list = list(cal_df['calendar_month'])
    idx_dec = months_list.index('2010-12')
    idx_jan = months_list.index('2011-01')

    plt.figure(figsize=(11, 5.8))
    plt.plot(range(len(months_list)), cal_df['activity_rate_pct'], marker='o', color='#1f77b4', linewidth=2, label='Calendar Activity Rate (%)')
    plt.axvspan(idx_dec - 0.5, idx_jan + 0.5, color='orange', alpha=0.25, label='Holiday Peak / Year-End Shading (Dec 2010 – Jan 2011)')
    plt.xticks(range(len(months_list)), months_list, rotation=45, ha='right')
    plt.ylabel("Active Customers / Previously Acquired Customers (%)", fontsize=10.5)
    plt.xlabel("Calendar Month", fontsize=10.5)
    plt.title("Share of previously acquired customers active each month", fontsize=12, fontweight='bold', pad=15)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(loc='upper right')

    caption_cal = (
        "Caption: Rate also falls as the base of one-time customers accumulates; the 2011 level is not attributable to the shutdown.\n"
        "Operational shutdown occurred from Dec 24, 2010 to Jan 3, 2011 (shaded: full months Dec 2010 and Jan 2011). Denominator excludes customers acquired in or after that month."
    )
    plt.figtext(0.5, 0.015, caption_cal, ha="center", fontsize=8.2, style="italic")
    plt.tight_layout(rect=[0, 0.06, 1, 1])
    plt.savefig("outputs/calendar_activity_trend.png", dpi=300, bbox_inches="tight")
    plt.close()

    # --------------------------------------------------------------------------
    # 6. median_revenue_6m_bootstrap.png
    # --------------------------------------------------------------------------
    print("Generating Chart 6: median_revenue_6m_bootstrap.png...")
    boot_df = pd.read_csv("outputs/bootstrap_median_revenue_ci.csv")
    labels_b = [
        "Nov 2010\n(n = 325)",
        "Dec 2010\n(n = 76)",
        "Other Cohorts (Jan 2010–Jun 2011)\n(n = 3,685)"
    ]
    medians_b = boot_df['median_6m_revenue'].values
    ci_low_b = boot_df['ci_95_low'].values
    ci_high_b = boot_df['ci_95_high'].values
    ns_b = boot_df['n_customers'].values

    yerr_low_b = medians_b - ci_low_b
    yerr_high_b = ci_high_b - medians_b

    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    colors_b = ['#1f77b4', '#d62728', '#7f7f7f']
    bars_b = ax.bar([0, 1, 2], medians_b, yerr=[yerr_low_b, yerr_high_b], capsize=8, color=colors_b, edgecolor='black', width=0.52, error_kw={'elinewidth': 1.8, 'capthick': 1.8, 'ecolor': '#333333'})

    for i, bar in enumerate(bars_b):
        h = bar.get_height()
        x = bar.get_x() + bar.get_width() / 2.
        ax.text(
            x, 
            ci_high_b[i] + 16, 
            f'£{medians_b[i]:.2f}\n[£{ci_low_b[i]:.2f}, £{ci_high_b[i]:.2f}]', 
            ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#222222'
        )
        ax.text(
            x, 
            h / 2., 
            f'n = {ns_b[i]:,}', 
            ha='center', va='center', fontsize=11, fontweight='bold', color='white',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.35, edgecolor='none')
        )

    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(labels_b, fontsize=10)
    ax.set_ylabel('Median 6-Month Gross Revenue per Customer (£)', fontsize=11, labelpad=10)
    ax.set_title('Median 6-Month Revenue per Customer (clean_v2) with Bootstrap 95% CIs', fontsize=12, fontweight='bold', pad=15)
    ax.set_ylim(0, 680)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    raw_caption_b = (
        "Caption: Bootstrap 95% percentile confidence intervals calculated from 10,000 resamples with fixed seed (seed=42) "
        "on clean_v2.parquet. Sample sizes shown on each bar: Nov 2010 n=325, Dec 2010 n=76, Other Cohorts (Jan 2010 – Jun 2011) n=3,685. "
        "Dec 2009 cohort excluded due to left-censoring."
    )
    wrapped_caption_b = textwrap.fill(raw_caption_b, 110)
    fig.subplots_adjust(bottom=0.28)
    fig.text(0.5, 0.04, wrapped_caption_b, ha='center', va='bottom', fontsize=8.5, style='italic', color='#444444')
    plt.savefig("outputs/median_revenue_6m_bootstrap.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("All visualizations regenerated successfully.")

if __name__ == "__main__":
    generate_visualizations()
