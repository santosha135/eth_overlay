import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# FILES
# ============================================================

FILES = {
    "5 Buckets":  "rotation_duration_summary_5_bucket.xlsx",
    "10 Buckets": "rotation_duration_summary_10_bucket.xlsx",
    "15 Buckets": "rotation_duration_summary_15_bucket.xlsx",
    "30 Buckets": "rotation_duration_summary_30_bucket.xlsx",
}

COLUMN = "average_rotation_duration_ns"


# ============================================================
# READ EACH BUCKET CONFIGURATION
# ============================================================

labels = []
means_ns = []
stds_ns = []
sems_ns = []
runs = []

print("=" * 75)
print("BUCKET ROTATION DURATION")
print("=" * 75)

for label, filename in FILES.items():

    path = Path(filename)

    if not path.exists():
        print(f"\nERROR: {filename} not found")
        continue

    df = pd.read_excel(
        path,
        sheet_name="per_file_average",
        engine="openpyxl"
    )

    if COLUMN not in df.columns:
        print(f"\nERROR: '{COLUMN}' not found in {filename}")
        print("Available columns:")
        print(df.columns.tolist())
        continue

    values = pd.to_numeric(
        df[COLUMN],
        errors="coerce"
    ).dropna()

    if len(values) == 0:
        print(f"\nERROR: No valid values in {filename}")
        continue

    # ========================================================
    # STATISTICS
    # ========================================================

    mean_ns = values.mean()

    # Standard deviation
    std_ns = values.std(ddof=1)

    # Standard error
    sem_ns = std_ns / np.sqrt(len(values))

    labels.append(label)
    means_ns.append(mean_ns)
    stds_ns.append(std_ns)
    sems_ns.append(sem_ns)
    runs.append(len(values))

    print(f"\n{label}")
    print("-" * 45)
    print(f"Runs             : {len(values)}")
    print(f"Average          : {mean_ns:,.2f} ns")
    print(f"Standard Dev.    : {std_ns:,.2f} ns")
    print(f"Standard Error   : {sem_ns:,.2f} ns")

    print(f"Average          : {mean_ns / 1000:,.3f} µs")
    print(f"Standard Dev.    : {std_ns / 1000:,.3f} µs")
    print(f"Standard Error   : {sem_ns / 1000:,.3f} µs")


# ============================================================
# CONVERT NS -> MICROSECONDS
# ============================================================

means_us = np.array(means_ns) / 1000
stds_us = np.array(stds_ns) / 1000
sems_us = np.array(sems_ns) / 1000

x = np.arange(len(labels))


# ============================================================
# PLOT: MEAN ± SEM
# ============================================================

fig, ax = plt.subplots(figsize=(8, 5.5))

bars = ax.bar(
    x,
    means_us,

    # Error bar = standard error
    yerr=sems_us,

    capsize=7,
    width=0.60,
    edgecolor="black",
    linewidth=1.1,
    error_kw={
        "elinewidth": 1.5,
        "capthick": 1.5
    }
)


# ============================================================
# AXIS LABELS
# ============================================================

ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=11)

ax.set_xlabel(
    "Number of Buckets",
    fontsize=12
)

ax.set_ylabel(
    "Average Bucket Rotation Duration (µs)",
    fontsize=12
)

ax.set_title(
    "Bucket Rotation Duration",
    fontsize=14
)

ax.grid(
    axis="y",
    linestyle="--",
    alpha=0.3
)

ax.set_axisbelow(True)


# ============================================================
# VALUE LABELS
# ============================================================

if len(means_us) > 0:

    max_height = max(means_us + sems_us)

    offset = max_height * 0.025

    for bar, mean, sem in zip(
        bars,
        means_us,
        sems_us
    ):

        ax.text(
            bar.get_x() + bar.get_width() / 2,
            mean + sem + offset,
            f"{mean:.2f}",
            ha="center",
            va="bottom",
            fontsize=10
        )

    # Duration starts at zero
    ax.set_ylim(
        0,
        max_height * 1.15
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
    "bucket_rotation_duration_sem.png",
    dpi=300,
    bbox_inches="tight"
)

plt.savefig(
    "bucket_rotation_duration_sem.pdf",
    bbox_inches="tight"
)

plt.show()


# ============================================================
# FINAL TABLE
# ============================================================

summary = pd.DataFrame({
    "Configuration": labels,
    "Runs": runs,

    "Mean_ns": means_ns,
    "Std_ns": stds_ns,
    "SEM_ns": sems_ns,

    "Mean_us": means_us,
    "Std_us": stds_us,
    "SEM_us": sems_us,
})

print("\n")
print("=" * 75)
print("FINAL BUCKET ROTATION RESULTS")
print("=" * 75)

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:,.3f}"
    )
)

summary.to_excel(
    "bucket_rotation_comparison_sem.xlsx",
    index=False
)