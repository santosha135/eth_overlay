import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

FILES = {
    "5 Buckets":  "duration_ns_average_summary_bucket_5.xlsx",
    "10 Buckets": "duration_ns_average_summary_bucket_10.xlsx",
    "15 Buckets": "duration_ns_average_summary_bucket_15.xlsx",
    "30 Buckets": "duration_ns_average_summary_bucket_30.xlsx",
}

COLUMN = "average_duration_ns"


# ============================================================
# READ DATA
# ============================================================

labels = []
means_ns = []
stds_ns = []
sems_ns = []
counts = []

for label, filename in FILES.items():

    path = Path(filename)

    if not path.exists():
        print(f"ERROR: File not found: {filename}")
        continue

    df = pd.read_excel(
        path,
        sheet_name="per_file_average",
        engine="openpyxl"
    )

    if COLUMN not in df.columns:
        print(f"ERROR: '{COLUMN}' not found in {filename}")
        print("Available columns:", list(df.columns))
        continue

    values = pd.to_numeric(
        df[COLUMN],
        errors="coerce"
    ).dropna()

    if len(values) == 0:
        print(f"ERROR: No valid values in {filename}")
        continue

    # ========================================================
    # STATISTICS
    # ========================================================

    mean_ns = values.mean()
    std_ns = values.std(ddof=1)

    # Standard Error of the Mean
    sem_ns = std_ns / np.sqrt(len(values))

    labels.append(label)
    means_ns.append(mean_ns)
    stds_ns.append(std_ns)
    sems_ns.append(sem_ns)
    counts.append(len(values))

    print(f"\n{label}")
    print("-" * 40)
    print(f"Runs           : {len(values)}")
    print(f"Mean           : {mean_ns / 1000:.4f} µs")
    print(f"Std Dev        : {std_ns / 1000:.4f} µs")
    print(f"Standard Error : {sem_ns / 1000:.4f} µs")


# ============================================================
# CONVERT TO MICROSECONDS
# ============================================================

means_us = np.array(means_ns) / 1000
stds_us = np.array(stds_ns) / 1000
sems_us = np.array(sems_ns) / 1000

x = np.arange(len(labels))


# ============================================================
# BAR PLOT — MEAN ± SEM
# ============================================================

fig, ax = plt.subplots(figsize=(9, 6))

bars = ax.bar(
    x,
    means_us,
    width=0.60,

    # Error bars = standard error
    yerr=sems_us,

    capsize=6,
    edgecolor="black",
    linewidth=1.2,
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
    ["5", "10", "15", "30"],
    fontsize=12
)

ax.set_xlabel(
    "Number of Buckets",
    fontsize=13
)

ax.set_ylabel(
    "Average Leader Selection Duration (µs)",
    fontsize=13
)

ax.set_title(
    "Leader Selection Duration by Number of Buckets",
    fontsize=14
)

# Duration starts at zero
ax.set_ylim(bottom=0)

ax.grid(
    axis="y",
    linestyle="--",
    alpha=0.3
)

ax.set_axisbelow(True)


# ============================================================
# ADD MEAN VALUES ABOVE ERROR BARS
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
            fontsize=11
        )

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
# SAVE
# ============================================================

plt.savefig(
    "leader_selection_sem.png",
    dpi=300,
    bbox_inches="tight"
)

plt.savefig(
    "leader_selection_sem.pdf",
    bbox_inches="tight"
)

plt.show()


# ============================================================
# FINAL TABLE
# ============================================================

summary = pd.DataFrame({
    "Configuration": labels,
    "Runs": counts,

    "Mean_ns": means_ns,
    "Std_ns": stds_ns,
    "SEM_ns": sems_ns,

    "Mean_us": means_us,
    "Std_us": stds_us,
    "SEM_us": sems_us,
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

summary.to_excel(
    "leader_selection_comparison_sem.xlsx",
    index=False
)