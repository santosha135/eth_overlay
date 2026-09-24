import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import t

# ============================================================
# CONFIGURATION
# ============================================================

NUM_RUNS = 5

# Fixed architecture
NUM_BUCKETS = 5

# Scalability variable
NODES_PER_BUCKET = [
    2,
    3,
    6,
    10,
    20,
    30,
    50,
    100,
]

COLUMN = "duration_ns_per_call"


# ============================================================
# STORAGE
# ============================================================

all_results = []

config_means = []
config_stds = []
config_sems = []
config_ci95 = []


# ============================================================
# READ EACH INDEPENDENT RUN
# ============================================================

print("=" * 90)
print("LEADER SELECTION SCALABILITY - 5 FIXED BUCKETS")
print("=" * 90)

for nodes_per_bucket in NODES_PER_BUCKET:

    total_nodes = NUM_BUCKETS * nodes_per_bucket

    run_means = []

    print()
    print(
        f"{nodes_per_bucket} NODES/BUCKET | "
        f"{NUM_BUCKETS} BUCKETS | "
        f"{total_nodes} TOTAL NODES"
    )
    print("-" * 90)

    # ========================================================
    # READ FIVE INDEPENDENT RUNS
    # ========================================================

    for run in range(1, NUM_RUNS + 1):

        run_dir = Path(f"run_{run:02d}")

        filename = run_dir / (
            f"leader_selection_"
            f"{nodes_per_bucket}_nodes_per_bucket.csv"
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
        # VALIDATE CONFIGURATION
        # ----------------------------------------------------

        if "num_buckets" in df.columns:

            unique_buckets = (
                pd.to_numeric(
                    df["num_buckets"],
                    errors="coerce"
                )
                .dropna()
                .unique()
            )

            if (
                len(unique_buckets) != 1
                or unique_buckets[0] != NUM_BUCKETS
            ):
                raise ValueError(
                    f"Unexpected bucket configuration "
                    f"in {filename}: {unique_buckets}"
                )

        if "nodes_per_bucket" in df.columns:

            unique_nodes = (
                pd.to_numeric(
                    df["nodes_per_bucket"],
                    errors="coerce"
                )
                .dropna()
                .unique()
            )

            if (
                len(unique_nodes) != 1
                or unique_nodes[0] != nodes_per_bucket
            ):
                raise ValueError(
                    f"Unexpected nodes-per-bucket "
                    f"in {filename}: {unique_nodes}"
                )

        if "total_miners" in df.columns:

            unique_total = (
                pd.to_numeric(
                    df["total_miners"],
                    errors="coerce"
                )
                .dropna()
                .unique()
            )

            if (
                len(unique_total) != 1
                or unique_total[0] != total_nodes
            ):
                raise ValueError(
                    f"Unexpected total miners "
                    f"in {filename}: {unique_total}"
                )

        # ----------------------------------------------------
        # ONE MEAN FOR THIS INDEPENDENT RUN
        # ----------------------------------------------------

        run_mean = values.mean()

        run_means.append(run_mean)

        all_results.append({
            "Buckets": NUM_BUCKETS,
            "Nodes_Per_Bucket": nodes_per_bucket,
            "Total_Nodes": total_nodes,
            "Run": run,
            "N_Batches": len(values),
            "Run_Mean_ns_per_call": run_mean,
        })

        print(
            f"Run {run}: "
            f"{run_mean:.6f} ns/call "
            f"(N measurements = {len(values):,})"
        )

    # ========================================================
    # STATISTICS ACROSS FIVE INDEPENDENT RUN MEANS
    # ========================================================

    run_means = np.asarray(
        run_means,
        dtype=float
    )

    n = len(run_means)

    mean = np.mean(run_means)

    std = np.std(
        run_means,
        ddof=1
    )

    sem = std / np.sqrt(n)

    # Student's t because N = 5 independent runs
    t_critical = t.ppf(
        0.975,
        df=n - 1
    )

    ci = t_critical * sem

    lower = mean - ci
    upper = mean + ci

    config_means.append(mean)
    config_stds.append(std)
    config_sems.append(sem)
    config_ci95.append(ci)

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
# CONVERT TO NUMPY ARRAYS
# ============================================================

config_means = np.asarray(
    config_means,
    dtype=float
)

config_stds = np.asarray(
    config_stds,
    dtype=float
)

config_sems = np.asarray(
    config_sems,
    dtype=float
)

config_ci95 = np.asarray(
    config_ci95,
    dtype=float
)


# ============================================================
# SAVE INDIVIDUAL RUN RESULTS
# ============================================================

runs_df = pd.DataFrame(
    all_results
)

runs_df.to_csv(
    "leader_selection_scalability_5runs_individual.csv",
    index=False
)


# ============================================================
# FINAL SUMMARY
# ============================================================

total_nodes_values = [
    NUM_BUCKETS * n
    for n in NODES_PER_BUCKET
]

summary = pd.DataFrame({

    "Buckets":
        [NUM_BUCKETS] * len(NODES_PER_BUCKET),

    "Nodes_Per_Bucket":
        NODES_PER_BUCKET,

    "Total_Nodes":
        total_nodes_values,

    "Independent_Runs":
        [NUM_RUNS] * len(NODES_PER_BUCKET),

    "Mean_ns_per_call":
        config_means,

    "Run_STD_ns_per_call":
        config_stds,

    "SEM_ns_per_call":
        config_sems,

    "CI95_Error_ns":
        config_ci95,

    "CI95_Lower_ns":
        config_means - config_ci95,

    "CI95_Upper_ns":
        config_means + config_ci95,
})


print()
print("=" * 100)
print(
    "FINAL RESULTS - "
    "5 FIXED BUCKETS, MEAN ± 95% CI ACROSS 5 RUNS"
)
print("=" * 100)

print(
    summary.to_string(
        index=False,
        float_format=lambda value: f"{value:.6f}"
    )
)


summary.to_csv(
    "leader_selection_scalability_5runs_summary.csv",
    index=False
)


# ============================================================
# PLOT
# ============================================================

fig, ax = plt.subplots(
    figsize=(10, 6)
)

x = np.arange(
    len(NODES_PER_BUCKET)
)


bars = ax.bar(

    x,

    config_means,

    width=0.62,

    # 95% confidence interval across
    # the five independent run means
    yerr=config_ci95,

    capsize=6,

    edgecolor="black",

    linewidth=1.1,

    error_kw={
        "elinewidth": 1.5,
        "capthick": 1.5,
    }
)


# ============================================================
# X AXIS
# ============================================================

ax.set_xticks(x)

ax.set_xticklabels(
    [
        str(nodes)
        for nodes in NODES_PER_BUCKET
    ],
    fontsize=12
)

ax.set_xlabel(
    "Nodes per Bucket",
    fontsize=14
)


# ============================================================
# Y AXIS
# ============================================================

ax.set_ylabel(
    "Average Leader Selection Time (ns/call)",
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
# VALUE LABELS
# ============================================================

max_height = np.max(
    config_means + config_ci95
)

offset = max_height * 0.025


for bar, mean, error in zip(
    bars,
    config_means,
    config_ci95
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
    "leader_selection_scalability_5buckets_95CI.png",
    dpi=300,
    bbox_inches="tight"
)

plt.savefig(
    "leader_selection_scalability_5buckets_95CI.pdf",
    bbox_inches="tight"
)


plt.show()
