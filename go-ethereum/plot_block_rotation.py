import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

FILES = {
    5:  "bucket_rotation_5_buckets.csv",
    10: "bucket_rotation_10_buckets.csv",
    15: "bucket_rotation_15_buckets.csv",
    30: "bucket_rotation_30_buckets.csv",
}

# IMPORTANT:
# New Go batch benchmark stores average time per operation here.
COLUMN = "duration_ns_per_call"

buckets = []
means = []
medians = []
stds = []
sems = []
ci95 = []
p95s = []
counts = []


# ============================================================
# READ DATA
# ============================================================

print("=" * 75)
print("BUCKET ROTATION TIMING - BATCH BENCHMARK")
print("=" * 75)

for bucket, filename in FILES.items():

    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {filename}"
        )

    df = pd.read_csv(path)

    if COLUMN not in df.columns:
        raise ValueError(
            f"Column '{COLUMN}' not found in {filename}\n"
            f"Available columns: {df.columns.tolist()}"
        )

    values = pd.to_numeric(
        df[COLUMN],
        errors="coerce"
    ).dropna()

    if len(values) == 0:
        raise ValueError(
            f"No valid timing values in {filename}"
        )

    # ========================================================
    # STATISTICS
    # ========================================================

    n = len(values)

    mean = values.mean()

    median = values.median()

    std = values.std(ddof=1)

    sem = std / np.sqrt(n)

    # Approximate 95% confidence interval half-width
    error = 1.96 * sem

    lower = mean - error
    upper = mean + error

    p95 = values.quantile(0.95)

    # ========================================================
    # STORE RESULTS
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
    # PRINT RESULTS
    # ========================================================

    print(f"\n{bucket} Buckets")
    print("-" * 50)

    print(f"N batches      : {n:,}")
    print(f"Mean           : {mean:.6f} ns/call")
    print(f"Median         : {median:.6f} ns/call")
    print(f"Std Dev        : {std:.6f} ns/call")
    print(f"SEM            : {sem:.6f} ns/call")
    print(f"P95            : {p95:.6f} ns/call")

    print(
        f"95% CI Error   : ±{error:.6f} ns/call"
    )

    print(
        f"95% CI         : "
        f"[{lower:.6f}, {upper:.6f}] ns/call"
    )


# ============================================================
# CONVERT TO NUMPY ARRAYS
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


print("\n")
print("=" * 75)
print("FINAL BUCKET ROTATION RESULTS")
print("=" * 75)

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:,.6f}"
    )
)


# ============================================================
# SAVE SUMMARY
# ============================================================

summary.to_csv(
    "bucket_rotation_batch_summary_95CI.csv",
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

    # ========================================================
    # ERROR BAR = 95% CONFIDENCE INTERVAL
    # ========================================================

    yerr=ci95,

    capsize=7,

    edgecolor="black",

    linewidth=1.1,

    error_kw={
        "elinewidth": 1.5,
        "capthick": 1.5
    }
)


# ============================================================
# AXES
# ============================================================

ax.set_xticks(x)

ax.set_xticklabels(
    [
        f"{b} Buckets"
        for b in buckets
    ],
    fontsize=11
)


ax.set_xlabel(
    "Number of Buckets",
    fontsize=12
)


ax.set_ylabel(
    "Average Bucket Rotation Time (ns/call)",
    fontsize=12
)


ax.set_title(
    "Bucket Rotation Time",
    fontsize=14
)


# ============================================================
# GRID
# ============================================================

ax.grid(
    axis="y",
    linestyle="--",
    alpha=0.3
)

ax.set_axisbelow(True)


# ============================================================
# MEAN VALUE ABOVE EACH BAR
# ============================================================

max_height = np.max(
    means + ci95
)

offset = max_height * 0.03


for bar, mean, error in zip(
    bars,
    means,
    ci95
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

        fontsize=10
    )


# ============================================================
# Y LIMIT
# ============================================================

ax.set_ylim(
    0,
    max_height * 1.18
)


# ============================================================
# CLEAN STYLE
# ============================================================

ax.spines["top"].set_visible(False)

ax.spines["right"].set_visible(False)


plt.tight_layout()


# ============================================================
# SAVE FIGURES
# ============================================================

plt.savefig(
    "bucket_rotation_batch_95CI.png",
    dpi=300,
    bbox_inches="tight"
)


plt.savefig(
    "bucket_rotation_batch_95CI.pdf",
    bbox_inches="tight"
)


plt.show()