#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# Configuration
# ============================================================

MODIFIED_FILE = (
    "replay_phased_fixed_metrics_replay_tx_v1_modified_15.xlsx"
)

MODIFIED_SHEET = "per_transaction"

PBS_FILE = "rbuilder_spec_exec_old.csv"

OUTPUT_FILE = (
    "modified_vs_pbs_normal_smart_contract_boxplot.png"
)

TITLE_FONT_SIZE = 22
AXIS_LABEL_FONT_SIZE = 20
TICK_FONT_SIZE = 17
LEGEND_FONT_SIZE = 15


# ============================================================
# Statistics helper
# ============================================================

def calculate_statistics(values):

    return {
        "count": len(values),
        "mean": values.mean(),
        "std": values.std(),
        "median": values.median(),
        "minimum": values.min(),
        "q1": values.quantile(0.25),
        "q3": values.quantile(0.75),
        "maximum": values.max(),
        "p95": values.quantile(0.95),
        "p99": values.quantile(0.99),
    }


# ============================================================
# METHOD 1:
# Modified smart-contract execution
#
# contract_address_mapped == True
# successful_call_reused == True
# status == SUCCESS
#
# metric:
# block_timestamp_latency_sec
# ============================================================

modified_df = pd.read_excel(
    MODIFIED_FILE,
    sheet_name=MODIFIED_SHEET,
    engine="openpyxl",
)


# Normalize booleans safely
modified_df["contract_address_mapped"] = (
    modified_df["contract_address_mapped"]
    .astype(str)
    .str.strip()
    .str.lower()
    .eq("true")
)

modified_df["successful_call_reused"] = (
    modified_df["successful_call_reused"]
    .astype(str)
    .str.strip()
    .str.lower()
    .eq("true")
)


# Normalize status
modified_df["status"] = (
    modified_df["status"]
    .astype(str)
    .str.strip()
    .str.upper()
)


# Numeric latency
modified_df["block_timestamp_latency_sec"] = pd.to_numeric(
    modified_df["block_timestamp_latency_sec"],
    errors="coerce",
)


# ============================================================
# Apply modified filter
# ============================================================

modified_filtered = modified_df[
    (modified_df["contract_address_mapped"] == True)
    & (modified_df["successful_call_reused"] == True)
    & (modified_df["status"] == "SUCCESS")
].copy()


modified_filtered = modified_filtered.dropna(
    subset=["block_timestamp_latency_sec"]
)


# Remove negative latency if any
modified_filtered = modified_filtered[
    modified_filtered["block_timestamp_latency_sec"] >= 0
].copy()


modified_values = modified_filtered[
    "block_timestamp_latency_sec"
].copy()


# ============================================================
# METHOD 2:
# PBS Ethereum normal smart-contract execution
#
# CSV:
# 0 timestamp
# 1 tx_hash
# 2 duration_us
# 3 gas
# 4 flag
#
# Filter:
# gas != 21000
# flag == False
# ============================================================

pbs_df = pd.read_csv(
    PBS_FILE,
    header=None,
    names=[
        "timestamp_ms",
        "tx_hash",
        "duration_us",
        "gas",
        "flag",
    ],
)


pbs_df["duration_us"] = pd.to_numeric(
    pbs_df["duration_us"],
    errors="coerce",
)


pbs_df["gas"] = pd.to_numeric(
    pbs_df["gas"],
    errors="coerce",
)


pbs_df["flag"] = (
    pbs_df["flag"]
    .astype(str)
    .str.strip()
    .str.lower()
    .eq("true")
)


# ============================================================
# Apply PBS filter
# ============================================================

pbs_filtered = pbs_df[
    (pbs_df["gas"] != 21000)
    & (pbs_df["flag"] == False)
].copy()


pbs_filtered = pbs_filtered.dropna(
    subset=[
        "tx_hash",
        "duration_us",
        "gas",
    ]
)


# ============================================================
# Average repeated measurements per tx_hash
# ============================================================

pbs_per_transaction = (
    pbs_filtered
    .groupby(
        "tx_hash",
        as_index=False,
    )
    .agg(
        average_duration_us=(
            "duration_us",
            "mean",
        ),
        measurement_count=(
            "duration_us",
            "count",
        ),
        gas=(
            "gas",
            "first",
        ),
    )
)


# ============================================================
# Convert microseconds -> seconds
# ============================================================

pbs_per_transaction["average_duration_sec"] = (
    pbs_per_transaction["average_duration_us"]
    / 1_000_000.0
)


pbs_values = pbs_per_transaction[
    "average_duration_sec"
].copy()


# ============================================================
# Statistics
# ============================================================

modified_stats = calculate_statistics(
    modified_values
)

pbs_stats = calculate_statistics(
    pbs_values
)


# ============================================================
# Print statistics
# ============================================================

print()
print("=" * 90)
print("MODIFIED SMART-CONTRACT EXECUTION")
print("=" * 90)

print(
    "Transactions       : {:,}".format(
        modified_stats["count"]
    )
)

print(
    "Average            : {:.6f} sec".format(
        modified_stats["mean"]
    )
)

print(
    "Standard deviation : {:.6f} sec".format(
        modified_stats["std"]
    )
)

print(
    "Median             : {:.6f} sec".format(
        modified_stats["median"]
    )
)

print(
    "P95                : {:.6f} sec".format(
        modified_stats["p95"]
    )
)

print(
    "P99                : {:.6f} sec".format(
        modified_stats["p99"]
    )
)


print()
print("=" * 90)
print("PBS ETHEREUM NORMAL SMART-CONTRACT EXECUTION")
print("=" * 90)

print(
    "Filtered raw rows   : {:,}".format(
        len(pbs_filtered)
    )
)

print(
    "Unique transactions : {:,}".format(
        pbs_stats["count"]
    )
)

print(
    "Average            : {:.9f} sec".format(
        pbs_stats["mean"]
    )
)

print(
    "Standard deviation : {:.9f} sec".format(
        pbs_stats["std"]
    )
)

print(
    "Median             : {:.9f} sec".format(
        pbs_stats["median"]
    )
)

print(
    "P95                : {:.9f} sec".format(
        pbs_stats["p95"]
    )
)

print(
    "P99                : {:.9f} sec".format(
        pbs_stats["p99"]
    )
)


# ============================================================
# Combined box plot
# ============================================================

figure, axis = plt.subplots(
    figsize=(11, 8)
)


box_data = [
    modified_values,
    pbs_values,
]


box_labels = [
    "Modified Smart Contract",
    "PBS Normal Smart Contract",
]


axis.boxplot(
    box_data,
    widths=0.50,
    showmeans=False,
    showfliers=True,
    whis=1.5,
)


# ============================================================
# Mean ± Standard deviation
# ============================================================

means = [
    modified_stats["mean"],
    pbs_stats["mean"],
]


stds = [
    modified_stats["std"],
    pbs_stats["std"],
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
# Labels
# ============================================================

axis.set_title(
    "Smart-Contract Execution Distribution",
    fontsize=TITLE_FONT_SIZE,
    pad=15,
)


axis.set_ylabel(
    "Latency / Execution Time (seconds)",
    fontsize=AXIS_LABEL_FONT_SIZE,
)


axis.set_xlabel(
    "Method",
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


axis.grid(
    axis="y",
    linestyle="--",
    alpha=0.5,
)


# ============================================================
# Statistics text
# ============================================================

statistics_text = (
    "Modified Smart Contract\n"
    "N = {:,}\n"
    "Mean = {:.3f} s\n"
    "Std Dev = {:.3f} s\n"
    "Median = {:.3f} s\n\n"
    "PBS Normal Smart Contract\n"
    "N = {:,}\n"
    "Mean = {:.6f} s\n"
    "Std Dev = {:.6f} s\n"
    "Median = {:.6f} s"
).format(
    modified_stats["count"],
    modified_stats["mean"],
    modified_stats["std"],
    modified_stats["median"],

    pbs_stats["count"],
    pbs_stats["mean"],
    pbs_stats["std"],
    pbs_stats["median"],
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
print("Combined box plot saved as:")
print(OUTPUT_FILE)
print("=" * 90)


plt.show()

plt.close(
    figure
)