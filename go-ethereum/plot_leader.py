import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

FILES = {
    5:  "leader_selection_5_buckets.csv",
    10: "leader_selection_10_buckets.csv",
    15: "leader_selection_15_buckets.csv",
    30: "leader_selection_30_buckets.csv",
}

COLUMN = "duration_ns"

buckets = []
means = []
stds = []
sems = []
ci95 = []
counts = []


# ============================================================
# READ DATA
# ============================================================

print("=" * 75)
print("LEADER SELECTION TIMING")
print("=" * 75)

for bucket, filename in FILES.items():

    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {filename}")

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
        raise ValueError(f"No valid timing values in {filename}")

    # ========================================================
    # STATISTICS
    # ========================================================

    n = len(values)

    mean = values.mean()

    std = values.std(ddof=1)

    sem = std / np.sqrt(n)

    # 95% confidence interval half-width
    error = 1.96 * sem

    lower = mean - error
    upper = mean + error

    buckets.append(bucket)
    means.append(mean)
    stds.append(std)
    sems.append(sem)
    ci95.append(error)
    counts.append(n)

    print(f"\n{bucket} Buckets")
    print("-" * 50)
    print(f"N              : {n:,}")
    print(f"Mean           : {mean:.4f} ns")
    print(f"Std Dev        : {std:.4f} ns")
    print(f"SEM            : {sem:.6f} ns")
    print(f"95% CI Error   : ±{error:.6f} ns")
    print(f"95% CI         : [{lower:.4f}, {upper:.4f}] ns")


# ============================================================
# CONVERT TO NUMPY ARRAYS
# ============================================================

means = np.array(means)
stds = np.array(stds)
sems = np.array(sems)
ci95 = np.array(ci95)


# ============================================================
# SUMMARY
# ============================================================

summary = pd.DataFrame({
    "Buckets": buckets,
    "N": counts,
    "Mean_ns": means,
    "Std_ns": stds,
    "SEM_ns": sems,
    "CI95_Error_ns": ci95,
    "CI95_Lower_ns": means - ci95,
    "CI95_Upper_ns": means + ci95,
})

print("\n")
print("=" * 75)
print("FINAL LEADER SELECTION RESULTS")
print("=" * 75)

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:,.4f}"
    )
)

summary.to_csv(
    "leader_selection_summary_95CI.csv",
    index=False
)


# ============================================================
# PLOT
# ============================================================

fig, ax = plt.subplots(figsize=(8, 5.5))

x = np.arange(len(buckets))

bars = ax.bar(
    x,
    means,
    width=0.60,

    # Error bar = 95% confidence interval
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
    [f"{b} Buckets" for b in buckets],
    fontsize=11
)

ax.set_xlabel(
    "Number of Buckets",
    fontsize=12
)

ax.set_ylabel(
    "Average Leader Selection Time (ns)",
    fontsize=12
)

ax.set_title(
    "Leader Selection Time",
    fontsize=14
)

ax.grid(
    axis="y",
    linestyle="--",
    alpha=0.3
)

ax.set_axisbelow(True)


# ============================================================
# MEAN VALUE ABOVE EACH BAR
# ============================================================

max_height = np.max(means + ci95)

offset = max_height * 0.03

for bar, mean, error in zip(
    bars,
    means,
    ci95
):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        mean + error + offset,
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
# SAVE
# ============================================================

plt.savefig(
    "leader_selection_95CI.png",
    dpi=300,
    bbox_inches="tight"
)

plt.savefig(
    "leader_selection_95CI.pdf",
    bbox_inches="tight"
)

plt.show()
