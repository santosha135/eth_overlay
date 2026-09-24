#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# CONFIGURATION
# ============================================================

# Modified / Our Protocol
MODIFIED_FILE = "tx_policy_metrics_15_new.xlsx"
MODIFIED_SHEET = "policy_metrics"

# Normal Ethereum
NORMAL_FILE = "rbuilder_spec_exec.csv"

OUTPUT_FILE = "modified_vs_normal_per_transaction.png"

TITLE_FONT_SIZE = 22
AXIS_LABEL_FONT_SIZE = 20
TICK_FONT_SIZE = 17
LEGEND_FONT_SIZE = 16


# ============================================================
# MODIFIED / OUR PROTOCOL
# CONTRACT_INTERACTION + runtime_bytecode
# ============================================================

modified_df = pd.read_excel(
    MODIFIED_FILE,
    sheet_name=MODIFIED_SHEET,
    engine="openpyxl",
)

modified_df = modified_df[
    (modified_df["operation_type"] == "CONTRACT_INTERACTION")
    & (modified_df["check_type"] == "runtime_bytecode")
].copy()

modified_df["bytecode_duration_us"] = pd.to_numeric(
    modified_df["bytecode_duration_us"],
    errors="coerce",
)

modified_df = modified_df.dropna(
    subset=["bytecode_duration_us"]
)

modified_values = modified_df[
    "bytecode_duration_us"
].reset_index(drop=True)


# ============================================================
# NORMAL ETHEREUM
# ============================================================

normal_df = pd.read_csv(
    NORMAL_FILE,
    header=None,
    names=[
        "timestamp_ms",
        "tx_hash",
        "duration_us",
        "gas",
        "flag",
    ],
)


# Convert numeric columns
normal_df["duration_us"] = pd.to_numeric(
    normal_df["duration_us"],
    errors="coerce",
)

normal_df["gas"] = pd.to_numeric(
    normal_df["gas"],
    errors="coerce",
)

normal_df["flag"] = (
    normal_df["flag"]
    .astype(str)
    .str.strip()
    .str.lower()
    .eq("true")
)


# ============================================================
# FILTER NORMAL TRANSACTIONS
# ============================================================

normal_filtered = normal_df[
    (normal_df["gas"] != 21000)
    & (normal_df["flag"] == True)
].copy()

normal_filtered = normal_filtered.dropna(
    subset=[
        "tx_hash",
        "duration_us",
        "gas",
    ]
)


# ============================================================
# ONE VALUE PER NORMAL TRANSACTION
#
# If same transaction was measured multiple times,
# calculate its average execution time.
# ============================================================

normal_per_transaction = (
    normal_filtered
    .groupby(
        "tx_hash",
        as_index=False,
    )
    .agg(
        average_duration_us=("duration_us", "mean"),
        measurement_count=("duration_us", "count"),
        gas=("gas", "first"),
    )
)

normal_values = normal_per_transaction[
    "average_duration_us"
].reset_index(drop=True)


# ============================================================
# PRINT ORIGINAL SAMPLE SIZES
# ============================================================

print("=" * 70)
print("ORIGINAL SAMPLE SIZES")
print("=" * 70)

print(
    "Modified / Our Protocol : {:,}".format(
        len(modified_values)
    )
)

print(
    "Normal Ethereum         : {:,}".format(
        len(normal_values)
    )
)


# ============================================================
# MAKE SAMPLE SIZE EQUAL
# ============================================================

N_EQUAL = min(
    len(modified_values),
    len(normal_values),
)

print()
print(
    "Equal N used for comparison: {:,}".format(
        N_EQUAL
    )
)


# Random sampling with reproducible seed
modified_values = modified_values.sample(
    n=N_EQUAL,
    random_state=42,
).reset_index(drop=True)

normal_values = normal_values.sample(
    n=N_EQUAL,
    random_state=42,
).reset_index(drop=True)


# ============================================================
# SORT FOR VISUALIZATION
#
# Sorting shows execution-time distribution clearly.
# Transaction #1 is the lowest-duration transaction.
# ============================================================

modified_plot = np.sort(
    modified_values.to_numpy()
)

normal_plot = np.sort(
    normal_values.to_numpy()
)

transaction_number = np.arange(
    1,
    N_EQUAL + 1
)


# ============================================================
# STATISTICS
# ============================================================

print()
print("=" * 70)
print("MODIFIED / OUR PROTOCOL")
print("=" * 70)

print(
    "N       : {:,}".format(
        len(modified_values)
    )
)

print(
    "Mean    : {:.3f} us".format(
        modified_values.mean()
    )
)

print(
    "Median  : {:.3f} us".format(
        modified_values.median()
    )
)

print(
    "P95     : {:.3f} us".format(
        modified_values.quantile(0.95)
    )
)

print(
    "Maximum : {:.3f} us".format(
        modified_values.max()
    )
)


print()
print("=" * 70)
print("NORMAL ETHEREUM")
print("=" * 70)

print(
    "N       : {:,}".format(
        len(normal_values)
    )
)

print(
    "Mean    : {:.3f} us".format(
        normal_values.mean()
    )
)

print(
    "Median  : {:.3f} us".format(
        normal_values.median()
    )
)

print(
    "P95     : {:.3f} us".format(
        normal_values.quantile(0.95)
    )
)

print(
    "Maximum : {:.3f} us".format(
        normal_values.max()
    )
)


# ============================================================
# PLOT
# ============================================================

fig, ax = plt.subplots(
    figsize=(13, 8)
)


# Modified / Our Protocol
ax.scatter(
    transaction_number,
    modified_plot,
    s=16,
    alpha=0.7,
    label="Our Protocol",
)


# Normal Ethereum
ax.scatter(
    transaction_number,
    normal_plot,
    s=16,
    alpha=0.7,
    label="Normal Ethereum",
)


# ============================================================
# AXIS LABELS
# ============================================================

ax.set_xlabel(
    "Transaction Number",
    fontsize=AXIS_LABEL_FONT_SIZE,
)

ax.set_ylabel(
    "Execution Duration (µs)",
    fontsize=AXIS_LABEL_FONT_SIZE,
)

ax.tick_params(
    axis="both",
    labelsize=TICK_FONT_SIZE,
)


# ============================================================
# GRID
# ============================================================

ax.grid(
    True,
    linestyle="--",
    alpha=0.4,
)


# ============================================================
# LEGEND
# ============================================================

ax.legend(
    fontsize=LEGEND_FONT_SIZE,
    loc="upper left",
)


# ============================================================
# SAVE
# ============================================================

fig.tight_layout()

fig.savefig(
    OUTPUT_FILE,
    dpi=300,
    bbox_inches="tight",
)

print()
print("=" * 70)
print("Plot saved as:")
print(OUTPUT_FILE)
print("=" * 70)

plt.show()

plt.close(fig)