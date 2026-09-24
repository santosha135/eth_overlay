import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

FILES = {
    5: "leader_selection_5_buckets.csv",
    10: "leader_selection_10_buckets.csv",
    15: "leader_selection_15_buckets.csv",
    30: "leader_selection_30_buckets.csv",
}

COLUMN = "duration_ns_per_call"

# ============================================================
# STORAGE
# ============================================================

buckets = []
means = []
medians = []
stds = []
sems = []
ci95 = []
p95s = []
counts = []

# ============================================================
# READ FILES
# ============================================================

print("=" * 80)
print("LEADER SELECTION - BATCH BENCHMARK")
print("=" * 80)

for bucket, filename in FILES.items():

    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {filename}"
        )

    df = pd.read_csv(path)

    if COLUMN not in df.columns:
        raise ValueError(
            f"'{COLUMN}' not found in {filename}\n"
            f"Available columns: {df.columns.tolist()}"
        )

    values = pd.to_numeric(
        df[COLUMN],
        errors="coerce"
    ).dropna()

    if len(values) == 0:
        raise ValueError(
            f"No valid values in {filename}"
        )

    # ========================================================
    # STATISTICS
    # ========================================================

    n = len(values)

    mean = values.mean()
    median = values.median()

    std = values.std(ddof=1)

    sem = std / np.sqrt(n)

    # Approximate 95% CI
    error = 1.96 * sem

    p95 = values.quantile(0.95)

    lower = mean - error
    upper = mean + error

    # ========================================================
    # STORE
    # ========================================================

    buckets.append(bucket)
    counts.append(n)

    means.append(mean)
    medians.append(median)

    stds.append(std)
    sems.append(sem)

    ci95.append(error)

    p95s.append(p95)

    # ========================================================
    # PRINT
    # ========================================================

    print()
    print(f"{bucket} Buckets")
    print("-" * 50)

    print(f"N batches      : {n:,}")
    print(f"Mean           : {mean:.6f} ns/call")
    print(f"Median         : {median:.6f} ns/call")
    print(f"Std Dev        : {std:.6f} ns/call")
    print(f"SEM            : {sem:.6f} ns/call")
    print(f"P95            : {p95:.6f} ns/call")

    print(
        f"95% CI         : "
        f"[{lower:.6f}, {upper:.6f}] ns/call"
    )

# ============================================================
# ARRAYS
# ============================================================

means = np.array(means)
medians = np.array(medians)

stds = np.array(stds)
sems = np.array(sems)

ci95 = np.array(ci95)
p95s = np.array(p95s)

# ============================================================
# SUMMARY
# ============================================================

summary = pd.DataFrame({

    "Buckets": buckets,

    "N_Batches": counts,

    "Mean_ns_per_call": means,

    "Median_ns_per_call": medians,

    "Std_ns_per_call": stds,

    "SEM_ns_per_call": sems,

    "CI95_Error_ns": ci95,

    "CI95_Lower_ns": means - ci95,

    "CI95_Upper_ns": means + ci95,

    "P95_ns_per_call": p95s,
})

print()
print("=" * 80)
print("FINAL RESULTS")
print("=" * 80)

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.6f}"
    )
)

summary.to_csv(
    "leader_selection_batch_summary.csv",
    index=False
)

# ============================================================
# PLOT
# ============================================================

fig, ax = plt.subplots(
    figsize=(8, 5.5)
)

x = np.arange(
    len(buckets)
)

bars = ax.bar(
    x,
    means,

    width=0.60,

    # 95% confidence interval
    yerr=ci95,

    capsize=7,

    edgecolor="black",

    linewidth=1.1,

    error_kw={
        "elinewidth": 1.5,
        "capthick": 1.5,
    }
)

# ============================================================
# LABELS
# ============================================================

ax.set_xticks(x)

ax.set_xticklabels(
    [
        f"{bucket} Buckets"
        for bucket in buckets
    ],
    fontsize=11,
)

ax.set_xlabel(
    "Number of Buckets",
    fontsize=12,
)

ax.set_ylabel(
    "Average Leader Selection Time (ns/call)",
    fontsize=12,
)

ax.set_title(
    "Leader Selection Time",
    fontsize=14,
)

# ============================================================
# GRID
# ============================================================

ax.grid(
    axis="y",
    linestyle="--",
    alpha=0.3,
)

ax.set_axisbelow(True)

# ============================================================
# VALUE LABELS
# ============================================================

max_height = np.max(
    means + ci95
)

offset = max_height * 0.03

for bar, mean, error in zip(
    bars,
    means,
    ci95,
):

    ax.text(

        bar.get_x()
        + bar.get_width() / 2,

        mean
        + error
        + offset,

        f"{mean:.2f}",

        ha="center",

        va="bottom",

        fontsize=10,
    )

# ============================================================
# Y LIMIT
# ============================================================

ax.set_ylim(
    0,
    max_height * 1.18,
)

# ============================================================
# STYLE
# ============================================================

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()

# ============================================================
# SAVE
# ============================================================

plt.savefig(
    "leader_selection_batch_95CI.png",
    dpi=300,
    bbox_inches="tight",
)

plt.savefig(
    "leader_selection_batch_95CI.pdf",
    bbox_inches="tight",
)

plt.show()
