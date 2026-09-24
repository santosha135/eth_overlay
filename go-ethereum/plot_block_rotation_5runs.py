import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import t

# ============================================================
# CONFIGURATION
# ============================================================

NUM_RUNS = 5

BUCKETS = [5, 10, 15, 30]

COLUMN = "duration_ns_per_call"


# ============================================================
# STORAGE
# ============================================================

all_results = []

bucket_means = []
bucket_medians = []
bucket_stds = []
bucket_sems = []
bucket_ci95 = []


# ============================================================
# READ EACH INDEPENDENT RUN
# ============================================================

print("=" * 80)
print("BUCKET ROTATION - 5 INDEPENDENT RUN ANALYSIS")
print("=" * 80)


for bucket in BUCKETS:

    run_means = []

    print()
    print(f"{bucket} BUCKETS")
    print("-" * 60)

    # ========================================================
    # READ RUN 01 ... RUN 05
    # ========================================================

    for run in range(1, NUM_RUNS + 1):

        run_dir = Path(f"run_{run:02d}")

        filename = (
            run_dir
            / f"bucket_rotation_{bucket}_buckets.csv"
        )

        # ----------------------------------------------------
        # CHECK FILE
        # ----------------------------------------------------

        if not filename.exists():

            raise FileNotFoundError(
                f"File not found: {filename}"
            )

        # ----------------------------------------------------
        # READ CSV
        # ----------------------------------------------------

        df = pd.read_csv(filename)

        # ----------------------------------------------------
        # CHECK COLUMN
        # ----------------------------------------------------

        if COLUMN not in df.columns:

            raise ValueError(
                f"Column '{COLUMN}' not found in {filename}\n"
                f"Available columns: {df.columns.tolist()}"
            )

        # ----------------------------------------------------
        # GET VALID VALUES
        # ----------------------------------------------------

        values = pd.to_numeric(
            df[COLUMN],
            errors="coerce"
        ).dropna()

        if len(values) == 0:

            raise ValueError(
                f"No valid timing values in {filename}"
            )

        # ====================================================
        # ONE MEAN FOR THIS INDEPENDENT RUN
        # ====================================================

        run_mean = values.mean()

        run_means.append(run_mean)

        # Save individual run result

        all_results.append({

            "Buckets": bucket,

            "Run": run,

            "N_Batches": len(values),

            "Run_Mean_ns_per_call": run_mean,

            "Run_Median_ns_per_call": values.median(),

            "Run_STD_ns_per_call": values.std(ddof=1),

            "Run_P95_ns_per_call": values.quantile(0.95),
        })

        print(
            f"Run {run}: "
            f"{run_mean:.6f} ns/call "
            f"(N batches = {len(values):,})"
        )


    # ========================================================
    # CONVERT 5 RUN MEANS TO NUMPY
    # ========================================================

    run_means = np.array(
        run_means,
        dtype=float
    )


    # ========================================================
    # STATISTICS ACROSS 5 INDEPENDENT RUNS
    # ========================================================

    n = len(run_means)

    mean = np.mean(run_means)

    median = np.median(run_means)

    # Run-to-run standard deviation
    std = np.std(
        run_means,
        ddof=1
    )

    # Standard error across independent runs
    sem = std / np.sqrt(n)


    # ========================================================
    # 95% CONFIDENCE INTERVAL
    #
    # Use Student's t because N = 5 is small.
    #
    # df = 5 - 1 = 4
    #
    # t(0.975, 4) ≈ 2.776
    # ========================================================

    t_critical = t.ppf(
        0.975,
        df=n - 1
    )

    ci = t_critical * sem

    lower = mean - ci
    upper = mean + ci


    # ========================================================
    # STORE FINAL RESULTS
    # ========================================================

    bucket_means.append(mean)

    bucket_medians.append(median)

    bucket_stds.append(std)

    bucket_sems.append(sem)

    bucket_ci95.append(ci)


    # ========================================================
    # PRINT BUCKET SUMMARY
    # ========================================================

    print()
    print("Summary across independent runs")
    print("-" * 60)

    print(f"Independent runs : {n}")

    print(
        f"Mean of runs     : "
        f"{mean:.6f} ns/call"
    )

    print(
        f"Median of runs   : "
        f"{median:.6f} ns/call"
    )

    print(
        f"Run-to-run STD   : "
        f"{std:.6f} ns/call"
    )

    print(
        f"SEM              : "
        f"{sem:.6f} ns/call"
    )

    print(
        f"t critical       : "
        f"{t_critical:.6f}"
    )

    print(
        f"95% CI Error     : "
        f"±{ci:.6f} ns/call"
    )

    print(
        f"95% CI           : "
        f"[{lower:.6f}, {upper:.6f}] ns/call"
    )


# ============================================================
# SAVE INDIVIDUAL RUN RESULTS
# ============================================================

runs_df = pd.DataFrame(
    all_results
)

runs_df.to_csv(
    "bucket_rotation_5runs_individual.csv",
    index=False
)


# ============================================================
# CONVERT FINAL VALUES TO NUMPY
# ============================================================

bucket_means = np.array(
    bucket_means
)

bucket_medians = np.array(
    bucket_medians
)

bucket_stds = np.array(
    bucket_stds
)

bucket_sems = np.array(
    bucket_sems
)

bucket_ci95 = np.array(
    bucket_ci95
)


# ============================================================
# FINAL SUMMARY DATAFRAME
# ============================================================

summary = pd.DataFrame({

    "Buckets":
        BUCKETS,

    "Independent_Runs":
        NUM_RUNS,

    "Mean_ns_per_call":
        bucket_means,

    "Median_Run_Mean_ns_per_call":
        bucket_medians,

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


# ============================================================
# PRINT FINAL RESULTS
# ============================================================

print()
print("=" * 80)

print(
    "FINAL BUCKET ROTATION RESULTS "
    "- MEAN ± 95% CI ACROSS 5 RUNS"
)

print("=" * 80)


print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.6f}"
    )
)


# ============================================================
# SAVE SUMMARY
# ============================================================

summary.to_csv(
    "bucket_rotation_5runs_summary.csv",
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


# ============================================================
# BAR PLOT
# ============================================================

bars = ax.bar(

    x,

    bucket_means,

    width=0.60,

    # --------------------------------------------------------
    # ERROR BAR = 95% CI ACROSS 5 INDEPENDENT RUNS
    # --------------------------------------------------------

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
        f"{b} Buckets"
        for b in BUCKETS
    ],
    fontsize=11
)


ax.set_xlabel(
    "Number of Buckets",
    fontsize=12
)


# ============================================================
# Y AXIS
# ============================================================

ax.set_ylabel(
    "Average Bucket Rotation Time (ns/call)",
    fontsize=12
)


# ============================================================
# TITLE
# ============================================================

ax.set_title(
    "Bucket Rotation Time "
    "(Mean ± 95% CI, 5 Independent Runs)",
    fontsize=13
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
# VALUE ABOVE EACH BAR
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
# SAVE FIGURES
# ============================================================

plt.savefig(
    "bucket_rotation_5runs_95CI.png",
    dpi=300,
    bbox_inches="tight"
)


plt.savefig(
    "bucket_rotation_5runs_95CI.pdf",
    bbox_inches="tight"
)


plt.show()
