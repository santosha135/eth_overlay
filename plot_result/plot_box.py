#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# Configuration
# ============================================================

POLICY_FILE = "tx_policy_metrics_15_new.xlsx"
POLICY_SHEET = "policy_metrics"

REGULAR_FILE = "rbuilder_spec_exec.csv"

OUTPUT_FILE = "runtime_bytecode_vs_regular_boxplot.png"

TITLE_FONT_SIZE = 22
AXIS_LABEL_FONT_SIZE = 20
TICK_FONT_SIZE = 17
LEGEND_FONT_SIZE = 15


# ============================================================
# METHOD 1
# CONTRACT_INTERACTION + runtime_bytecode
# ============================================================

policy_df = pd.read_excel(
    POLICY_FILE,
    sheet_name=POLICY_SHEET,
    engine="openpyxl",
)

runtime_df = policy_df[
    (policy_df["operation_type"] == "CONTRACT_INTERACTION")
    & (policy_df["check_type"] == "runtime_bytecode")
].copy()

runtime_df["bytecode_duration_us"] = pd.to_numeric(
    runtime_df["bytecode_duration_us"],
    errors="coerce",
)

runtime_df = runtime_df.dropna(
    subset=["bytecode_duration_us"]
)

runtime_values = runtime_df[
    "bytecode_duration_us"
].copy()


# ============================================================
# METHOD 2
# Regular execution CSV
#
# CSV columns:
# 0 = timestamp
# 1 = transaction hash
# 2 = execution duration in us
# 3 = gas
# 4 = boolean flag
# ============================================================

regular_df = pd.read_csv(
    REGULAR_FILE,
    header=None,
    names=[
        "timestamp_ms",
        "tx_hash",
        "duration_us",
        "gas",
        "flag",
    ],
)


# ============================================================
# Convert columns
# ============================================================

regular_df["duration_us"] = pd.to_numeric(
    regular_df["duration_us"],
    errors="coerce",
)

regular_df["gas"] = pd.to_numeric(
    regular_df["gas"],
    errors="coerce",
)

regular_df["flag"] = (
    regular_df["flag"]
    .astype(str)
    .str.strip()
    .str.lower()
    .eq("true")
)


# ============================================================
# Filter regular transactions
#
# gas != 21000
# flag == True
# ============================================================

regular_filtered = regular_df[
    (regular_df["gas"] != 21000)
    & (regular_df["flag"] == True)
].copy()

regular_filtered = regular_filtered.dropna(
    subset=[
        "tx_hash",
        "duration_us",
        "gas",
    ]
)


# ============================================================
# Average repeated measurements for each transaction
# ============================================================

regular_per_transaction = (
    regular_filtered
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

regular_values = regular_per_transaction[
    "average_duration_us"
].copy()


# ============================================================
# Statistics helper
# ============================================================

def calculate_statistics(values):

    return {
        "count": len(values),
        "total": values.sum(),
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


runtime_stats = calculate_statistics(
    runtime_values
)

regular_stats = calculate_statistics(
    regular_values
)


# ============================================================
# Print statistics
# ============================================================

print()
print("=" * 80)
print("METHOD 1: CONTRACT_INTERACTION + runtime_bytecode")
print("=" * 80)

print(
    "Samples             : {:,}".format(
        runtime_stats["count"]
    )
)

print(
    "Total duration      : {:.3f} us".format(
        runtime_stats["total"]
    )
)

print(
    "Average             : {:.3f} us".format(
        runtime_stats["mean"]
    )
)

print(
    "Standard deviation  : {:.3f} us".format(
        runtime_stats["std"]
    )
)

print(
    "Median              : {:.3f} us".format(
        runtime_stats["median"]
    )
)

print(
    "Q1                  : {:.3f} us".format(
        runtime_stats["q1"]
    )
)

print(
    "Q3                  : {:.3f} us".format(
        runtime_stats["q3"]
    )
)

print(
    "Minimum             : {:.3f} us".format(
        runtime_stats["minimum"]
    )
)

print(
    "Maximum             : {:.3f} us".format(
        runtime_stats["maximum"]
    )
)

print(
    "P95                 : {:.3f} us".format(
        runtime_stats["p95"]
    )
)

print(
    "P99                 : {:.3f} us".format(
        runtime_stats["p99"]
    )
)


print()
print("=" * 80)
print("METHOD 2: Regular transaction execution")
print("Filter: gas != 21000 AND flag == True")
print("Repeated measurements averaged by tx_hash")
print("=" * 80)

print(
    "Filtered raw rows   : {:,}".format(
        len(regular_filtered)
    )
)

print(
    "Unique transactions : {:,}".format(
        regular_stats["count"]
    )
)

print(
    "Total avg duration  : {:.3f} us".format(
        regular_stats["total"]
    )
)

print(
    "Average             : {:.3f} us".format(
        regular_stats["mean"]
    )
)

print(
    "Standard deviation  : {:.3f} us".format(
        regular_stats["std"]
    )
)

print(
    "Median              : {:.3f} us".format(
        regular_stats["median"]
    )
)

print(
    "Q1                  : {:.3f} us".format(
        regular_stats["q1"]
    )
)

print(
    "Q3                  : {:.3f} us".format(
        regular_stats["q3"]
    )
)

print(
    "Minimum             : {:.3f} us".format(
        regular_stats["minimum"]
    )
)

print(
    "Maximum             : {:.3f} us".format(
        regular_stats["maximum"]
    )
)

print(
    "P95                 : {:.3f} us".format(
        regular_stats["p95"]
    )
)

print(
    "P99                 : {:.3f} us".format(
        regular_stats["p99"]
    )
)


# ============================================================
# Comparison
# ============================================================

difference = (
    runtime_stats["mean"]
    - regular_stats["mean"]
)

print()
print("=" * 80)
print("COMPARISON")
print("=" * 80)

print(
    "Runtime bytecode mean : {:.3f} us".format(
        runtime_stats["mean"]
    )
)

print(
    "Regular mean          : {:.3f} us".format(
        regular_stats["mean"]
    )
)

print(
    "Mean difference       : {:.3f} us".format(
        difference
    )
)

print(
    "Runtime std dev       : {:.3f} us".format(
        runtime_stats["std"]
    )
)

print(
    "Regular std dev       : {:.3f} us".format(
        regular_stats["std"]
    )
)


# ============================================================
# Box plot
# ============================================================

figure, axis = plt.subplots(
    figsize=(11, 8)
)

box_data = [
    runtime_values,
    regular_values,
]

box_labels = [
    "Runtime Bytecode",
    "Regular Execution",
]

# axis.boxplot(
#     box_data,
#     widths=0.50,

#     # Show arithmetic mean
#     showmeans=True,

#     # Mean shown as line
#     meanline=True,

#     # Show outliers
#     showfliers=True,

#     # Standard Tukey whiskers:
#     # Q1 - 1.5*IQR and Q3 + 1.5*IQR
#     whis=1.5,
# )
axis.boxplot(
    box_data,
    widths=0.50,
    showmeans=False,
    showfliers=True,
    whis=1.5,
)


# ============================================================
# Title and labels
# ============================================================

axis.set_title(
    "Execution-Time Distribution",
    fontsize=TITLE_FONT_SIZE,
    pad=15,
)

axis.set_ylabel(
    "Execution Duration (µs)",
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


# ============================================================
# Grid
# ============================================================

axis.grid(
    axis="y",
    linestyle="--",
    alpha=0.5,
)


# ============================================================
# Add mean ± standard deviation markers
# ============================================================

means = [
    runtime_stats["mean"],
    regular_stats["mean"],
]

stds = [
    runtime_stats["std"],
    regular_stats["std"],
]

# axis.errorbar(
#     [1, 2],
#     means,
#     yerr=stds,

#     fmt="o",
#     capsize=8,
#     linewidth=2,
#     markersize=7,

#     label="Mean ± Standard Deviation",
# )
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
# Statistics text
# ============================================================

statistics_text = (
    "Runtime Bytecode\n"
    "N = {:,}\n"
    "Mean = {:.2f} µs\n"
    "Std Dev = {:.2f} µs\n"
    "Median = {:.2f} µs\n\n"
    "Regular Execution\n"
    "N = {:,}\n"
    "Mean = {:.2f} µs\n"
    "Std Dev = {:.2f} µs\n"
    "Median = {:.2f} µs"
).format(
    runtime_stats["count"],
    runtime_stats["mean"],
    runtime_stats["std"],
    runtime_stats["median"],

    regular_stats["count"],
    regular_stats["mean"],
    regular_stats["std"],
    regular_stats["median"],
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
print("=" * 80)
print("Box plot saved as:")
print(OUTPUT_FILE)
print("=" * 80)

plt.show()

plt.close(
    figure
)