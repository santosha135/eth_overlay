#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# Configuration
# ============================================================

MODIFIED_FILE = (
    "replay_phased_fixed_metrics_replay_tx_v1_modified_15.xlsx"
)

NORMAL_FILE = (
    "replay_phased_fixed_metrics_replay_tx_v1_normal.xlsx"
)

SHEET_NAME = "per_transaction"

LATENCY_COLUMN = "block_timestamp_latency_sec"

OUTPUT_FILE = (
    "modified_vs_pbs_normal_smart_contract_latency_boxplot.png"
)

TITLE_FONT_SIZE = 22
AXIS_LABEL_FONT_SIZE = 20
TICK_FONT_SIZE = 17
LEGEND_FONT_SIZE = 15


# ============================================================
# Helper: load and filter smart-contract transactions
# ============================================================

def load_smart_contract_latency(
    file_path,
    case_name,
):

    print(
        "Loading {}...".format(case_name),
        flush=True,
    )

    df = pd.read_excel(
        file_path,
        sheet_name=SHEET_NAME,
        engine="openpyxl",

        # Only read columns needed for this plot
        usecols=[
            "contract_address_mapped",
            "successful_call_reused",
            "status",
            LATENCY_COLUMN,
        ],
    )

    print(
        "  Total rows loaded: {:,}".format(
            len(df)
        ),
        flush=True,
    )

    # --------------------------------------------------------
    # Normalize boolean columns
    # --------------------------------------------------------

    df["contract_address_mapped"] = (
        df["contract_address_mapped"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )

    df["successful_call_reused"] = (
        df["successful_call_reused"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )

    # --------------------------------------------------------
    # Normalize status
    # --------------------------------------------------------

    df["status"] = (
        df["status"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # --------------------------------------------------------
    # Convert latency to numeric
    # --------------------------------------------------------

    df[LATENCY_COLUMN] = pd.to_numeric(
        df[LATENCY_COLUMN],
        errors="coerce",
    )

    # --------------------------------------------------------
    # Apply requested smart-contract filter
    # --------------------------------------------------------

    filtered = df[
        (df["contract_address_mapped"] == True)
        & (df["successful_call_reused"] == True)
        & (df["status"] == "SUCCESS")
        & (df[LATENCY_COLUMN].notna())
        & (df[LATENCY_COLUMN] >= 0)
    ].copy()

    print(
        "  Smart-contract transactions: {:,}".format(
            len(filtered)
        ),
        flush=True,
    )

    return filtered[LATENCY_COLUMN].copy()


# ============================================================
# Statistics helper
# ============================================================

def calculate_statistics(values):

    return {
        "count": int(len(values)),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "median": float(values.median()),
        "minimum": float(values.min()),
        "q1": float(values.quantile(0.25)),
        "q3": float(values.quantile(0.75)),
        "maximum": float(values.max()),
        "p90": float(values.quantile(0.90)),
        "p95": float(values.quantile(0.95)),
        "p99": float(values.quantile(0.99)),
    }


# ============================================================
# Load both methods
# ============================================================

modified_values = load_smart_contract_latency(
    MODIFIED_FILE,
    "Modified Protocol",
)

normal_values = load_smart_contract_latency(
    NORMAL_FILE,
    "PBS Normal",
)


# ============================================================
# Calculate statistics
# ============================================================

modified_stats = calculate_statistics(
    modified_values
)

normal_stats = calculate_statistics(
    normal_values
)


# ============================================================
# Print statistics
# ============================================================

print()
print("=" * 85)
print("MODIFIED PROTOCOL - SMART CONTRACT")
print("=" * 85)

print(
    "Transactions       : {:,}".format(
        modified_stats["count"]
    )
)

print(
    "Average            : {:.3f} seconds".format(
        modified_stats["mean"]
    )
)

print(
    "Standard deviation : {:.3f} seconds".format(
        modified_stats["std"]
    )
)

print(
    "Median             : {:.3f} seconds".format(
        modified_stats["median"]
    )
)

print(
    "Minimum            : {:.3f} seconds".format(
        modified_stats["minimum"]
    )
)

print(
    "Q1                 : {:.3f} seconds".format(
        modified_stats["q1"]
    )
)

print(
    "Q3                 : {:.3f} seconds".format(
        modified_stats["q3"]
    )
)

print(
    "P90                : {:.3f} seconds".format(
        modified_stats["p90"]
    )
)

print(
    "P95                : {:.3f} seconds".format(
        modified_stats["p95"]
    )
)

print(
    "P99                : {:.3f} seconds".format(
        modified_stats["p99"]
    )
)

print(
    "Maximum            : {:.3f} seconds".format(
        modified_stats["maximum"]
    )
)


print()
print("=" * 85)
print("PBS NORMAL - SMART CONTRACT")
print("=" * 85)

print(
    "Transactions       : {:,}".format(
        normal_stats["count"]
    )
)

print(
    "Average            : {:.3f} seconds".format(
        normal_stats["mean"]
    )
)

print(
    "Standard deviation : {:.3f} seconds".format(
        normal_stats["std"]
    )
)

print(
    "Median             : {:.3f} seconds".format(
        normal_stats["median"]
    )
)

print(
    "Minimum            : {:.3f} seconds".format(
        normal_stats["minimum"]
    )
)

print(
    "Q1                 : {:.3f} seconds".format(
        normal_stats["q1"]
    )
)

print(
    "Q3                 : {:.3f} seconds".format(
        normal_stats["q3"]
    )
)

print(
    "P90                : {:.3f} seconds".format(
        normal_stats["p90"]
    )
)

print(
    "P95                : {:.3f} seconds".format(
        normal_stats["p95"]
    )
)

print(
    "P99                : {:.3f} seconds".format(
        normal_stats["p99"]
    )
)

print(
    "Maximum            : {:.3f} seconds".format(
        normal_stats["maximum"]
    )
)


# ============================================================
# Comparison
# ============================================================

mean_difference = (
    normal_stats["mean"]
    - modified_stats["mean"]
)

if normal_stats["mean"] > 0:

    improvement_percent = (
        mean_difference
        / normal_stats["mean"]
        * 100.0
    )

else:

    improvement_percent = float("nan")


std_difference = (
    normal_stats["std"]
    - modified_stats["std"]
)


print()
print("=" * 85)
print("COMPARISON")
print("=" * 85)

print(
    "Modified mean       : {:.3f} s".format(
        modified_stats["mean"]
    )
)

print(
    "PBS Normal mean     : {:.3f} s".format(
        normal_stats["mean"]
    )
)

print(
    "Mean reduction      : {:.3f} s".format(
        mean_difference
    )
)

print(
    "Improvement         : {:.2f}%".format(
        improvement_percent
    )
)

print(
    "Modified std dev    : {:.3f} s".format(
        modified_stats["std"]
    )
)

print(
    "PBS Normal std dev  : {:.3f} s".format(
        normal_stats["std"]
    )
)

print(
    "Std-dev reduction   : {:.3f} s".format(
        std_difference
    )
)


# ============================================================
# Create combined box plot
# ============================================================

figure, axis = plt.subplots(
    figsize=(11, 8)
)


box_data = [
    modified_values,
    normal_values,
]


box_labels = [
    "Modified Protocol\nSmart Contract",
    "PBS Normal\nSmart Contract",
]


# ============================================================
# Box plot
# ============================================================

axis.boxplot(
    box_data,
    widths=0.50,

    # Median displayed by normal box-plot line
    showmeans=False,

    # Show outliers
    showfliers=True,

    # Tukey whiskers
    whis=1.5,
)


# ============================================================
# Mean ± Standard Deviation
# ============================================================

means = [
    modified_stats["mean"],
    normal_stats["mean"],
]


stds = [
    modified_stats["std"],
    normal_stats["std"],
]


axis.errorbar(
    [1, 2],
    means,
    yerr=stds,
    fmt="o",
    capsize=8,
    linewidth=2,
    markersize=7,
    label="Mean ± Standard Deviation",
)


# ============================================================
# Title and axes
# ============================================================

axis.set_title(
    "Smart-Contract Block Inclusion Latency",
    fontsize=TITLE_FONT_SIZE,
    pad=15,
)


axis.set_ylabel(
    "Block Timestamp Latency (seconds)",
    fontsize=AXIS_LABEL_FONT_SIZE,
)


axis.set_xlabel(
    "Protocol",
    fontsize=AXIS_LABEL_FONT_SIZE,
)


axis.set_xticks(
    [1, 2]
)


axis.set_xticklabels(
    box_labels,
    fontsize=TICK_FONT_SIZE,
)


axis.tick_params(
    axis="y",
    labelsize=TICK_FONT_SIZE,
)


# ============================================================
# Grid
# ============================================================

axis.grid(
    axis="y",
    linestyle="--",
    alpha=0.5,
)


# ============================================================
# Statistics text box
# ============================================================

statistics_text = (
    "Modified Protocol\n"
    "N = {:,}\n"
    "Mean = {:.2f} s\n"
    "Std Dev = {:.2f} s\n"
    "Median = {:.2f} s\n"
    "P95 = {:.2f} s\n\n"
    "PBS Normal\n"
    "N = {:,}\n"
    "Mean = {:.2f} s\n"
    "Std Dev = {:.2f} s\n"
    "Median = {:.2f} s\n"
    "P95 = {:.2f} s"
).format(
    modified_stats["count"],
    modified_stats["mean"],
    modified_stats["std"],
    modified_stats["median"],
    modified_stats["p95"],

    normal_stats["count"],
    normal_stats["mean"],
    normal_stats["std"],
    normal_stats["median"],
    normal_stats["p95"],
)


axis.text(
    1.02,
    0.97,
    statistics_text,
    transform=axis.transAxes,
    fontsize=14,
    verticalalignment="top",
    bbox=dict(
        boxstyle="round",
        alpha=0.15,
    ),
)


# ============================================================
# Legend
# ============================================================

axis.legend(
    loc="upper left",
    fontsize=LEGEND_FONT_SIZE,
)


# ============================================================
# Save
# ============================================================

figure.tight_layout()


figure.savefig(
    OUTPUT_FILE,
    dpi=300,
    bbox_inches="tight",
)


print()
print("=" * 85)
print("Box plot saved as:")
print(OUTPUT_FILE)
print("=" * 85)


# If running on SSH/headless server,
# you can leave plt.show() disabled.

# plt.show()

plt.close(
    figure
)