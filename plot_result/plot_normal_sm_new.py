#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


# ============================================================
# Configuration
# ============================================================

MODIFIED_FILES = [
    Path(
        "replay_phased_fixed_metrics_replay_tx_v{}_modified_15.xlsx".format(i)
    )
    for i in range(1, 11)
]

NORMAL_FILES = [
    Path(
        "replay_phased_fixed_metrics_replay_tx_v{}_sm_normal.xlsx".format(i)
    )
    for i in range(1, 11)
]

SHEET_NAME = "per_transaction"

LATENCY_COLUMN = "block_timestamp_latency_sec"

OUTPUT_FILE = (
    "modified_vs_pbs_normal_v1_v10_smart_contract_latency_boxplot.png"
)

TITLE_FONT_SIZE = 22
AXIS_LABEL_FONT_SIZE = 20
TICK_FONT_SIZE = 17
LEGEND_FONT_SIZE = 15


# ============================================================
# Helper: load and filter ONE file
# ============================================================

def load_smart_contract_latency(file_path, case_name):

    print(
        "Loading {}: {}".format(case_name, file_path),
        flush=True,
    )

    if not file_path.exists():
        print(
            "  WARNING: File not found. Skipping: {}".format(file_path),
            flush=True,
        )
        return pd.Series(dtype=float)

    df = pd.read_excel(
        file_path,
        sheet_name=SHEET_NAME,
        engine="openpyxl",

        # Same columns as original script
        usecols=[
            "contract_address_mapped",
            "successful_call_reused",
            "status",
            LATENCY_COLUMN,
        ],
    )

    print(
        "  Total rows loaded: {:,}".format(len(df)),
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
    # SAME smart-contract filter as original script
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
# Helper: combine v1-v10
# ============================================================

def load_all_runs(file_list, case_name):

    all_values = []

    print()
    print("=" * 90)
    print("{} - LOADING V1 TO V10".format(case_name))
    print("=" * 90)

    total_rows = 0

    for run_number, file_path in enumerate(file_list, start=1):

        values = load_smart_contract_latency(
            file_path,
            "{} v{}".format(case_name, run_number),
        )

        print(
            "  v{} qualifying transactions: {:,}".format(
                run_number,
                len(values),
            )
        )

        total_rows += len(values)

        if len(values) > 0:
            all_values.append(values)

    if not all_values:
        raise RuntimeError(
            "No qualifying transactions found for {}.".format(case_name)
        )

    combined = pd.concat(
        all_values,
        ignore_index=True,
    )

    print()
    print(
        "{} TOTAL v1-v10 TRANSACTIONS: {:,}".format(
            case_name,
            len(combined),
        )
    )

    return combined


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
# Load Modified v1-v10
# ============================================================

modified_values = load_all_runs(
    MODIFIED_FILES,
    "Modified Protocol",
)


# ============================================================
# Load Normal v1-v10
# ============================================================

normal_values = load_all_runs(
    NORMAL_FILES,
    "PBS Normal",
)


# ============================================================
# Make both groups use equal sample size
# ============================================================

N_EQUAL = min(
    len(modified_values),
    len(normal_values),
)

print("Equal N used for both groups:", N_EQUAL)

modified_values = modified_values.sample(
    n=N_EQUAL,
    random_state=42,
).reset_index(drop=True)

normal_values = normal_values.sample(
    n=N_EQUAL,
    random_state=42,
).reset_index(drop=True)


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
print("=" * 90)
print("MODIFIED PROTOCOL - V1 TO V10 COMBINED")
print("=" * 90)

print(
    "Total transactions : {:,}".format(
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
print("=" * 90)
print("PBS NORMAL - V1 TO V10 COMBINED")
print("=" * 90)

print(
    "Total transactions : {:,}".format(
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
print("=" * 90)
print("COMPARISON - ALL V1 TO V10 TRANSACTIONS")
print("=" * 90)

print(
    "Modified total      : {:,}".format(
        modified_stats["count"]
    )
)

print(
    "PBS Normal total    : {:,}".format(
        normal_stats["count"]
    )
)

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
    "Our Protocol",
    "Normal Ethereum",
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
    #showfliers=True,
    showfliers=False,
    # Tukey whiskers
    whis=1.5,
)

# ============================================================
# Automatically zoom y-axis
# ============================================================

combined_values = pd.concat(
    [
        modified_values,
        normal_values,
    ],
    ignore_index=True,
)

plot_upper_limit = (
    combined_values.quantile(0.99)
    * 1.20
)

axis.set_ylim(
    0,
    plot_upper_limit,
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

# axis.set_title(
#     "Smart-Contract Block Inclusion Latency (v1-v10 Combined)",
#     fontsize=TITLE_FONT_SIZE,
#     pad=15,
# )


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

# statistics_text = (
#     "Our Protocol\n"
#     "N = {:,}\n"
#     "Mean = {:.2f} s\n"
#     "Std Dev = {:.2f} s\n"
#     "Median = {:.2f} s\n"
#     "P95 = {:.2f} s\n\n"

#     "PBS Normal\n"
#     "N = {:,}\n"
#     "Mean = {:.2f} s\n"
#     "Std Dev = {:.2f} s\n"
#     "Median = {:.2f} s\n"
#     "P95 = {:.2f} s"
# ).format(
#     modified_stats["count"],
#     modified_stats["mean"],
#     modified_stats["std"],
#     modified_stats["median"],
#     modified_stats["p95"],

#     normal_stats["count"],
#     normal_stats["mean"],
#     normal_stats["std"],
#     normal_stats["median"],
#     normal_stats["p95"],
# )


# axis.text(
#     1.02,
#     0.97,
#     statistics_text,
#     transform=axis.transAxes,
#     fontsize=14,
#     verticalalignment="top",
#     bbox=dict(
#         boxstyle="round",
#         alpha=0.15,
#     ),
# )


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
print("=" * 90)
print("Box plot saved as:")
print(OUTPUT_FILE)
print("=" * 90)


# If running on SSH/headless server,
# leave plt.show() disabled.

# plt.show()

plt.close(
    figure
)