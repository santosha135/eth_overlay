import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import t


# ============================================================
# CONFIGURATION
# ============================================================

NUM_RUNS = 5

BUCKETS = [
    5,
    10,
    15,
    30,
    50,
    100,
]

MINERS_PER_BUCKET = 6

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
# READ DATA
# ============================================================

print("=" * 90)
print("BUCKET ROTATION SCALABILITY - 6 MINERS PER BUCKET")
print("=" * 90)


for bucket in BUCKETS:

    total_miners = bucket * MINERS_PER_BUCKET

    run_means = []

    print()
    print(
        f"{bucket} BUCKETS | "
        f"{MINERS_PER_BUCKET} MINERS/BUCKET | "
        f"{total_miners} TOTAL MINERS"
    )

    print("-" * 90)

    # ========================================================
    # FIVE INDEPENDENT RUNS
    # ========================================================

    for run in range(1, NUM_RUNS + 1):

        run_dir = Path(
            f"run_{run:02d}"
        )

        filename = (
            run_dir /
            f"bucket_rotation_{bucket}_buckets.csv"
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

        df = pd.read_csv(
            filename
        )

        # ----------------------------------------------------
        # CHECK TIMING COLUMN
        # ----------------------------------------------------

        if COLUMN not in df.columns:

            raise ValueError(
                f"Column '{COLUMN}' not found "
                f"in {filename}\n"
                f"Available columns: "
                f"{df.columns.tolist()}"
            )

        # ====================================================
        # VALIDATE CONFIGURATION
        # ====================================================

        if "num_buckets" in df.columns:

            actual_buckets = (
                pd.to_numeric(
                    df["num_buckets"],
                    errors="coerce"
                )
                .dropna()
                .unique()
            )

            if (
                len(actual_buckets) != 1
                or actual_buckets[0] != bucket
            ):

                raise ValueError(
                    f"Unexpected bucket count "
                    f"in {filename}: "
                    f"{actual_buckets}"
                )

        if "miners_per_bucket" in df.columns:

            actual_miners_per_bucket = (
                pd.to_numeric(
                    df["miners_per_bucket"],
                    errors="coerce"
                )
                .dropna()
                .unique()
            )

            if (
                len(actual_miners_per_bucket) != 1
                or
                actual_miners_per_bucket[0]
                != MINERS_PER_BUCKET
            ):

                raise ValueError(
                    f"Unexpected miners/bucket "
                    f"in {filename}: "
                    f"{actual_miners_per_bucket}"
                )

        if "total_miners" in df.columns:

            actual_total = (
                pd.to_numeric(
                    df["total_miners"],
                    errors="coerce"
                )
                .dropna()
                .unique()
            )

            if (
                len(actual_total) != 1
                or actual_total[0] != total_miners
            ):

                raise ValueError(
                    f"Unexpected total miners "
                    f"in {filename}: "
                    f"{actual_total}"
                )

        # ====================================================
        # GET VALID TIMING VALUES
        # ====================================================

        values = pd.to_numeric(
            df[COLUMN],
            errors="coerce"
        ).dropna()

        if len(values) == 0:

            raise ValueError(
                f"No valid timing values "
                f"in {filename}"
            )

        # ====================================================
        # ONE MEAN PER INDEPENDENT RUN
        # ====================================================

        run_mean = values.mean()

        run_means.append(
            run_mean
        )

        all_results.append({

            "Buckets":
                bucket,

            "Miners_Per_Bucket":
                MINERS_PER_BUCKET,

            "Total_Miners":
                total_miners,

            "Run":
                run,

            "N_Measurements":
                len(values),

            "Run_Mean_ns_per_call":
                run_mean,
        })

        print(
            f"Run {run}: "
            f"{run_mean:.6f} ns/call "
            f"(N = {len(values):,})"
        )

    # ========================================================
    # STATISTICS ACROSS FIVE INDEPENDENT RUNS
    # ========================================================

    run_means = np.asarray(
        run_means,
        dtype=float
    )

    n = len(
        run_means
    )

    mean = np.mean(
        run_means
    )

    std = np.std(
        run_means,
        ddof=1
    )

    sem = (
        std /
        np.sqrt(n)
    )

    # Student's t critical value.
    t_critical = t.ppf(
        0.975,
        df=n - 1
    )

    ci = (
        t_critical *
        sem
    )

    lower = (
        mean - ci
    )

    upper = (
        mean + ci
    )

    bucket_means.append(
        mean
    )

    bucket_stds.append(
        std
    )

    bucket_sems.append(
        sem
    )

    bucket_ci95.append(
        ci
    )

    print()
    print(
        f"Mean of 5 runs : "
        f"{mean:.6f} ns/call"
    )

    print(
        f"Run-to-run STD : "
        f"{std:.6f} ns/call"
    )

    print(
        f"SEM            : "
        f"{sem:.6f} ns/call"
    )

    print(
        f"95% CI error   : "
        f"±{ci:.6f} ns/call"
    )

    print(
        f"95% CI         : "
        f"[{lower:.6f}, "
        f"{upper:.6f}] ns/call"
    )


# ============================================================
# CONVERT TO ARRAYS
# ============================================================

bucket_means = np.asarray(
    bucket_means
)

bucket_stds = np.asarray(
    bucket_stds
)

bucket_sems = np.asarray(
    bucket_sems
)

bucket_ci95 = np.asarray(
    bucket_ci95
)


# ============================================================
# SAVE INDIVIDUAL RUN RESULTS
# ============================================================

runs_df = pd.DataFrame(
    all_results
)

runs_df.to_csv(
    "bucket_rotation_scalability_5runs_individual.csv",
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

total_miners_values = [
    bucket * MINERS_PER_BUCKET
    for bucket in BUCKETS
]


summary = pd.DataFrame({

    "Buckets":
        BUCKETS,

    "Miners_Per_Bucket":
        [MINERS_PER_BUCKET] * len(BUCKETS),

    "Total_Miners":
        total_miners_values,

    "Independent_Runs":
        [NUM_RUNS] * len(BUCKETS),

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
print("=" * 100)

print(
    "FINAL BUCKET ROTATION SCALABILITY RESULTS "
    "- MEAN ± 95% CI"
)

print("=" * 100)

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.6f}"
    )
)


summary.to_csv(
    "bucket_rotation_scalability_5runs_summary.csv",
    index=False
)


# ============================================================
# PLOT
# ============================================================

fig, ax = plt.subplots(
    figsize=(10, 6)
)

x = np.arange(
    len(BUCKETS)
)


bars = ax.bar(

    x,

    bucket_means,

    width=0.62,

    # 95% CI across five independent runs
    yerr=bucket_ci95,

    capsize=6,

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

ax.set_xticks(
    x
)

ax.set_xticklabels(
    [
        str(bucket)
        for bucket in BUCKETS
    ],
    fontsize=12
)

ax.set_xlabel(
    "Number of Buckets",
    fontsize=14
)


# ============================================================
# Y AXIS
# ============================================================

ax.set_ylabel(
    "Average Bucket Rotation Time (ns/call)",
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

ax.set_axisbelow(
    True
)


# ============================================================
# VALUE ABOVE EACH BAR
# ============================================================

max_height = np.max(
    bucket_means +
    bucket_ci95
)

offset = (
    max_height *
    0.025
)


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

ax.spines[
    "top"
].set_visible(False)

ax.spines[
    "right"
].set_visible(False)


plt.tight_layout()


# ============================================================
# SAVE
# ============================================================

plt.savefig(
    "bucket_rotation_scalability_95CI.png",
    dpi=300,
    bbox_inches="tight"
)

plt.savefig(
    "bucket_rotation_scalability_95CI.pdf",
    bbox_inches="tight"
)


plt.show()
