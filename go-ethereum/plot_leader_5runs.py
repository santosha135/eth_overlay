import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import t

# ============================================================
# CONFIGURATION
# ============================================================

NUM_RUNS = 5

# BUCKETS = [5, 10, 15]
BUCKETS = [6, 3, 2]

COLUMN = "duration_ns_per_call"


# ============================================================
# STORAGE
# ============================================================

all_results = []

bucket_means = []
bucket_stds = []
bucket_sems = []
bucket_ci95 = []


# ============================================================
# READ EACH INDEPENDENT RUN
# ============================================================

print("=" * 80)
print("LEADER SELECTION - INDEPENDENT RUN ANALYSIS")
print("=" * 80)

for bucket in BUCKETS:

    run_means = []

    print()
    print(f"{bucket} BUCKETS")
    print("-" * 60)

    for run in range(1, NUM_RUNS + 1):

        run_dir = Path(f"run_{run:02d}")

        filename = run_dir / (
            f"leader_selection_{bucket}_buckets.csv"
        )

        if not filename.exists():
            raise FileNotFoundError(
                f"File not found: {filename}"
            )

        df = pd.read_csv(filename)

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

        # ----------------------------------------------------
        # ONE MEAN FOR THIS ENTIRE INDEPENDENT RUN
        # ----------------------------------------------------

        run_mean = values.mean()

        run_means.append(run_mean)

        all_results.append({
            "Buckets": bucket,
            "Run": run,
            "N_Batches": len(values),
            "Run_Mean_ns_per_call": run_mean,
        })

        print(
            f"Run {run}: "
            f"{run_mean:.6f} ns/call "
            f"(N batches = {len(values):,})"
        )


    # ========================================================
    # STATISTICS ACROSS THE 5 INDEPENDENT RUN MEANS
    # ========================================================

    run_means = np.array(run_means)

    n = len(run_means)

    mean = np.mean(run_means)

    std = np.std(
        run_means,
        ddof=1
    )

    sem = std / np.sqrt(n)

    # Student's t critical value
    # Better than 1.96 when N is only 5
    t_critical = t.ppf(
        0.975,
        df=n - 1
    )

    ci = t_critical * sem

    lower = mean - ci
    upper = mean + ci

    bucket_means.append(mean)
    bucket_stds.append(std)
    bucket_sems.append(sem)
    bucket_ci95.append(ci)

    print()
    print(f"Mean of 5 runs : {mean:.6f} ns/call")
    print(f"Run-to-run STD : {std:.6f} ns/call")
    print(f"SEM            : {sem:.6f} ns/call")
    print(f"t critical     : {t_critical:.4f}")
    print(f"95% CI error   : ±{ci:.6f} ns/call")
    print(
        f"95% CI         : "
        f"[{lower:.6f}, {upper:.6f}] ns/call"
    )


# ============================================================
# SAVE INDIVIDUAL RUN RESULTS
# ============================================================

runs_df = pd.DataFrame(all_results)

runs_df.to_csv(
    "leader_selection_5runs_individual.csv",
    index=False
)


# ============================================================
# FINAL SUMMARY
# ============================================================

bucket_means = np.array(bucket_means)
bucket_stds = np.array(bucket_stds)
bucket_sems = np.array(bucket_sems)
bucket_ci95 = np.array(bucket_ci95)


summary = pd.DataFrame({

    "Buckets": BUCKETS,

    "Independent_Runs": NUM_RUNS,

    "Mean_ns_per_call":
        bucket_means,

    "Run_STD_ns_per_call":
        bucket_stds,

    "SEM_ns_per_call":
        bucket_sems,

    "CI95_Error_ns":
        bucket_ci95,

    "CI95_Lower_ns":
        bucket_means - bucket_ci95,

    "CI95_Upper_ns":
        bucket_means + bucket_ci95,
})


print()
print("=" * 80)
print("FINAL RESULTS - MEAN ± 95% CI ACROSS 5 RUNS")
print("=" * 80)

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.6f}"
    )
)


summary.to_csv(
    "leader_selection_5runs_summary.csv",
    index=False
)


# ============================================================
# PLOT
# ============================================================

fig, ax = plt.subplots(
    figsize=(8, 5.5)
)

x = np.arange(
    len(BUCKETS)
)


bars = ax.bar(

    x,

    bucket_means,

    width=0.60,

    # 95% CI across independent runs
    yerr=bucket_ci95,

    capsize=7,

    edgecolor="black",

    linewidth=1.1,

    error_kw={
        "elinewidth": 1.5,
        "capthick": 1.5
    }
)


# ============================================================
# X AXIS
# ============================================================

ax.set_xticks(x)

ax.set_xticklabels(
    [
        f"{b} Nodes"
        for b in BUCKETS
    ],
    fontsize=11
)

ax.set_xlabel(
    "Number of Nodes",
    fontsize=12
)


# ============================================================
# Y AXIS
# ============================================================

ax.set_ylabel(
    "Average Leader Selection Time (ns/call)",
    fontsize=12
)


# ============================================================
# TITLE
# ============================================================

# ax.set_title(
#     "Leader Selection Time (Mean ± 95% CI, 5 Independent Runs)",
#     fontsize=13
# )


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
# VALUE LABELS
# ============================================================

max_height = np.max(
    bucket_means + bucket_ci95
)

offset = max_height * 0.025


for bar, mean, error in zip(
    bars,
    bucket_means,
    bucket_ci95
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
# SAVE
# ============================================================

plt.savefig(
    "leader_selection_5runs_95CI.png",
    dpi=300,
    bbox_inches="tight"
)

plt.savefig(
    "leader_selection_5runs_95CI.pdf",
    bbox_inches="tight"
)


plt.show()
