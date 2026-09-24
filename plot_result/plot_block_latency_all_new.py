#!/usr/bin/env python3

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TITLE_FONT_SIZE = 22
AXIS_LABEL_FONT_SIZE = 20
TICK_FONT_SIZE = 17
LEGEND_FONT_SIZE = 15#!/usr/bin/env python3

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TITLE_FONT_SIZE = 22
AXIS_LABEL_FONT_SIZE = 20
TICK_FONT_SIZE = 17
LEGEND_FONT_SIZE = 15

# ============================================================
# Configuration
# ============================================================

# Each experiment contains 10 Excel files (v1 ... v10).
# Change only the filename templates below if your actual names differ.
NORMAL_FILES = [
    Path("replay_phased_fixed_metrics_replay_tx_v{}_sm_normal.xlsx".format(i))
    for i in range(1, 11)
]

MODIFIED_FILES = {
    "Modified - 5 Buckets": [
        Path("replay_phased_fixed_metrics_replay_tx_v{}_modified_5.xlsx".format(i))
        for i in range(1, 11)
    ],
    "Modified - 10 Buckets": [
        Path("replay_phased_fixed_metrics_replay_tx_v{}_modified_10.xlsx".format(i))
        for i in range(1, 11)
    ],
    "Modified - 15 Buckets": [
        Path("replay_phased_fixed_metrics_replay_tx_v{}_modified_15.xlsx".format(i))
        for i in range(1, 11)
    ],
    "Modified - 30 Buckets": [
        Path("replay_phased_fixed_metrics_replay_tx_v{}_modified_30.xlsx".format(i))
        for i in range(1, 11)
    ],
}

SHEET_NAME = "per_transaction"
LATENCY_COLUMN = "block_timestamp_latency_sec"


# ============================================================
# Latency filtering
# ============================================================

MAX_LATENCY_SECONDS = 1000.0
MIN_LATENCY_SECONDS = 0.0


# ============================================================
# Per-transaction plot configuration
# ============================================================

# 1 = every transaction, 10 = every 10th transaction, etc.
PLOT_EVERY_N = 1

LIMIT_TRANSACTION_Y_AXIS_TO_PERCENTILE = False
TRANSACTION_Y_AXIS_PERCENTILE = 0.99
TRANSACTION_Y_AXIS_PADDING = 1.10


# ============================================================
# CDF plot configuration
# ============================================================

CDF_AS_PERCENTAGE = True

LIMIT_CDF_X_AXIS_TO_PERCENTILE = True
CDF_X_AXIS_PERCENTILE = 0.99
CDF_X_AXIS_PADDING = 1.10

CDF_MINIMUM_X_AXIS_SECONDS = 30.0
CDF_FIXED_X_AXIS_MAX_SECONDS = None

SHOW_CDF_PERCENTILE_LINES = False


# ============================================================
# CDF threshold table
# ============================================================

CDF_LATENCY_THRESHOLDS_SECONDS = [
    1,
    2,
    5,
    10,
    15,
    20,
    25,
    30,
    45,
    60,
    120,
    300,
    600,
    1000,
]


# ============================================================
# Output files
# ============================================================

TRANSACTION_PLOT_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency.png"
)

CDF_PLOT_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency_cdf.png"
)

CDF_FULL_RANGE_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency_cdf_full_range.png"
)

CDF_TABLE_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency_cdf_table.csv"
)

STATISTICS_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency_statistics.csv"
)

COMPARISON_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency_comparison.csv"
)


# ============================================================
# Data loading and filtering
# ============================================================

def load_latency(
    file_path: Path,
    case_name: str,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Load valid successful transactions from one Excel file.

    Transactions with negative latency or latency greater than
    MAX_LATENCY_SECONDS are excluded.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            "Input file does not exist:\n  {}".format(
                file_path.resolve()
            )
        )

    try:
        df = pd.read_excel(
            file_path,
            sheet_name=SHEET_NAME,
            engine="openpyxl",
        )
    except ValueError as exc:
        raise ValueError(
            "Could not find sheet '{}' in {}".format(
                SHEET_NAME,
                file_path.name,
            )
        ) from exc

    required_columns = {
        "status",
        "tx_hash",
        "block_number",
        LATENCY_COLUMN,
    }

    missing_columns = required_columns.difference(df.columns)

    if missing_columns:
        raise ValueError(
            "{} is missing required columns: {}\n"
            "Available columns: {}".format(
                file_path.name,
                sorted(missing_columns),
                list(df.columns),
            )
        )

    total_rows = len(df)

    df["status"] = (
        df["status"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["block_number"] = pd.to_numeric(
        df["block_number"],
        errors="coerce",
    )

    df[LATENCY_COLUMN] = pd.to_numeric(
        df[LATENCY_COLUMN],
        errors="coerce",
    )

    valid_base_mask = (
        (df["status"] == "SUCCESS")
        & df["tx_hash"].notna()
        & df["block_number"].notna()
        & df[LATENCY_COLUMN].notna()
        & np.isfinite(df[LATENCY_COLUMN])
    )

    valid_base_df = df[valid_base_mask].copy()

    successful_valid_rows = len(valid_base_df)

    negative_latency_count = int(
        (
            valid_base_df[LATENCY_COLUMN]
            < MIN_LATENCY_SECONDS
        ).sum()
    )

    above_max_latency_count = int(
        (
            valid_base_df[LATENCY_COLUMN]
            > MAX_LATENCY_SECONDS
        ).sum()
    )

    df = valid_base_df[
        (
            valid_base_df[LATENCY_COLUMN]
            >= MIN_LATENCY_SECONDS
        )
        & (
            valid_base_df[LATENCY_COLUMN]
            <= MAX_LATENCY_SECONDS
        )
    ].copy()

    included_rows = len(df)

    invalid_or_unsuccessful_rows = (
        total_rows - successful_valid_rows
    )

    filter_information = {
        "total_rows": int(total_rows),
        "invalid_or_unsuccessful_rows": int(
            invalid_or_unsuccessful_rows
        ),
        "negative_latency_rows": int(
            negative_latency_count
        ),
        "above_max_latency_rows": int(
            above_max_latency_count
        ),
        "included_rows": int(included_rows),
    }

    if df.empty:
        raise ValueError(
            "No valid transactions remained in {} after applying "
            "the latency range {:.3f} to {:.3f} seconds.".format(
                file_path.name,
                MIN_LATENCY_SECONDS,
                MAX_LATENCY_SECONDS,
            )
        )

    # Sort using the best available transaction ordering column.
    if "send_epoch_ms" in df.columns:
        df["send_epoch_ms"] = pd.to_numeric(
            df["send_epoch_ms"],
            errors="coerce",
        )
        df = df.sort_values(
            by="send_epoch_ms",
            kind="stable",
            na_position="last",
        )

    elif "send_epoch" in df.columns:
        df["send_epoch"] = pd.to_numeric(
            df["send_epoch"],
            errors="coerce",
        )
        df = df.sort_values(
            by="send_epoch",
            kind="stable",
            na_position="last",
        )

    elif "send_time_utc" in df.columns:
        df["send_time_utc"] = pd.to_datetime(
            df["send_time_utc"],
            errors="coerce",
            utc=True,
        )
        df = df.sort_values(
            by="send_time_utc",
            kind="stable",
            na_position="last",
        )

    elif "tx_index" in df.columns:
        df["tx_index"] = pd.to_numeric(
            df["tx_index"],
            errors="coerce",
        )
        df = df.sort_values(
            by="tx_index",
            kind="stable",
            na_position="last",
        )

    df = df.reset_index(drop=True)

    df["transaction_number"] = range(
        1,
        len(df) + 1,
    )

    df["case"] = case_name

    return df, filter_information



def load_latency_files(
    file_paths: List[Path],
    case_name: str,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Load and concatenate all v1...v10 files for one experiment.

    Every row from every file is treated as one observation.  The function
    intentionally does not deduplicate tx_hash values because separate runs
    are independent benchmark observations.
    """

    if not file_paths:
        raise ValueError("No input files configured for {}".format(case_name))

    frames = []
    combined_information = {
        "total_rows": 0,
        "invalid_or_unsuccessful_rows": 0,
        "negative_latency_rows": 0,
        "above_max_latency_rows": 0,
        "included_rows": 0,
    }

    print("\nLoading {}".format(case_name))
    print("=" * 75)

    for run_number, file_path in enumerate(file_paths, start=1):
        run_case_name = "{} v{}".format(case_name, run_number)
        df, information = load_latency(file_path, run_case_name)

        # Keep the run number so you can identify the source later if needed.
        df["run_number"] = run_number
        df["source_file"] = file_path.name
        frames.append(df)

        for key in combined_information:
            combined_information[key] += int(information[key])

        print(
            "  v{:>2}: {:>6,} included -> {}".format(
                run_number,
                information["included_rows"],
                file_path.name,
            )
        )

    combined_df = pd.concat(frames, ignore_index=True)

    # Preserve v1, v2, ... v10 order and create one continuous x-axis.
    combined_df["transaction_number"] = range(1, len(combined_df) + 1)
    combined_df["case"] = case_name

    print(
        "  TOTAL: {:,} transactions included across {} files".format(
            len(combined_df),
            len(file_paths),
        )
    )

    return combined_df, combined_information

def print_filter_information(
    case_name: str,
    file_path: Path,
    information: Dict[str, int],
) -> None:
    """Print filtering information for one experiment."""

    print("\n{} filtering".format(case_name))
    print("=" * 75)

    print(
        "Input file                         : {}".format(
            file_path.name
        )
    )
    print(
        "Total rows                         : {:,}".format(
            information["total_rows"]
        )
    )
    print(
        "Invalid/failed/incomplete rows      : {:,}".format(
            information["invalid_or_unsuccessful_rows"]
        )
    )
    print(
        "Negative latency rows excluded      : {:,}".format(
            information["negative_latency_rows"]
        )
    )
    print(
        "Latency > {:.0f} seconds excluded     : {:,}".format(
            MAX_LATENCY_SECONDS,
            information["above_max_latency_rows"],
        )
    )
    print(
        "Transactions included in analysis   : {:,}".format(
            information["included_rows"]
        )
    )


# ============================================================
# Statistics
# ============================================================

def calculate_statistics(
    case_name: str,
    df: pd.DataFrame,
    filter_information: Dict[str, int],
) -> Dict[str, object]:
    """Calculate latency statistics for one experiment."""

    latency = df[LATENCY_COLUMN]

    return {
        "case": case_name,
        "transactions_included": int(len(latency)),
        "transactions_above_max_excluded": int(
            filter_information["above_max_latency_rows"]
        ),
        "maximum_allowed_latency_seconds": float(
            MAX_LATENCY_SECONDS
        ),
        "average_seconds": float(latency.mean()),
        "median_seconds": float(latency.median()),
        "minimum_seconds": float(latency.min()),
        "maximum_seconds": float(latency.max()),
        "standard_deviation_seconds": float(
            latency.std()
        ),
        "p50_seconds": float(
            latency.quantile(0.50)
        ),
        "p90_seconds": float(
            latency.quantile(0.90)
        ),
        "p95_seconds": float(
            latency.quantile(0.95)
        ),
        "p99_seconds": float(
            latency.quantile(0.99)
        ),
    }


def print_statistics(
    statistics: Dict[str, object],
) -> None:
    """Print latency statistics for one experiment."""

    print("\n{}".format(statistics["case"]))
    print("=" * 75)

    print(
        "Transactions : {:,}".format(
            statistics["transactions_included"]
        )
    )
    print(
        "Average      : {:.3f} seconds".format(
            statistics["average_seconds"]
        )
    )
    print(
        "Median       : {:.3f} seconds".format(
            statistics["median_seconds"]
        )
    )
    print(
        "Minimum      : {:.3f} seconds".format(
            statistics["minimum_seconds"]
        )
    )
    print(
        "Maximum      : {:.3f} seconds".format(
            statistics["maximum_seconds"]
        )
    )
    print(
        "Std. dev.    : {:.3f} seconds".format(
            statistics["standard_deviation_seconds"]
        )
    )
    print(
        "P50          : {:.3f} seconds".format(
            statistics["p50_seconds"]
        )
    )
    print(
        "P90          : {:.3f} seconds".format(
            statistics["p90_seconds"]
        )
    )
    print(
        "P95          : {:.3f} seconds".format(
            statistics["p95_seconds"]
        )
    )
    print(
        "P99          : {:.3f} seconds".format(
            statistics["p99_seconds"]
        )
    )


def create_comparison_table(
    normal: pd.DataFrame,
    modified_cases: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Create a table comparing every modified case against Normal.
    """

    normal_latency = normal[LATENCY_COLUMN]

    normal_metrics = {
        "average_seconds": float(normal_latency.mean()),
        "median_seconds": float(normal_latency.median()),
        "p90_seconds": float(
            normal_latency.quantile(0.90)
        ),
        "p95_seconds": float(
            normal_latency.quantile(0.95)
        ),
        "p99_seconds": float(
            normal_latency.quantile(0.99)
        ),
    }

    rows = []

    for case_name, df in modified_cases.items():
        latency = df[LATENCY_COLUMN]

        modified_metrics = {
            "average_seconds": float(latency.mean()),
            "median_seconds": float(latency.median()),
            "p90_seconds": float(
                latency.quantile(0.90)
            ),
            "p95_seconds": float(
                latency.quantile(0.95)
            ),
            "p99_seconds": float(
                latency.quantile(0.99)
            ),
        }

        row = {
            "case": case_name,
        }

        for metric_name, normal_value in normal_metrics.items():
            modified_value = modified_metrics[metric_name]

            difference = normal_value - modified_value

            if normal_value > 0:
                improvement_percentage = (
                    difference / normal_value
                ) * 100.0
            else:
                improvement_percentage = float("nan")

            row[
                "normal_{}".format(metric_name)
            ] = normal_value

            row[
                "modified_{}".format(metric_name)
            ] = modified_value

            row[
                "difference_{}".format(metric_name)
            ] = difference

            row[
                "improvement_percent_{}".format(metric_name)
            ] = improvement_percentage

        rows.append(row)

    return pd.DataFrame(rows)


def print_comparison_table(
    normal: pd.DataFrame,
    modified_cases: Dict[str, pd.DataFrame],
) -> None:
    """Print Normal versus all modified experiments."""

    metric_definitions = [
        ("Average", "mean"),
        ("Median", "median"),
        ("P90", 0.90),
        ("P95", 0.95),
        ("P99", 0.99),
    ]

    case_names = ["Normal"] + list(modified_cases.keys())

    column_width = 24

    print("\nLatency comparison")
    print("=" * (18 + column_width * len(case_names)))

    header = "{:<14}".format("Metric")

    for case_name in case_names:
        header += "{:>{width}}".format(
            case_name,
            width=column_width,
        )

    print(header)
    print("-" * (18 + column_width * len(case_names)))

    for metric_name, operation in metric_definitions:
        row = "{:<14}".format(metric_name)

        if operation == "mean":
            normal_value = normal[LATENCY_COLUMN].mean()
        elif operation == "median":
            normal_value = normal[LATENCY_COLUMN].median()
        else:
            normal_value = normal[LATENCY_COLUMN].quantile(
                operation
            )

        row += "{:>{width}.3f}".format(
            normal_value,
            width=column_width,
        )

        for _, df in modified_cases.items():
            if operation == "mean":
                value = df[LATENCY_COLUMN].mean()
            elif operation == "median":
                value = df[LATENCY_COLUMN].median()
            else:
                value = df[LATENCY_COLUMN].quantile(
                    operation
                )

            row += "{:>{width}.3f}".format(
                value,
                width=column_width,
            )

        print(row)


# ============================================================
# Axis calculations
# ============================================================

def calculate_combined_percentile_limit(
    all_cases: Dict[str, pd.DataFrame],
    percentile: float,
    padding: float,
) -> Optional[float]:
    """
    Calculate an axis limit using all experiment distributions.
    """

    if percentile <= 0 or percentile > 1:
        raise ValueError(
            "Percentile must be greater than 0 and "
            "less than or equal to 1."
        )

    if padding <= 0:
        raise ValueError(
            "Axis padding must be greater than zero."
        )

    combined_latency = pd.concat(
        [
            df[LATENCY_COLUMN]
            for df in all_cases.values()
        ],
        ignore_index=True,
    )

    percentile_value = combined_latency.quantile(
        percentile
    )

    if (
        pd.isna(percentile_value)
        or not np.isfinite(percentile_value)
        or percentile_value <= 0
    ):
        return None

    return float(percentile_value * padding)


def determine_cdf_x_axis_limit(
    all_cases: Dict[str, pd.DataFrame],
) -> Optional[float]:
    """Determine a readable CDF x-axis upper limit."""

    if CDF_FIXED_X_AXIS_MAX_SECONDS is not None:
        if CDF_FIXED_X_AXIS_MAX_SECONDS <= 0:
            raise ValueError(
                "CDF_FIXED_X_AXIS_MAX_SECONDS must "
                "be greater than zero."
            )

        return min(
            float(CDF_FIXED_X_AXIS_MAX_SECONDS),
            MAX_LATENCY_SECONDS,
        )

    if not LIMIT_CDF_X_AXIS_TO_PERCENTILE:
        return None

    limit = calculate_combined_percentile_limit(
        all_cases=all_cases,
        percentile=CDF_X_AXIS_PERCENTILE,
        padding=CDF_X_AXIS_PADDING,
    )

    if limit is None:
        return None

    if CDF_MINIMUM_X_AXIS_SECONDS is not None:
        if CDF_MINIMUM_X_AXIS_SECONDS <= 0:
            raise ValueError(
                "CDF_MINIMUM_X_AXIS_SECONDS must "
                "be greater than zero."
            )

        limit = max(
            limit,
            float(CDF_MINIMUM_X_AXIS_SECONDS),
        )

    return min(limit, MAX_LATENCY_SECONDS)


# ============================================================
# Per-transaction latency plot
# ============================================================

# def plot_transaction_latency(
#     all_cases: Dict[str, pd.DataFrame],
# ) -> None:
#     """Plot latency versus transaction sending order."""

#     if PLOT_EVERY_N < 1:
#         raise ValueError(
#             "PLOT_EVERY_N must be at least 1."
#         )

#     y_axis_limit = None

#     if LIMIT_TRANSACTION_Y_AXIS_TO_PERCENTILE:
#         y_axis_limit = calculate_combined_percentile_limit(
#             all_cases=all_cases,
#             percentile=(
#                 TRANSACTION_Y_AXIS_PERCENTILE
#             ),
#             padding=TRANSACTION_Y_AXIS_PADDING,
#         )

#         if y_axis_limit is not None:
#             y_axis_limit = min(
#                 y_axis_limit,
#                 MAX_LATENCY_SECONDS,
#             )

#     figure, axis = plt.subplots(
#         figsize=(16, 8)
#     )

#     for case_name, df in all_cases.items():
#         plot_df = df.iloc[
#             ::PLOT_EVERY_N
#         ].copy()

#         average_latency = df[
#             LATENCY_COLUMN
#         ].mean()

#         axis.plot(
#             plot_df["transaction_number"],
#             plot_df[LATENCY_COLUMN],
#             marker="o",
#             markersize=2.0,
#             linewidth=1.0,
#             label=(
#                 "{} - average {:.2f} s"
#             ).format(
#                 case_name,
#                 average_latency,
#             ),
#         )

#     axis.set_ylim(bottom=0)

#     if y_axis_limit is not None:
#         axis.set_ylim(
#             bottom=0,
#             top=y_axis_limit,
#         )

#     axis.set_title(
#         "Per-Transaction Block Inclusion Latency "
#         "(Latency <= {:.0f} Seconds)".format(
#             MAX_LATENCY_SECONDS
#         ),
#         fontsize=16,
#     )

#     axis.set_xlabel(
#         "Transaction Number After Filtering",
#         fontsize=12,
#     )

#     axis.set_ylabel(
#         "Block Timestamp Latency (seconds)",
#         fontsize=12,
#     )

#     axis.grid(
#         visible=True,
#         linestyle="--",
#         alpha=0.5,
#     )

#     axis.legend(
#         loc="best",
#         fontsize=9,
#     )

#     figure.tight_layout()

#     figure.savefig(
#         TRANSACTION_PLOT_OUTPUT_FILE,
#         dpi=300,
#         bbox_inches="tight",
#     )

#     plt.show()
#     plt.close(figure)

#     print(
#         "\nPer-transaction graph saved as:\n  {}".format(
#             Path(
#                 TRANSACTION_PLOT_OUTPUT_FILE
#             ).resolve()
#         )
#     )


# # ============================================================
# # CDF calculations
# # ============================================================

# def calculate_cdf(
#     df: pd.DataFrame,
# ) -> Tuple[np.ndarray, np.ndarray]:
#     """Calculate the empirical cumulative distribution."""

#     sorted_latency = np.sort(
#         df[LATENCY_COLUMN]
#         .dropna()
#         .to_numpy(dtype=float)
#     )

#     if len(sorted_latency) == 0:
#         raise ValueError(
#             "Cannot calculate CDF because the "
#             "latency data is empty."
#         )

#     cumulative_probability = (
#         np.arange(
#             1,
#             len(sorted_latency) + 1,
#             dtype=float,
#         )
#         / float(len(sorted_latency))
#     )

#     return (
#         sorted_latency,
#         cumulative_probability,
#     )
# ============================================================
# CDF calculations
# ============================================================

def calculate_cdf(
    df: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate the empirical cumulative distribution."""

    sorted_latency = np.sort(
        df[LATENCY_COLUMN]
        .dropna()
        .to_numpy(dtype=float)
    )

    if len(sorted_latency) == 0:
        raise ValueError(
            "Cannot calculate CDF because the latency data is empty."
        )

    cumulative_probability = (
        np.arange(
            1,
            len(sorted_latency) + 1,
            dtype=float,
        )
        / float(len(sorted_latency))
    )

    return (
        sorted_latency,
        cumulative_probability,
    )


def plot_transaction_latency(
    all_cases: Dict[str, pd.DataFrame],
) -> None:
    """Plot latency versus transaction sending order."""

    if PLOT_EVERY_N < 1:
        raise ValueError(
            "PLOT_EVERY_N must be at least 1."
        )

    y_axis_limit = None

    if LIMIT_TRANSACTION_Y_AXIS_TO_PERCENTILE:
        y_axis_limit = calculate_combined_percentile_limit(
            all_cases=all_cases,
            percentile=TRANSACTION_Y_AXIS_PERCENTILE,
            padding=TRANSACTION_Y_AXIS_PADDING,
        )

        if y_axis_limit is not None:
            y_axis_limit = min(
                y_axis_limit,
                MAX_LATENCY_SECONDS,
            )

    # ----------------------------------------------------------
    # Create figure
    # ----------------------------------------------------------

    figure, axis = plt.subplots(
        figsize=(16, 8)
    )

    # ----------------------------------------------------------
    # Plot each experiment
    # ----------------------------------------------------------

    for case_name, df in all_cases.items():

        plot_df = df.iloc[
            ::PLOT_EVERY_N
        ].copy()

        average_latency = df[
            LATENCY_COLUMN
        ].mean()

        axis.plot(
            plot_df["transaction_number"],
            plot_df[LATENCY_COLUMN],
            marker="o",
            markersize=2.5,
            linewidth=1.5,
            label=(
                "{} - average {:.2f} s"
            ).format(
                case_name,
                average_latency,
            ),
        )

    # ----------------------------------------------------------
    # Y-axis
    # ----------------------------------------------------------

    axis.set_ylim(bottom=0)

    if y_axis_limit is not None:
        axis.set_ylim(
            bottom=0,
            top=y_axis_limit,
        )

    # ----------------------------------------------------------
    # Title
    # ----------------------------------------------------------

    axis.set_title(
        "Per-Transaction Block Inclusion Latency "
        "(Latency <= {:.0f} Seconds)".format(
            MAX_LATENCY_SECONDS
        ),
        fontsize=TITLE_FONT_SIZE,
        pad=15,
    )

    # ----------------------------------------------------------
    # Axis labels
    # ----------------------------------------------------------

    axis.set_xlabel(
        "Transaction Number After Filtering",
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    axis.set_ylabel(
        "Block Timestamp Latency (seconds)",
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    # ----------------------------------------------------------
    # Tick-label sizes
    # ----------------------------------------------------------

    axis.tick_params(
        axis="both",
        which="major",
        labelsize=TICK_FONT_SIZE,
    )

    # ----------------------------------------------------------
    # Grid
    # ----------------------------------------------------------

    axis.grid(
        visible=True,
        linestyle="--",
        alpha=0.5,
    )

    # ----------------------------------------------------------
    # Legend
    # ----------------------------------------------------------

    axis.legend(
        loc="best",
        fontsize=LEGEND_FONT_SIZE,
        frameon=True,
    )

    # ----------------------------------------------------------
    # Layout and save
    # ----------------------------------------------------------

    figure.tight_layout()

    figure.savefig(
        TRANSACTION_PLOT_OUTPUT_FILE,
        dpi=300,
        bbox_inches="tight",
    )

    plt.show()
    plt.close(figure)

    print(
        "\nPer-transaction graph saved as:\n  {}".format(
            Path(
                TRANSACTION_PLOT_OUTPUT_FILE
            ).resolve()
        )
    )

def percentage_within_threshold(
    latency_values: pd.Series,
    threshold_seconds: float,
) -> float:
    """Return percentage of transactions within a threshold."""

    if len(latency_values) == 0:
        return float("nan")

    count_within = int(
        (
            latency_values <= threshold_seconds
        ).sum()
    )

    return (
        float(count_within)
        / float(len(latency_values))
    ) * 100.0


# ============================================================
# CDF threshold table
# ============================================================

def create_cdf_threshold_table(
    all_cases: Dict[str, pd.DataFrame],
    thresholds: List[float],
) -> pd.DataFrame:
    """
    Create one threshold table for all experiments.
    """

    rows = []

    for threshold in thresholds:
        if threshold < 0:
            raise ValueError(
                "CDF thresholds cannot be negative."
            )

        if threshold > MAX_LATENCY_SECONDS:
            continue

        row = {
            "latency_threshold_seconds": float(
                threshold
            )
        }

        for case_name, df in all_cases.items():
            safe_name = (
                case_name
                .lower()
                .replace(" ", "_")
                .replace("-", "")
            )

            row[
                "{}_within_threshold_percent".format(
                    safe_name
                )
            ] = percentage_within_threshold(
                df[LATENCY_COLUMN],
                threshold,
            )

        rows.append(row)

    return pd.DataFrame(rows)


def print_cdf_threshold_table(
    table: pd.DataFrame,
) -> None:
    """Print the threshold comparison table."""

    print("\nCDF threshold comparison")
    print("=" * 140)

    print(
        table.to_string(
            index=False,
            float_format=lambda value: "{:.2f}".format(
                value
            ),
        )
    )


# ============================================================
# Readable percentile-limited CDF graph
# ============================================================

# def plot_latency_cdf(
#     all_cases: Dict[str, pd.DataFrame],
# ) -> None:
#     """Plot a readable empirical CDF for all experiments."""

#     cdf_x_axis_limit = determine_cdf_x_axis_limit(
#         all_cases
#     )

#     if CDF_AS_PERCENTAGE:
#         y_axis_label = (
#             "Cumulative Percentage of Transactions"
#         )
#         y_axis_maximum = 100.0
#     else:
#         y_axis_label = "Cumulative Probability"
#         y_axis_maximum = 1.0

#     figure, axis = plt.subplots(
#         figsize=(13, 8)
#     )

#     for case_name, df in all_cases.items():
#         latency_values, cdf_values = calculate_cdf(
#             df
#         )

#         if CDF_AS_PERCENTAGE:
#             plot_y = cdf_values * 100.0
#         else:
#             plot_y = cdf_values

#         median_value = float(
#             df[LATENCY_COLUMN].median()
#         )

#         p95_value = float(
#             df[LATENCY_COLUMN].quantile(0.95)
#         )

#         axis.plot(
#             latency_values,
#             plot_y,
#             linewidth=2.0,
#             drawstyle="steps-post",
#             label=(
#                 "{} (median {:.2f} s, P95 {:.2f} s)"
#             ).format(
#                 case_name,
#                 median_value,
#                 p95_value,
#             ),
#         )

#         if SHOW_CDF_PERCENTILE_LINES:
#             axis.axvline(
#                 x=median_value,
#                 linestyle=":",
#                 linewidth=0.8,
#                 alpha=0.5,
#             )

#             axis.axvline(
#                 x=p95_value,
#                 linestyle="--",
#                 linewidth=0.8,
#                 alpha=0.5,
#             )

#     axis.set_xlim(left=0)

#     if cdf_x_axis_limit is not None:
#         axis.set_xlim(
#             left=0,
#             right=cdf_x_axis_limit,
#         )

#         print("\nCDF visible range")
#         print("=" * 75)

#         print(
#             "Visible x-axis upper limit: "
#             "{:.3f} seconds".format(
#                 cdf_x_axis_limit
#             )
#         )

#         for case_name, df in all_cases.items():
#             values_beyond_visible = int(
#                 (
#                     df[LATENCY_COLUMN]
#                     > cdf_x_axis_limit
#                 ).sum()
#             )

#             print(
#                 "{:<35}: {:,}".format(
#                     case_name,
#                     values_beyond_visible,
#                 )
#             )

#     axis.set_ylim(
#         bottom=0,
#         top=y_axis_maximum,
#     )

#     axis.set_title(
#         "CDF of Block Inclusion Latency "
#         "(Latency <= {:.0f} Seconds)".format(
#             MAX_LATENCY_SECONDS
#         ),
#         fontsize=16,
#     )

#     axis.set_xlabel(
#         "Block Timestamp Latency (seconds)",
#         fontsize=12,
#     )

#     axis.set_ylabel(
#         y_axis_label,
#         fontsize=12,
#     )

#     axis.grid(
#         visible=True,
#         linestyle="--",
#         alpha=0.5,
#     )

#     axis.legend(
#         loc="lower right",
#         fontsize=9,
#     )

#     figure.tight_layout()

#     figure.savefig(
#         CDF_PLOT_OUTPUT_FILE,
#         dpi=300,
#         bbox_inches="tight",
#     )

#     plt.show()
#     plt.close(figure)

#     print(
#         "\nReadable CDF graph saved as:\n  {}".format(
#             Path(
#                 CDF_PLOT_OUTPUT_FILE
#             ).resolve()
#         )
#     )
def plot_latency_cdf(
    all_cases: Dict[str, pd.DataFrame],
) -> None:
    """Plot a readable empirical CDF for all experiments."""

    # ----------------------------------------------------------
    # Determine readable X-axis range
    # ----------------------------------------------------------

    cdf_x_axis_limit = determine_cdf_x_axis_limit(
        all_cases
    )

    # ----------------------------------------------------------
    # Y-axis configuration
    # ----------------------------------------------------------

    if CDF_AS_PERCENTAGE:
        y_axis_label = (
            "Cumulative Percentage of Transactions"
        )
        y_axis_maximum = 100.0
    else:
        y_axis_label = "Cumulative Probability"
        y_axis_maximum = 1.0

    # ----------------------------------------------------------
    # Create figure
    # ----------------------------------------------------------

    figure, axis = plt.subplots(
        figsize=(13, 8)
    )

    # ----------------------------------------------------------
    # Plot each CDF
    # ----------------------------------------------------------

    for case_name, df in all_cases.items():

        latency_values, cdf_values = calculate_cdf(
            df
        )

        if CDF_AS_PERCENTAGE:
            plot_y = cdf_values * 100.0
        else:
            plot_y = cdf_values

        median_value = float(
            df[LATENCY_COLUMN].median()
        )

        p95_value = float(
            df[LATENCY_COLUMN].quantile(0.95)
        )

        axis.plot(
            latency_values,
            plot_y,
            linewidth=2.5,
            drawstyle="steps-post",
            label=(
                "{} (median {:.2f} s, P95 {:.2f} s)"
            ).format(
                case_name,
                median_value,
                p95_value,
            ),
        )

        # ------------------------------------------------------
        # Optional percentile lines
        # ------------------------------------------------------

        if SHOW_CDF_PERCENTILE_LINES:

            axis.axvline(
                x=median_value,
                linestyle=":",
                linewidth=1.0,
                alpha=0.5,
            )

            axis.axvline(
                x=p95_value,
                linestyle="--",
                linewidth=1.0,
                alpha=0.5,
            )

    # ----------------------------------------------------------
    # X-axis
    # ----------------------------------------------------------

    axis.set_xlim(left=0)

    if cdf_x_axis_limit is not None:

        axis.set_xlim(
            left=0,
            right=cdf_x_axis_limit,
        )

        print("\nCDF visible range")
        print("=" * 75)

        print(
            "Visible x-axis upper limit: "
            "{:.3f} seconds".format(
                cdf_x_axis_limit
            )
        )

        for case_name, df in all_cases.items():

            values_beyond_visible = int(
                (
                    df[LATENCY_COLUMN]
                    > cdf_x_axis_limit
                ).sum()
            )

            print(
                "{:<35}: {:,}".format(
                    case_name,
                    values_beyond_visible,
                )
            )

    # ----------------------------------------------------------
    # Y-axis
    # ----------------------------------------------------------

    axis.set_ylim(
        bottom=0,
        top=y_axis_maximum,
    )

    # ----------------------------------------------------------
    # Title
    # ----------------------------------------------------------

    axis.set_title(
        "CDF of Block Inclusion Latency "
        "(Latency <= {:.0f} Seconds)".format(
            MAX_LATENCY_SECONDS
        ),
        fontsize=TITLE_FONT_SIZE,
        pad=15,
    )

    # ----------------------------------------------------------
    # Axis labels
    # ----------------------------------------------------------

    axis.set_xlabel(
        "Block Timestamp Latency (seconds)",
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    axis.set_ylabel(
        y_axis_label,
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    # ----------------------------------------------------------
    # Tick sizes
    # ----------------------------------------------------------

    axis.tick_params(
        axis="both",
        which="major",
        labelsize=TICK_FONT_SIZE,
    )

    # ----------------------------------------------------------
    # Grid
    # ----------------------------------------------------------

    axis.grid(
        visible=True,
        linestyle="--",
        alpha=0.5,
    )

    # ----------------------------------------------------------
    # Legend
    # ----------------------------------------------------------

    axis.legend(
        loc="lower right",
        fontsize=LEGEND_FONT_SIZE,
        frameon=True,
    )

    # ----------------------------------------------------------
    # Layout and save
    # ----------------------------------------------------------

    figure.tight_layout()

    figure.savefig(
        CDF_PLOT_OUTPUT_FILE,
        dpi=300,
        bbox_inches="tight",
    )

    plt.show()
    plt.close(figure)

    print(
        "\nReadable CDF graph saved as:\n  {}".format(
            Path(
                CDF_PLOT_OUTPUT_FILE
            ).resolve()
        )
    )

# ============================================================
# Complete filtered-range CDF graph
# ============================================================

# def plot_full_range_latency_cdf(
#     all_cases: Dict[str, pd.DataFrame],
# ) -> None:
#     """Plot complete CDF range for all experiments."""

#     if CDF_AS_PERCENTAGE:
#         y_axis_label = (
#             "Cumulative Percentage of Transactions"
#         )
#         y_axis_maximum = 100.0
#     else:
#         y_axis_label = "Cumulative Probability"
#         y_axis_maximum = 1.0

#     figure, axis = plt.subplots(
#         figsize=(13, 8)
#     )

#     for case_name, df in all_cases.items():
#         latency_values, cdf_values = calculate_cdf(
#             df
#         )

#         if CDF_AS_PERCENTAGE:
#             plot_y = cdf_values * 100.0
#         else:
#             plot_y = cdf_values

#         axis.plot(
#             latency_values,
#             plot_y,
#             linewidth=2.0,
#             drawstyle="steps-post",
#             label=case_name,
#         )

#     axis.set_xlim(
#         left=0,
#         right=MAX_LATENCY_SECONDS,
#     )

#     axis.set_ylim(
#         bottom=0,
#         top=y_axis_maximum,
#     )

#     axis.set_title(
#         "CDF of Block Inclusion Latency — "
#         "Complete Filtered Range",
#         fontsize=16,
#     )

#     axis.set_xlabel(
#         "Block Timestamp Latency (seconds)",
#         fontsize=12,
#     )

#     axis.set_ylabel(
#         y_axis_label,
#         fontsize=12,
#     )

#     axis.grid(
#         visible=True,
#         linestyle="--",
#         alpha=0.5,
#     )

#     axis.legend(
#         loc="lower right",
#         fontsize=9,
#     )

#     figure.tight_layout()

#     figure.savefig(
#         CDF_FULL_RANGE_OUTPUT_FILE,
#         dpi=300,
#         bbox_inches="tight",
#     )

#     plt.show()
#     plt.close(figure)

#     print(
#         "\nComplete filtered-range CDF saved as:\n  {}".format(
#             Path(
#                 CDF_FULL_RANGE_OUTPUT_FILE
#             ).resolve()
#         )
#     )
def plot_full_range_latency_cdf(
    all_cases: Dict[str, pd.DataFrame],
) -> None:
    """Plot complete CDF range for all experiments."""

    # ----------------------------------------------------------
    # Y-axis configuration
    # ----------------------------------------------------------

    if CDF_AS_PERCENTAGE:
        y_axis_label = (
            "Cumulative Percentage of Transactions"
        )
        y_axis_maximum = 100.0
    else:
        y_axis_label = "Cumulative Probability"
        y_axis_maximum = 1.0

    # ----------------------------------------------------------
    # Create figure
    # ----------------------------------------------------------

    figure, axis = plt.subplots(
        figsize=(13, 8)
    )

    # ----------------------------------------------------------
    # Plot each experiment
    # ----------------------------------------------------------

    for case_name, df in all_cases.items():

        latency_values, cdf_values = calculate_cdf(
            df
        )

        if CDF_AS_PERCENTAGE:
            plot_y = cdf_values * 100.0
        else:
            plot_y = cdf_values

        median_value = float(
            df[LATENCY_COLUMN].median()
        )

        p95_value = float(
            df[LATENCY_COLUMN].quantile(0.95)
        )

        axis.plot(
            latency_values,
            plot_y,
            linewidth=2.5,
            drawstyle="steps-post",
            label=(
                "{} (median {:.2f} s, P95 {:.2f} s)"
            ).format(
                case_name,
                median_value,
                p95_value,
            ),
        )

        # ------------------------------------------------------
        # Optional percentile lines
        # ------------------------------------------------------

        if SHOW_CDF_PERCENTILE_LINES:

            axis.axvline(
                x=median_value,
                linestyle=":",
                linewidth=1.0,
                alpha=0.5,
            )

            axis.axvline(
                x=p95_value,
                linestyle="--",
                linewidth=1.0,
                alpha=0.5,
            )

    # ----------------------------------------------------------
    # Full X-axis range
    # ----------------------------------------------------------

    axis.set_xlim(
        left=0,
        right=MAX_LATENCY_SECONDS,
    )

    # ----------------------------------------------------------
    # Y-axis
    # ----------------------------------------------------------

    axis.set_ylim(
        bottom=0,
        top=y_axis_maximum,
    )

    # ----------------------------------------------------------
    # Title
    # ----------------------------------------------------------

    axis.set_title(
        "CDF of Block Inclusion Latency — "
        "Complete Filtered Range",
        fontsize=TITLE_FONT_SIZE,
        pad=15,
    )

    # ----------------------------------------------------------
    # Axis labels
    # ----------------------------------------------------------

    axis.set_xlabel(
        "Block Timestamp Latency (seconds)",
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    axis.set_ylabel(
        y_axis_label,
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    # ----------------------------------------------------------
    # Tick-label sizes
    # ----------------------------------------------------------

    axis.tick_params(
        axis="both",
        which="major",
        labelsize=TICK_FONT_SIZE,
    )

    # ----------------------------------------------------------
    # Grid
    # ----------------------------------------------------------

    axis.grid(
        visible=True,
        linestyle="--",
        alpha=0.5,
    )

    # ----------------------------------------------------------
    # Legend
    # ----------------------------------------------------------

    axis.legend(
        loc="lower right",
        fontsize=LEGEND_FONT_SIZE,
        frameon=True,
    )

    # ----------------------------------------------------------
    # Layout and save
    # ----------------------------------------------------------

    figure.tight_layout()

    figure.savefig(
        CDF_FULL_RANGE_OUTPUT_FILE,
        dpi=300,
        bbox_inches="tight",
    )

    plt.show()
    plt.close(figure)

    print(
        "\nComplete filtered-range CDF saved as:\n  {}".format(
            Path(
                CDF_FULL_RANGE_OUTPUT_FILE
            ).resolve()
        )
    )

# ============================================================
# Main
# ============================================================

def main() -> None:
    try:
        normal, normal_filter_information = load_latency_files(
            NORMAL_FILES,
            "Normal",
        )

        all_cases = {
            "Normal": normal,
        }

        all_filter_information = {
            "Normal": normal_filter_information,
        }

        all_file_paths = {
            "Normal": NORMAL_FILES,
        }

        modified_cases = {}

        for case_name, file_paths in MODIFIED_FILES.items():
            case_df, case_filter_information = load_latency_files(
                file_paths,
                case_name,
            )

            modified_cases[case_name] = case_df
            all_cases[case_name] = case_df
            all_filter_information[case_name] = case_filter_information
            all_file_paths[case_name] = file_paths

        # Print combined filtering information for each experiment.
        for case_name in all_cases:
            information = all_filter_information[case_name]

            print("\n{} combined filtering".format(case_name))
            print("=" * 75)
            print("Files loaded                         : {:,}".format(
                len(all_file_paths[case_name])
            ))
            print("Total rows                          : {:,}".format(
                information["total_rows"]
            ))
            print("Invalid/failed/incomplete rows      : {:,}".format(
                information["invalid_or_unsuccessful_rows"]
            ))
            print("Negative latency rows excluded      : {:,}".format(
                information["negative_latency_rows"]
            ))
            print("Latency > {:.0f} seconds excluded     : {:,}".format(
                MAX_LATENCY_SECONDS,
                information["above_max_latency_rows"],
            ))
            print("Transactions included in analysis   : {:,}".format(
                information["included_rows"]
            ))

        # Calculate and print statistics.
        statistics_rows = []

        for case_name, df in all_cases.items():
            statistics = calculate_statistics(
                case_name,
                df,
                all_filter_information[case_name],
            )

            statistics_rows.append(statistics)
            print_statistics(statistics)

        statistics_table = pd.DataFrame(statistics_rows)
        statistics_table.to_csv(
            STATISTICS_OUTPUT_FILE,
            index=False,
            float_format="%.6f",
        )

        print(
            "\nStatistics saved as:\n  {}".format(
                Path(STATISTICS_OUTPUT_FILE).resolve()
            )
        )

        # Print and save normal-versus-modified comparisons.
        print_comparison_table(
            normal,
            modified_cases,
        )

        comparison_table = create_comparison_table(
            normal,
            modified_cases,
        )

        comparison_table.to_csv(
            COMPARISON_OUTPUT_FILE,
            index=False,
            float_format="%.6f",
        )

        print(
            "\nComparison table saved as:\n  {}".format(
                Path(COMPARISON_OUTPUT_FILE).resolve()
            )
        )

        # Create and save threshold table.
        cdf_threshold_table = create_cdf_threshold_table(
            all_cases=all_cases,
            thresholds=CDF_LATENCY_THRESHOLDS_SECONDS,
        )

        print_cdf_threshold_table(cdf_threshold_table)

        cdf_threshold_table.to_csv(
            CDF_TABLE_OUTPUT_FILE,
            index=False,
            float_format="%.6f",
        )

        print(
            "\nCDF threshold table saved as:\n  {}".format(
                Path(CDF_TABLE_OUTPUT_FILE).resolve()
            )
        )

        # Generate graphs from ALL transactions across v1...v10.
        plot_transaction_latency(all_cases)
        plot_latency_cdf(all_cases)
        plot_full_range_latency_cdf(all_cases)

        print("\nCompleted successfully.")
        print("=" * 75)
        print(
            "Each plotted case combines v1 through v10. "
            "All transactions with latency greater than "
            "{:.0f} seconds were excluded.".format(
                MAX_LATENCY_SECONDS
            )
        )

    except (
        FileNotFoundError,
        ValueError,
        PermissionError,
        ImportError,
    ) as exc:
        print(
            "\nERROR: {}".format(exc),
            file=sys.stderr,
        )
        sys.exit(1)

    except Exception as exc:
        print(
            "\nUnexpected error: {}: {}".format(
                type(exc).__name__,
                exc,
            ),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()



# ============================================================
# Configuration
# ============================================================

NORMAL_FILE = Path(
    "replay_phased_fixed_metrics_replay_tx_v1_normal.xlsx"
)

# Change these filenames to match your actual Excel files.
MODIFIED_FILES = {
    "Modified - 5 Buckets": Path(
        "replay_phased_fixed_metrics_replay_tx_v1_modified_5.xlsx"
    ),
    "Modified - 10 Buckets": Path(
        "replay_phased_fixed_metrics_replay_tx_v1_modified_10.xlsx"
    ),
    "Modified - 15 Buckets": Path(
        "replay_phased_fixed_metrics_replay_tx_v1_modified_15.xlsx"
    ),
    "Modified - 30 Buckets": Path(
        "replay_phased_fixed_metrics_replay_tx_v1_modified_30.xlsx"
    ),
}

SHEET_NAME = "per_transaction"
LATENCY_COLUMN = "block_timestamp_latency_sec"


# ============================================================
# Latency filtering
# ============================================================

MAX_LATENCY_SECONDS = 1000.0
MIN_LATENCY_SECONDS = 0.0


# ============================================================
# Per-transaction plot configuration
# ============================================================

# 1 = every transaction, 10 = every 10th transaction, etc.
PLOT_EVERY_N = 1

LIMIT_TRANSACTION_Y_AXIS_TO_PERCENTILE = False
TRANSACTION_Y_AXIS_PERCENTILE = 0.99
TRANSACTION_Y_AXIS_PADDING = 1.10


# ============================================================
# CDF plot configuration
# ============================================================

CDF_AS_PERCENTAGE = True

LIMIT_CDF_X_AXIS_TO_PERCENTILE = True
CDF_X_AXIS_PERCENTILE = 0.99
CDF_X_AXIS_PADDING = 1.10

CDF_MINIMUM_X_AXIS_SECONDS = 30.0
CDF_FIXED_X_AXIS_MAX_SECONDS = None

SHOW_CDF_PERCENTILE_LINES = False


# ============================================================
# CDF threshold table
# ============================================================

CDF_LATENCY_THRESHOLDS_SECONDS = [
    1,
    2,
    5,
    10,
    15,
    20,
    25,
    30,
    45,
    60,
    120,
    300,
    600,
    1000,
]


# ============================================================
# Output files
# ============================================================

TRANSACTION_PLOT_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency.png"
)

CDF_PLOT_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency_cdf.png"
)

CDF_FULL_RANGE_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency_cdf_full_range.png"
)

CDF_TABLE_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency_cdf_table.csv"
)

STATISTICS_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency_statistics.csv"
)

COMPARISON_OUTPUT_FILE = (
    "normal_vs_multiple_bucket_block_latency_comparison.csv"
)


# ============================================================
# Data loading and filtering
# ============================================================

def load_latency(
    file_path: Path,
    case_name: str,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Load valid successful transactions from one Excel file.

    Transactions with negative latency or latency greater than
    MAX_LATENCY_SECONDS are excluded.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            "Input file does not exist:\n  {}".format(
                file_path.resolve()
            )
        )

    try:
        df = pd.read_excel(
            file_path,
            sheet_name=SHEET_NAME,
            engine="openpyxl",
        )
    except ValueError as exc:
        raise ValueError(
            "Could not find sheet '{}' in {}".format(
                SHEET_NAME,
                file_path.name,
            )
        ) from exc

    required_columns = {
        "status",
        "tx_hash",
        "block_number",
        LATENCY_COLUMN,
    }

    missing_columns = required_columns.difference(df.columns)

    if missing_columns:
        raise ValueError(
            "{} is missing required columns: {}\n"
            "Available columns: {}".format(
                file_path.name,
                sorted(missing_columns),
                list(df.columns),
            )
        )

    total_rows = len(df)

    df["status"] = (
        df["status"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["block_number"] = pd.to_numeric(
        df["block_number"],
        errors="coerce",
    )

    df[LATENCY_COLUMN] = pd.to_numeric(
        df[LATENCY_COLUMN],
        errors="coerce",
    )

    valid_base_mask = (
        (df["status"] == "SUCCESS")
        & df["tx_hash"].notna()
        & df["block_number"].notna()
        & df[LATENCY_COLUMN].notna()
        & np.isfinite(df[LATENCY_COLUMN])
    )

    valid_base_df = df[valid_base_mask].copy()

    successful_valid_rows = len(valid_base_df)

    negative_latency_count = int(
        (
            valid_base_df[LATENCY_COLUMN]
            < MIN_LATENCY_SECONDS
        ).sum()
    )

    above_max_latency_count = int(
        (
            valid_base_df[LATENCY_COLUMN]
            > MAX_LATENCY_SECONDS
        ).sum()
    )

    df = valid_base_df[
        (
            valid_base_df[LATENCY_COLUMN]
            >= MIN_LATENCY_SECONDS
        )
        & (
            valid_base_df[LATENCY_COLUMN]
            <= MAX_LATENCY_SECONDS
        )
    ].copy()

    included_rows = len(df)

    invalid_or_unsuccessful_rows = (
        total_rows - successful_valid_rows
    )

    filter_information = {
        "total_rows": int(total_rows),
        "invalid_or_unsuccessful_rows": int(
            invalid_or_unsuccessful_rows
        ),
        "negative_latency_rows": int(
            negative_latency_count
        ),
        "above_max_latency_rows": int(
            above_max_latency_count
        ),
        "included_rows": int(included_rows),
    }

    if df.empty:
        raise ValueError(
            "No valid transactions remained in {} after applying "
            "the latency range {:.3f} to {:.3f} seconds.".format(
                file_path.name,
                MIN_LATENCY_SECONDS,
                MAX_LATENCY_SECONDS,
            )
        )

    # Sort using the best available transaction ordering column.
    if "send_epoch_ms" in df.columns:
        df["send_epoch_ms"] = pd.to_numeric(
            df["send_epoch_ms"],
            errors="coerce",
        )
        df = df.sort_values(
            by="send_epoch_ms",
            kind="stable",
            na_position="last",
        )

    elif "send_epoch" in df.columns:
        df["send_epoch"] = pd.to_numeric(
            df["send_epoch"],
            errors="coerce",
        )
        df = df.sort_values(
            by="send_epoch",
            kind="stable",
            na_position="last",
        )

    elif "send_time_utc" in df.columns:
        df["send_time_utc"] = pd.to_datetime(
            df["send_time_utc"],
            errors="coerce",
            utc=True,
        )
        df = df.sort_values(
            by="send_time_utc",
            kind="stable",
            na_position="last",
        )

    elif "tx_index" in df.columns:
        df["tx_index"] = pd.to_numeric(
            df["tx_index"],
            errors="coerce",
        )
        df = df.sort_values(
            by="tx_index",
            kind="stable",
            na_position="last",
        )

    df = df.reset_index(drop=True)

    df["transaction_number"] = range(
        1,
        len(df) + 1,
    )

    df["case"] = case_name

    return df, filter_information


def print_filter_information(
    case_name: str,
    file_path: Path,
    information: Dict[str, int],
) -> None:
    """Print filtering information for one experiment."""

    print("\n{} filtering".format(case_name))
    print("=" * 75)

    print(
        "Input file                         : {}".format(
            file_path.name
        )
    )
    print(
        "Total rows                         : {:,}".format(
            information["total_rows"]
        )
    )
    print(
        "Invalid/failed/incomplete rows      : {:,}".format(
            information["invalid_or_unsuccessful_rows"]
        )
    )
    print(
        "Negative latency rows excluded      : {:,}".format(
            information["negative_latency_rows"]
        )
    )
    print(
        "Latency > {:.0f} seconds excluded     : {:,}".format(
            MAX_LATENCY_SECONDS,
            information["above_max_latency_rows"],
        )
    )
    print(
        "Transactions included in analysis   : {:,}".format(
            information["included_rows"]
        )
    )


# ============================================================
# Statistics
# ============================================================

def calculate_statistics(
    case_name: str,
    df: pd.DataFrame,
    filter_information: Dict[str, int],
) -> Dict[str, object]:
    """Calculate latency statistics for one experiment."""

    latency = df[LATENCY_COLUMN]

    return {
        "case": case_name,
        "transactions_included": int(len(latency)),
        "transactions_above_max_excluded": int(
            filter_information["above_max_latency_rows"]
        ),
        "maximum_allowed_latency_seconds": float(
            MAX_LATENCY_SECONDS
        ),
        "average_seconds": float(latency.mean()),
        "median_seconds": float(latency.median()),
        "minimum_seconds": float(latency.min()),
        "maximum_seconds": float(latency.max()),
        "standard_deviation_seconds": float(
            latency.std()
        ),
        "p50_seconds": float(
            latency.quantile(0.50)
        ),
        "p90_seconds": float(
            latency.quantile(0.90)
        ),
        "p95_seconds": float(
            latency.quantile(0.95)
        ),
        "p99_seconds": float(
            latency.quantile(0.99)
        ),
    }


def print_statistics(
    statistics: Dict[str, object],
) -> None:
    """Print latency statistics for one experiment."""

    print("\n{}".format(statistics["case"]))
    print("=" * 75)

    print(
        "Transactions : {:,}".format(
            statistics["transactions_included"]
        )
    )
    print(
        "Average      : {:.3f} seconds".format(
            statistics["average_seconds"]
        )
    )
    print(
        "Median       : {:.3f} seconds".format(
            statistics["median_seconds"]
        )
    )
    print(
        "Minimum      : {:.3f} seconds".format(
            statistics["minimum_seconds"]
        )
    )
    print(
        "Maximum      : {:.3f} seconds".format(
            statistics["maximum_seconds"]
        )
    )
    print(
        "Std. dev.    : {:.3f} seconds".format(
            statistics["standard_deviation_seconds"]
        )
    )
    print(
        "P50          : {:.3f} seconds".format(
            statistics["p50_seconds"]
        )
    )
    print(
        "P90          : {:.3f} seconds".format(
            statistics["p90_seconds"]
        )
    )
    print(
        "P95          : {:.3f} seconds".format(
            statistics["p95_seconds"]
        )
    )
    print(
        "P99          : {:.3f} seconds".format(
            statistics["p99_seconds"]
        )
    )


def create_comparison_table(
    normal: pd.DataFrame,
    modified_cases: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Create a table comparing every modified case against Normal.
    """

    normal_latency = normal[LATENCY_COLUMN]

    normal_metrics = {
        "average_seconds": float(normal_latency.mean()),
        "median_seconds": float(normal_latency.median()),
        "p90_seconds": float(
            normal_latency.quantile(0.90)
        ),
        "p95_seconds": float(
            normal_latency.quantile(0.95)
        ),
        "p99_seconds": float(
            normal_latency.quantile(0.99)
        ),
    }

    rows = []

    for case_name, df in modified_cases.items():
        latency = df[LATENCY_COLUMN]

        modified_metrics = {
            "average_seconds": float(latency.mean()),
            "median_seconds": float(latency.median()),
            "p90_seconds": float(
                latency.quantile(0.90)
            ),
            "p95_seconds": float(
                latency.quantile(0.95)
            ),
            "p99_seconds": float(
                latency.quantile(0.99)
            ),
        }

        row = {
            "case": case_name,
        }

        for metric_name, normal_value in normal_metrics.items():
            modified_value = modified_metrics[metric_name]

            difference = normal_value - modified_value

            if normal_value > 0:
                improvement_percentage = (
                    difference / normal_value
                ) * 100.0
            else:
                improvement_percentage = float("nan")

            row[
                "normal_{}".format(metric_name)
            ] = normal_value

            row[
                "modified_{}".format(metric_name)
            ] = modified_value

            row[
                "difference_{}".format(metric_name)
            ] = difference

            row[
                "improvement_percent_{}".format(metric_name)
            ] = improvement_percentage

        rows.append(row)

    return pd.DataFrame(rows)


def print_comparison_table(
    normal: pd.DataFrame,
    modified_cases: Dict[str, pd.DataFrame],
) -> None:
    """Print Normal versus all modified experiments."""

    metric_definitions = [
        ("Average", "mean"),
        ("Median", "median"),
        ("P90", 0.90),
        ("P95", 0.95),
        ("P99", 0.99),
    ]

    case_names = ["Normal"] + list(modified_cases.keys())

    column_width = 24

    print("\nLatency comparison")
    print("=" * (18 + column_width * len(case_names)))

    header = "{:<14}".format("Metric")

    for case_name in case_names:
        header += "{:>{width}}".format(
            case_name,
            width=column_width,
        )

    print(header)
    print("-" * (18 + column_width * len(case_names)))

    for metric_name, operation in metric_definitions:
        row = "{:<14}".format(metric_name)

        if operation == "mean":
            normal_value = normal[LATENCY_COLUMN].mean()
        elif operation == "median":
            normal_value = normal[LATENCY_COLUMN].median()
        else:
            normal_value = normal[LATENCY_COLUMN].quantile(
                operation
            )

        row += "{:>{width}.3f}".format(
            normal_value,
            width=column_width,
        )

        for _, df in modified_cases.items():
            if operation == "mean":
                value = df[LATENCY_COLUMN].mean()
            elif operation == "median":
                value = df[LATENCY_COLUMN].median()
            else:
                value = df[LATENCY_COLUMN].quantile(
                    operation
                )

            row += "{:>{width}.3f}".format(
                value,
                width=column_width,
            )

        print(row)


# ============================================================
# Axis calculations
# ============================================================

def calculate_combined_percentile_limit(
    all_cases: Dict[str, pd.DataFrame],
    percentile: float,
    padding: float,
) -> Optional[float]:
    """
    Calculate an axis limit using all experiment distributions.
    """

    if percentile <= 0 or percentile > 1:
        raise ValueError(
            "Percentile must be greater than 0 and "
            "less than or equal to 1."
        )

    if padding <= 0:
        raise ValueError(
            "Axis padding must be greater than zero."
        )

    combined_latency = pd.concat(
        [
            df[LATENCY_COLUMN]
            for df in all_cases.values()
        ],
        ignore_index=True,
    )

    percentile_value = combined_latency.quantile(
        percentile
    )

    if (
        pd.isna(percentile_value)
        or not np.isfinite(percentile_value)
        or percentile_value <= 0
    ):
        return None

    return float(percentile_value * padding)


def determine_cdf_x_axis_limit(
    all_cases: Dict[str, pd.DataFrame],
) -> Optional[float]:
    """Determine a readable CDF x-axis upper limit."""

    if CDF_FIXED_X_AXIS_MAX_SECONDS is not None:
        if CDF_FIXED_X_AXIS_MAX_SECONDS <= 0:
            raise ValueError(
                "CDF_FIXED_X_AXIS_MAX_SECONDS must "
                "be greater than zero."
            )

        return min(
            float(CDF_FIXED_X_AXIS_MAX_SECONDS),
            MAX_LATENCY_SECONDS,
        )

    if not LIMIT_CDF_X_AXIS_TO_PERCENTILE:
        return None

    limit = calculate_combined_percentile_limit(
        all_cases=all_cases,
        percentile=CDF_X_AXIS_PERCENTILE,
        padding=CDF_X_AXIS_PADDING,
    )

    if limit is None:
        return None

    if CDF_MINIMUM_X_AXIS_SECONDS is not None:
        if CDF_MINIMUM_X_AXIS_SECONDS <= 0:
            raise ValueError(
                "CDF_MINIMUM_X_AXIS_SECONDS must "
                "be greater than zero."
            )

        limit = max(
            limit,
            float(CDF_MINIMUM_X_AXIS_SECONDS),
        )

    return min(limit, MAX_LATENCY_SECONDS)


# ============================================================
# Per-transaction latency plot
# ============================================================

# def plot_transaction_latency(
#     all_cases: Dict[str, pd.DataFrame],
# ) -> None:
#     """Plot latency versus transaction sending order."""

#     if PLOT_EVERY_N < 1:
#         raise ValueError(
#             "PLOT_EVERY_N must be at least 1."
#         )

#     y_axis_limit = None

#     if LIMIT_TRANSACTION_Y_AXIS_TO_PERCENTILE:
#         y_axis_limit = calculate_combined_percentile_limit(
#             all_cases=all_cases,
#             percentile=(
#                 TRANSACTION_Y_AXIS_PERCENTILE
#             ),
#             padding=TRANSACTION_Y_AXIS_PADDING,
#         )

#         if y_axis_limit is not None:
#             y_axis_limit = min(
#                 y_axis_limit,
#                 MAX_LATENCY_SECONDS,
#             )

#     figure, axis = plt.subplots(
#         figsize=(16, 8)
#     )

#     for case_name, df in all_cases.items():
#         plot_df = df.iloc[
#             ::PLOT_EVERY_N
#         ].copy()

#         average_latency = df[
#             LATENCY_COLUMN
#         ].mean()

#         axis.plot(
#             plot_df["transaction_number"],
#             plot_df[LATENCY_COLUMN],
#             marker="o",
#             markersize=2.0,
#             linewidth=1.0,
#             label=(
#                 "{} - average {:.2f} s"
#             ).format(
#                 case_name,
#                 average_latency,
#             ),
#         )

#     axis.set_ylim(bottom=0)

#     if y_axis_limit is not None:
#         axis.set_ylim(
#             bottom=0,
#             top=y_axis_limit,
#         )

#     axis.set_title(
#         "Per-Transaction Block Inclusion Latency "
#         "(Latency <= {:.0f} Seconds)".format(
#             MAX_LATENCY_SECONDS
#         ),
#         fontsize=16,
#     )

#     axis.set_xlabel(
#         "Transaction Number After Filtering",
#         fontsize=12,
#     )

#     axis.set_ylabel(
#         "Block Timestamp Latency (seconds)",
#         fontsize=12,
#     )

#     axis.grid(
#         visible=True,
#         linestyle="--",
#         alpha=0.5,
#     )

#     axis.legend(
#         loc="best",
#         fontsize=9,
#     )

#     figure.tight_layout()

#     figure.savefig(
#         TRANSACTION_PLOT_OUTPUT_FILE,
#         dpi=300,
#         bbox_inches="tight",
#     )

#     plt.show()
#     plt.close(figure)

#     print(
#         "\nPer-transaction graph saved as:\n  {}".format(
#             Path(
#                 TRANSACTION_PLOT_OUTPUT_FILE
#             ).resolve()
#         )
#     )


# # ============================================================
# # CDF calculations
# # ============================================================

# def calculate_cdf(
#     df: pd.DataFrame,
# ) -> Tuple[np.ndarray, np.ndarray]:
#     """Calculate the empirical cumulative distribution."""

#     sorted_latency = np.sort(
#         df[LATENCY_COLUMN]
#         .dropna()
#         .to_numpy(dtype=float)
#     )

#     if len(sorted_latency) == 0:
#         raise ValueError(
#             "Cannot calculate CDF because the "
#             "latency data is empty."
#         )

#     cumulative_probability = (
#         np.arange(
#             1,
#             len(sorted_latency) + 1,
#             dtype=float,
#         )
#         / float(len(sorted_latency))
#     )

#     return (
#         sorted_latency,
#         cumulative_probability,
#     )
# ============================================================
# CDF calculations
# ============================================================

def calculate_cdf(
    df: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate the empirical cumulative distribution."""

    sorted_latency = np.sort(
        df[LATENCY_COLUMN]
        .dropna()
        .to_numpy(dtype=float)
    )

    if len(sorted_latency) == 0:
        raise ValueError(
            "Cannot calculate CDF because the latency data is empty."
        )

    cumulative_probability = (
        np.arange(
            1,
            len(sorted_latency) + 1,
            dtype=float,
        )
        / float(len(sorted_latency))
    )

    return (
        sorted_latency,
        cumulative_probability,
    )


def plot_transaction_latency(
    all_cases: Dict[str, pd.DataFrame],
) -> None:
    """Plot latency versus transaction sending order."""

    if PLOT_EVERY_N < 1:
        raise ValueError(
            "PLOT_EVERY_N must be at least 1."
        )

    y_axis_limit = None

    if LIMIT_TRANSACTION_Y_AXIS_TO_PERCENTILE:
        y_axis_limit = calculate_combined_percentile_limit(
            all_cases=all_cases,
            percentile=TRANSACTION_Y_AXIS_PERCENTILE,
            padding=TRANSACTION_Y_AXIS_PADDING,
        )

        if y_axis_limit is not None:
            y_axis_limit = min(
                y_axis_limit,
                MAX_LATENCY_SECONDS,
            )

    # ----------------------------------------------------------
    # Create figure
    # ----------------------------------------------------------

    figure, axis = plt.subplots(
        figsize=(16, 8)
    )

    # ----------------------------------------------------------
    # Plot each experiment
    # ----------------------------------------------------------

    for case_name, df in all_cases.items():

        plot_df = df.iloc[
            ::PLOT_EVERY_N
        ].copy()

        average_latency = df[
            LATENCY_COLUMN
        ].mean()

        axis.plot(
            plot_df["transaction_number"],
            plot_df[LATENCY_COLUMN],
            marker="o",
            markersize=2.5,
            linewidth=1.5,
            label=(
                "{} - average {:.2f} s"
            ).format(
                case_name,
                average_latency,
            ),
        )

    # ----------------------------------------------------------
    # Y-axis
    # ----------------------------------------------------------

    axis.set_ylim(bottom=0)

    if y_axis_limit is not None:
        axis.set_ylim(
            bottom=0,
            top=y_axis_limit,
        )

    # ----------------------------------------------------------
    # Title
    # ----------------------------------------------------------

    axis.set_title(
        "Per-Transaction Block Inclusion Latency "
        "(Latency <= {:.0f} Seconds)".format(
            MAX_LATENCY_SECONDS
        ),
        fontsize=TITLE_FONT_SIZE,
        pad=15,
    )

    # ----------------------------------------------------------
    # Axis labels
    # ----------------------------------------------------------

    axis.set_xlabel(
        "Transaction Number After Filtering",
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    axis.set_ylabel(
        "Block Timestamp Latency (seconds)",
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    # ----------------------------------------------------------
    # Tick-label sizes
    # ----------------------------------------------------------

    axis.tick_params(
        axis="both",
        which="major",
        labelsize=TICK_FONT_SIZE,
    )

    # ----------------------------------------------------------
    # Grid
    # ----------------------------------------------------------

    axis.grid(
        visible=True,
        linestyle="--",
        alpha=0.5,
    )

    # ----------------------------------------------------------
    # Legend
    # ----------------------------------------------------------

    axis.legend(
        loc="best",
        fontsize=LEGEND_FONT_SIZE,
        frameon=True,
    )

    # ----------------------------------------------------------
    # Layout and save
    # ----------------------------------------------------------

    figure.tight_layout()

    figure.savefig(
        TRANSACTION_PLOT_OUTPUT_FILE,
        dpi=300,
        bbox_inches="tight",
    )

    plt.show()
    plt.close(figure)

    print(
        "\nPer-transaction graph saved as:\n  {}".format(
            Path(
                TRANSACTION_PLOT_OUTPUT_FILE
            ).resolve()
        )
    )

def percentage_within_threshold(
    latency_values: pd.Series,
    threshold_seconds: float,
) -> float:
    """Return percentage of transactions within a threshold."""

    if len(latency_values) == 0:
        return float("nan")

    count_within = int(
        (
            latency_values <= threshold_seconds
        ).sum()
    )

    return (
        float(count_within)
        / float(len(latency_values))
    ) * 100.0


# ============================================================
# CDF threshold table
# ============================================================

def create_cdf_threshold_table(
    all_cases: Dict[str, pd.DataFrame],
    thresholds: List[float],
) -> pd.DataFrame:
    """
    Create one threshold table for all experiments.
    """

    rows = []

    for threshold in thresholds:
        if threshold < 0:
            raise ValueError(
                "CDF thresholds cannot be negative."
            )

        if threshold > MAX_LATENCY_SECONDS:
            continue

        row = {
            "latency_threshold_seconds": float(
                threshold
            )
        }

        for case_name, df in all_cases.items():
            safe_name = (
                case_name
                .lower()
                .replace(" ", "_")
                .replace("-", "")
            )

            row[
                "{}_within_threshold_percent".format(
                    safe_name
                )
            ] = percentage_within_threshold(
                df[LATENCY_COLUMN],
                threshold,
            )

        rows.append(row)

    return pd.DataFrame(rows)


def print_cdf_threshold_table(
    table: pd.DataFrame,
) -> None:
    """Print the threshold comparison table."""

    print("\nCDF threshold comparison")
    print("=" * 140)

    print(
        table.to_string(
            index=False,
            float_format=lambda value: "{:.2f}".format(
                value
            ),
        )
    )


# ============================================================
# Readable percentile-limited CDF graph
# ============================================================

# def plot_latency_cdf(
#     all_cases: Dict[str, pd.DataFrame],
# ) -> None:
#     """Plot a readable empirical CDF for all experiments."""

#     cdf_x_axis_limit = determine_cdf_x_axis_limit(
#         all_cases
#     )

#     if CDF_AS_PERCENTAGE:
#         y_axis_label = (
#             "Cumulative Percentage of Transactions"
#         )
#         y_axis_maximum = 100.0
#     else:
#         y_axis_label = "Cumulative Probability"
#         y_axis_maximum = 1.0

#     figure, axis = plt.subplots(
#         figsize=(13, 8)
#     )

#     for case_name, df in all_cases.items():
#         latency_values, cdf_values = calculate_cdf(
#             df
#         )

#         if CDF_AS_PERCENTAGE:
#             plot_y = cdf_values * 100.0
#         else:
#             plot_y = cdf_values

#         median_value = float(
#             df[LATENCY_COLUMN].median()
#         )

#         p95_value = float(
#             df[LATENCY_COLUMN].quantile(0.95)
#         )

#         axis.plot(
#             latency_values,
#             plot_y,
#             linewidth=2.0,
#             drawstyle="steps-post",
#             label=(
#                 "{} (median {:.2f} s, P95 {:.2f} s)"
#             ).format(
#                 case_name,
#                 median_value,
#                 p95_value,
#             ),
#         )

#         if SHOW_CDF_PERCENTILE_LINES:
#             axis.axvline(
#                 x=median_value,
#                 linestyle=":",
#                 linewidth=0.8,
#                 alpha=0.5,
#             )

#             axis.axvline(
#                 x=p95_value,
#                 linestyle="--",
#                 linewidth=0.8,
#                 alpha=0.5,
#             )

#     axis.set_xlim(left=0)

#     if cdf_x_axis_limit is not None:
#         axis.set_xlim(
#             left=0,
#             right=cdf_x_axis_limit,
#         )

#         print("\nCDF visible range")
#         print("=" * 75)

#         print(
#             "Visible x-axis upper limit: "
#             "{:.3f} seconds".format(
#                 cdf_x_axis_limit
#             )
#         )

#         for case_name, df in all_cases.items():
#             values_beyond_visible = int(
#                 (
#                     df[LATENCY_COLUMN]
#                     > cdf_x_axis_limit
#                 ).sum()
#             )

#             print(
#                 "{:<35}: {:,}".format(
#                     case_name,
#                     values_beyond_visible,
#                 )
#             )

#     axis.set_ylim(
#         bottom=0,
#         top=y_axis_maximum,
#     )

#     axis.set_title(
#         "CDF of Block Inclusion Latency "
#         "(Latency <= {:.0f} Seconds)".format(
#             MAX_LATENCY_SECONDS
#         ),
#         fontsize=16,
#     )

#     axis.set_xlabel(
#         "Block Timestamp Latency (seconds)",
#         fontsize=12,
#     )

#     axis.set_ylabel(
#         y_axis_label,
#         fontsize=12,
#     )

#     axis.grid(
#         visible=True,
#         linestyle="--",
#         alpha=0.5,
#     )

#     axis.legend(
#         loc="lower right",
#         fontsize=9,
#     )

#     figure.tight_layout()

#     figure.savefig(
#         CDF_PLOT_OUTPUT_FILE,
#         dpi=300,
#         bbox_inches="tight",
#     )

#     plt.show()
#     plt.close(figure)

#     print(
#         "\nReadable CDF graph saved as:\n  {}".format(
#             Path(
#                 CDF_PLOT_OUTPUT_FILE
#             ).resolve()
#         )
#     )
def plot_latency_cdf(
    all_cases: Dict[str, pd.DataFrame],
) -> None:
    """Plot a readable empirical CDF for all experiments."""

    # ----------------------------------------------------------
    # Determine readable X-axis range
    # ----------------------------------------------------------

    cdf_x_axis_limit = determine_cdf_x_axis_limit(
        all_cases
    )

    # ----------------------------------------------------------
    # Y-axis configuration
    # ----------------------------------------------------------

    if CDF_AS_PERCENTAGE:
        y_axis_label = (
            "Cumulative Percentage of Transactions"
        )
        y_axis_maximum = 100.0
    else:
        y_axis_label = "Cumulative Probability"
        y_axis_maximum = 1.0

    # ----------------------------------------------------------
    # Create figure
    # ----------------------------------------------------------

    figure, axis = plt.subplots(
        figsize=(13, 8)
    )

    # ----------------------------------------------------------
    # Plot each CDF
    # ----------------------------------------------------------

    for case_name, df in all_cases.items():

        latency_values, cdf_values = calculate_cdf(
            df
        )

        if CDF_AS_PERCENTAGE:
            plot_y = cdf_values * 100.0
        else:
            plot_y = cdf_values

        median_value = float(
            df[LATENCY_COLUMN].median()
        )

        p95_value = float(
            df[LATENCY_COLUMN].quantile(0.95)
        )

        axis.plot(
            latency_values,
            plot_y,
            linewidth=2.5,
            drawstyle="steps-post",
            label=(
                "{} (median {:.2f} s, P95 {:.2f} s)"
            ).format(
                case_name,
                median_value,
                p95_value,
            ),
        )

        # ------------------------------------------------------
        # Optional percentile lines
        # ------------------------------------------------------

        if SHOW_CDF_PERCENTILE_LINES:

            axis.axvline(
                x=median_value,
                linestyle=":",
                linewidth=1.0,
                alpha=0.5,
            )

            axis.axvline(
                x=p95_value,
                linestyle="--",
                linewidth=1.0,
                alpha=0.5,
            )

    # ----------------------------------------------------------
    # X-axis
    # ----------------------------------------------------------

    axis.set_xlim(left=0)

    if cdf_x_axis_limit is not None:

        axis.set_xlim(
            left=0,
            right=cdf_x_axis_limit,
        )

        print("\nCDF visible range")
        print("=" * 75)

        print(
            "Visible x-axis upper limit: "
            "{:.3f} seconds".format(
                cdf_x_axis_limit
            )
        )

        for case_name, df in all_cases.items():

            values_beyond_visible = int(
                (
                    df[LATENCY_COLUMN]
                    > cdf_x_axis_limit
                ).sum()
            )

            print(
                "{:<35}: {:,}".format(
                    case_name,
                    values_beyond_visible,
                )
            )

    # ----------------------------------------------------------
    # Y-axis
    # ----------------------------------------------------------

    axis.set_ylim(
        bottom=0,
        top=y_axis_maximum,
    )

    # ----------------------------------------------------------
    # Title
    # ----------------------------------------------------------

    axis.set_title(
        "CDF of Block Inclusion Latency "
        "(Latency <= {:.0f} Seconds)".format(
            MAX_LATENCY_SECONDS
        ),
        fontsize=TITLE_FONT_SIZE,
        pad=15,
    )

    # ----------------------------------------------------------
    # Axis labels
    # ----------------------------------------------------------

    axis.set_xlabel(
        "Block Timestamp Latency (seconds)",
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    axis.set_ylabel(
        y_axis_label,
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    # ----------------------------------------------------------
    # Tick sizes
    # ----------------------------------------------------------

    axis.tick_params(
        axis="both",
        which="major",
        labelsize=TICK_FONT_SIZE,
    )

    # ----------------------------------------------------------
    # Grid
    # ----------------------------------------------------------

    axis.grid(
        visible=True,
        linestyle="--",
        alpha=0.5,
    )

    # ----------------------------------------------------------
    # Legend
    # ----------------------------------------------------------

    axis.legend(
        loc="lower right",
        fontsize=LEGEND_FONT_SIZE,
        frameon=True,
    )

    # ----------------------------------------------------------
    # Layout and save
    # ----------------------------------------------------------

    figure.tight_layout()

    figure.savefig(
        CDF_PLOT_OUTPUT_FILE,
        dpi=300,
        bbox_inches="tight",
    )

    plt.show()
    plt.close(figure)

    print(
        "\nReadable CDF graph saved as:\n  {}".format(
            Path(
                CDF_PLOT_OUTPUT_FILE
            ).resolve()
        )
    )

# ============================================================
# Complete filtered-range CDF graph
# ============================================================

# def plot_full_range_latency_cdf(
#     all_cases: Dict[str, pd.DataFrame],
# ) -> None:
#     """Plot complete CDF range for all experiments."""

#     if CDF_AS_PERCENTAGE:
#         y_axis_label = (
#             "Cumulative Percentage of Transactions"
#         )
#         y_axis_maximum = 100.0
#     else:
#         y_axis_label = "Cumulative Probability"
#         y_axis_maximum = 1.0

#     figure, axis = plt.subplots(
#         figsize=(13, 8)
#     )

#     for case_name, df in all_cases.items():
#         latency_values, cdf_values = calculate_cdf(
#             df
#         )

#         if CDF_AS_PERCENTAGE:
#             plot_y = cdf_values * 100.0
#         else:
#             plot_y = cdf_values

#         axis.plot(
#             latency_values,
#             plot_y,
#             linewidth=2.0,
#             drawstyle="steps-post",
#             label=case_name,
#         )

#     axis.set_xlim(
#         left=0,
#         right=MAX_LATENCY_SECONDS,
#     )

#     axis.set_ylim(
#         bottom=0,
#         top=y_axis_maximum,
#     )

#     axis.set_title(
#         "CDF of Block Inclusion Latency — "
#         "Complete Filtered Range",
#         fontsize=16,
#     )

#     axis.set_xlabel(
#         "Block Timestamp Latency (seconds)",
#         fontsize=12,
#     )

#     axis.set_ylabel(
#         y_axis_label,
#         fontsize=12,
#     )

#     axis.grid(
#         visible=True,
#         linestyle="--",
#         alpha=0.5,
#     )

#     axis.legend(
#         loc="lower right",
#         fontsize=9,
#     )

#     figure.tight_layout()

#     figure.savefig(
#         CDF_FULL_RANGE_OUTPUT_FILE,
#         dpi=300,
#         bbox_inches="tight",
#     )

#     plt.show()
#     plt.close(figure)

#     print(
#         "\nComplete filtered-range CDF saved as:\n  {}".format(
#             Path(
#                 CDF_FULL_RANGE_OUTPUT_FILE
#             ).resolve()
#         )
#     )
def plot_full_range_latency_cdf(
    all_cases: Dict[str, pd.DataFrame],
) -> None:
    """Plot complete CDF range for all experiments."""

    # ----------------------------------------------------------
    # Y-axis configuration
    # ----------------------------------------------------------

    if CDF_AS_PERCENTAGE:
        y_axis_label = (
            "Cumulative Percentage of Transactions"
        )
        y_axis_maximum = 100.0
    else:
        y_axis_label = "Cumulative Probability"
        y_axis_maximum = 1.0

    # ----------------------------------------------------------
    # Create figure
    # ----------------------------------------------------------

    figure, axis = plt.subplots(
        figsize=(13, 8)
    )

    # ----------------------------------------------------------
    # Plot each experiment
    # ----------------------------------------------------------

    for case_name, df in all_cases.items():

        latency_values, cdf_values = calculate_cdf(
            df
        )

        if CDF_AS_PERCENTAGE:
            plot_y = cdf_values * 100.0
        else:
            plot_y = cdf_values

        median_value = float(
            df[LATENCY_COLUMN].median()
        )

        p95_value = float(
            df[LATENCY_COLUMN].quantile(0.95)
        )

        axis.plot(
            latency_values,
            plot_y,
            linewidth=2.5,
            drawstyle="steps-post",
            label=(
                "{} (median {:.2f} s, P95 {:.2f} s)"
            ).format(
                case_name,
                median_value,
                p95_value,
            ),
        )

        # ------------------------------------------------------
        # Optional percentile lines
        # ------------------------------------------------------

        if SHOW_CDF_PERCENTILE_LINES:

            axis.axvline(
                x=median_value,
                linestyle=":",
                linewidth=1.0,
                alpha=0.5,
            )

            axis.axvline(
                x=p95_value,
                linestyle="--",
                linewidth=1.0,
                alpha=0.5,
            )

    # ----------------------------------------------------------
    # Full X-axis range
    # ----------------------------------------------------------

    axis.set_xlim(
        left=0,
        right=MAX_LATENCY_SECONDS,
    )

    # ----------------------------------------------------------
    # Y-axis
    # ----------------------------------------------------------

    axis.set_ylim(
        bottom=0,
        top=y_axis_maximum,
    )

    # ----------------------------------------------------------
    # Title
    # ----------------------------------------------------------

    axis.set_title(
        "CDF of Block Inclusion Latency — "
        "Complete Filtered Range",
        fontsize=TITLE_FONT_SIZE,
        pad=15,
    )

    # ----------------------------------------------------------
    # Axis labels
    # ----------------------------------------------------------

    axis.set_xlabel(
        "Block Timestamp Latency (seconds)",
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    axis.set_ylabel(
        y_axis_label,
        fontsize=AXIS_LABEL_FONT_SIZE,
        labelpad=10,
    )

    # ----------------------------------------------------------
    # Tick-label sizes
    # ----------------------------------------------------------

    axis.tick_params(
        axis="both",
        which="major",
        labelsize=TICK_FONT_SIZE,
    )

    # ----------------------------------------------------------
    # Grid
    # ----------------------------------------------------------

    axis.grid(
        visible=True,
        linestyle="--",
        alpha=0.5,
    )

    # ----------------------------------------------------------
    # Legend
    # ----------------------------------------------------------

    axis.legend(
        loc="lower right",
        fontsize=LEGEND_FONT_SIZE,
        frameon=True,
    )

    # ----------------------------------------------------------
    # Layout and save
    # ----------------------------------------------------------

    figure.tight_layout()

    figure.savefig(
        CDF_FULL_RANGE_OUTPUT_FILE,
        dpi=300,
        bbox_inches="tight",
    )

    plt.show()
    plt.close(figure)

    print(
        "\nComplete filtered-range CDF saved as:\n  {}".format(
            Path(
                CDF_FULL_RANGE_OUTPUT_FILE
            ).resolve()
        )
    )

# ============================================================
# Main
# ============================================================

def main() -> None:
    try:
        normal, normal_filter_information = load_latency(
            NORMAL_FILE,
            "Normal",
        )

        all_cases = {
            "Normal": normal,
        }

        all_filter_information = {
            "Normal": normal_filter_information,
        }

        all_file_paths = {
            "Normal": NORMAL_FILE,
        }

        modified_cases = {}

        for case_name, file_path in MODIFIED_FILES.items():
            case_df, case_filter_information = load_latency(
                file_path,
                case_name,
            )

            modified_cases[case_name] = case_df
            all_cases[case_name] = case_df

            all_filter_information[
                case_name
            ] = case_filter_information

            all_file_paths[
                case_name
            ] = file_path

        # Print filtering information.
        for case_name, df in all_cases.items():
            print_filter_information(
                case_name,
                all_file_paths[case_name],
                all_filter_information[case_name],
            )

        # Calculate and print statistics.
        statistics_rows = []

        for case_name, df in all_cases.items():
            statistics = calculate_statistics(
                case_name,
                df,
                all_filter_information[case_name],
            )

            statistics_rows.append(statistics)

            print_statistics(statistics)

        statistics_table = pd.DataFrame(
            statistics_rows
        )

        statistics_table.to_csv(
            STATISTICS_OUTPUT_FILE,
            index=False,
            float_format="%.6f",
        )

        print(
            "\nStatistics saved as:\n  {}".format(
                Path(
                    STATISTICS_OUTPUT_FILE
                ).resolve()
            )
        )

        # Print and save normal-versus-modified comparisons.
        print_comparison_table(
            normal,
            modified_cases,
        )

        comparison_table = create_comparison_table(
            normal,
            modified_cases,
        )

        comparison_table.to_csv(
            COMPARISON_OUTPUT_FILE,
            index=False,
            float_format="%.6f",
        )

        print(
            "\nComparison table saved as:\n  {}".format(
                Path(
                    COMPARISON_OUTPUT_FILE
                ).resolve()
            )
        )

        # Create and save threshold table.
        cdf_threshold_table = (
            create_cdf_threshold_table(
                all_cases=all_cases,
                thresholds=(
                    CDF_LATENCY_THRESHOLDS_SECONDS
                ),
            )
        )

        print_cdf_threshold_table(
            cdf_threshold_table
        )

        cdf_threshold_table.to_csv(
            CDF_TABLE_OUTPUT_FILE,
            index=False,
            float_format="%.6f",
        )

        print(
            "\nCDF threshold table saved as:\n  {}".format(
                Path(
                    CDF_TABLE_OUTPUT_FILE
                ).resolve()
            )
        )

        # Generate graphs.
        plot_transaction_latency(
            all_cases
        )

        plot_latency_cdf(
            all_cases
        )

        plot_full_range_latency_cdf(
            all_cases
        )

        print("\nCompleted successfully.")
        print("=" * 75)

        print(
            "All transactions with latency greater than "
            "{:.0f} seconds were excluded.".format(
                MAX_LATENCY_SECONDS
            )
        )

    except (
        FileNotFoundError,
        ValueError,
        PermissionError,
        ImportError,
    ) as exc:
        print(
            "\nERROR: {}".format(exc),
            file=sys.stderr,
        )
        sys.exit(1)

    except Exception as exc:
        print(
            "\nUnexpected error: {}: {}".format(
                type(exc).__name__,
                exc,
            ),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

