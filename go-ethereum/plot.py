import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

BUCKETS = [5, 10, 15, 30]

ROTATION_FILES = {
    5:  "bucket_rotation_5_buckets.csv",
    10: "bucket_rotation_10_buckets.csv",
    15: "bucket_rotation_15_buckets.csv",
    30: "bucket_rotation_30_buckets.csv",
}

LEADER_FILES = {
    5:  "leader_selection_5_buckets.csv",
    10: "leader_selection_10_buckets.csv",
    15: "leader_selection_15_buckets.csv",
    30: "leader_selection_30_buckets.csv",
}

COLUMN = "duration_ns"


# ============================================================
# FUNCTION TO READ FILES AND CALCULATE STATISTICS
# ============================================================

def calculate_statistics(files):

    means = []
    stds = []
    medians = []
    p95s = []
    counts = []

    for bucket in BUCKETS:

        filename = files[bucket]
        path = Path(filename)

        if not path.exists():
            raise FileNotFoundError(
                f"Could not find: {filename}"
            )

        print(f"\nReading: {filename}")

        df = pd.read_csv(path)

        if COLUMN not in df.columns:
            raise ValueError(
                f"{COLUMN} not found in {filename}\n"
                f"Available columns: {list(df.columns)}"
            )

        # Make sure duration is numeric
        values = pd.to_numeric(
            df[COLUMN],
            errors="coerce"
        ).dropna()

        # ----------------------------------------------------
        # Statistics
        # ----------------------------------------------------

        count = len(values)
        mean = values.mean()
        std = values.std(ddof=1)
        median = values.median()
        p95 = values.quantile(0.95)

        counts.append(count)
        means.append(mean)
        stds.append(std)
        medians.append(median)
        p95s.append(p95)

        print(f"Buckets : {bucket}")
        print(f"N       : {count:,}")
        print(f"Mean    : {mean:.4f} ns")
        print(f"Median  : {median:.4f} ns")
        print(f"Std Dev : {std:.4f} ns")
        print(f"P95     : {p95:.4f} ns")

    return {
        "mean": np.array(means),
        "std": np.array(stds),
        "median": np.array(medians),
        "p95": np.array(p95s),
        "count": np.array(counts),
    }


# ============================================================
# READ BUCKET ROTATION RESULTS
# ============================================================

print("\n")
print("=" * 60)
print("BUCKET ROTATION")
print("=" * 60)

rotation_stats = calculate_statistics(
    ROTATION_FILES
)


# ============================================================
# READ LEADER SELECTION RESULTS
# ============================================================

print("\n")
print("=" * 60)
print("LEADER SELECTION")
print("=" * 60)

leader_stats = calculate_statistics(
    LEADER_FILES
)


# ============================================================
# PRINT SUMMARY TABLE
# ============================================================

summary = pd.DataFrame({
    "Buckets": BUCKETS,

    "Rotation_N":
        rotation_stats["count"],

    "Rotation_Mean_ns":
        rotation_stats["mean"],

    "Rotation_Std_ns":
        rotation_stats["std"],

    "Rotation_Median_ns":
        rotation_stats["median"],

    "Rotation_P95_ns":
        rotation_stats["p95"],

    "Leader_N":
        leader_stats["count"],

    "Leader_Mean_ns":
        leader_stats["mean"],

    "Leader_Std_ns":
        leader_stats["std"],

    "Leader_Median_ns":
        leader_stats["median"],

    "Leader_P95_ns":
        leader_stats["p95"],
})

print("\n")
print("=" * 60)
print("SUMMARY")
print("=" * 60)

print(summary.to_string(index=False))


# Save summary
summary.to_csv(
    "scheduler_timing_summary.csv",
    index=False
)


# ============================================================
# PLOT 1: BUCKET ROTATION
# Mean +/- Standard Deviation
# ============================================================

plt.figure(figsize=(8, 5))

plt.bar(
    [str(x) for x in BUCKETS],
    rotation_stats["mean"],
    yerr=rotation_stats["std"],
    capsize=6
)

plt.xlabel(
    "Number of Buckets",
    fontsize=12
)

plt.ylabel(
    "Bucket Rotation Time (ns)",
    fontsize=12
)

plt.title(
    "Bucket Rotation Time",
    fontsize=14
)

plt.grid(
    axis="y",
    linestyle="--",
    alpha=0.4
)

plt.tight_layout()

plt.savefig(
    "bucket_rotation_timing.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()


# ============================================================
# PLOT 2: LEADER SELECTION
# Mean +/- Standard Deviation
# ============================================================

plt.figure(figsize=(8, 5))

plt.bar(
    [str(x) for x in BUCKETS],
    leader_stats["mean"],
    yerr=leader_stats["std"],
    capsize=6
)

plt.xlabel(
    "Number of Buckets",
    fontsize=12
)

plt.ylabel(
    "Leader Selection Time (ns)",
    fontsize=12
)

plt.title(
    "Leader Selection Time",
    fontsize=14
)

plt.grid(
    axis="y",
    linestyle="--",
    alpha=0.4
)

plt.tight_layout()

plt.savefig(
    "leader_selection_timing.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()
