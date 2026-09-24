#!/usr/bin/env python3

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ============================================================
# Configuration
# ============================================================

NORMAL_FILE = Path(
    "replay_phased_fixed_metrics_replay_tx_v1_normal.xlsx"
)

MODIFIED_FILE = Path(
    "replay_phased_fixed_metrics_replay_tx_v1_modified.xlsx"
)

SHEET_NAME = "per_transaction"
LATENCY_COLUMN = "block_timestamp_latency_sec"


# ============================================================
# Latency filtering
# ============================================================

# Transactions with latency greater than this value are excluded
# from all statistics, graphs, and output tables.
MAX_LATENCY_SECONDS = 1000.0

# Transactions with negative latency are also excluded.
MIN_LATENCY_SECONDS = 0.0


# ============================================================
# Per-transaction plot configuration
# ============================================================

# Plot every Nth transaction:
#
# 1  = every transaction
# 10 = every 10th transaction
# 50 = every 50th transaction
#
# This affects only visualization.
# All valid transactions are still used for statistics and CDF.
PLOT_EVERY_N = 1


# True:
# Limit the visible per-transaction graph y-axis using the
# combined percentile.
#
# False:
# Display the complete filtered range, up to 1000 seconds.
LIMIT_TRANSACTION_Y_AXIS_TO_PERCENTILE = False

TRANSACTION_Y_AXIS_PERCENTILE = 0.99
TRANSACTION_Y_AXIS_PADDING = 1.10


# ============================================================
# CDF plot configuration
# ============================================================

# True:
# Show CDF y-axis as percentage from 0 to 100.
#
# False:
# Show CDF y-axis as probability from 0.0 to 1.0.
CDF_AS_PERCENTAGE = True


# True:
# Limit the visible CDF x-axis to the combined percentile.
#
# False:
# Show the complete filtered range up to 1000 seconds.
LIMIT_CDF_X_AXIS_TO_PERCENTILE = True

CDF_X_AXIS_PERCENTILE = 0.99
CDF_X_AXIS_PADDING = 1.10


# Ensure that the CDF graph displays at least this range.
# Set to None to disable.
CDF_MINIMUM_X_AXIS_SECONDS = 30.0


# Set to a number such as 60.0 to force the CDF x-axis to
# display exactly from 0 to 60 seconds.
#
# Keep as None to use automatic percentile-based scaling.
CDF_FIXED_X_AXIS_MAX_SECONDS = None


# Add median and P95 vertical reference lines to the CDF.
SHOW_CDF_PERCENTILE_LINES = True


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
    "normal_vs_modified_block_latency.png"
)

CDF_PLOT_OUTPUT_FILE = (
    "normal_vs_modified_block_latency_cdf.png"
)

CDF_FULL_RANGE_OUTPUT_FILE = (
    "normal_vs_modified_block_latency_cdf_full_range.png"
)

CDF_TABLE_OUTPUT_FILE = (
    "normal_vs_modified_block_latency_cdf_table.csv"
)

STATISTICS_OUTPUT_FILE = (
    "normal_vs_modified_block_latency_statistics.csv"
)


# ============================================================
# Data loading and filtering
# ============================================================

def load_latency(
    file_path: Path,
    case_name: str,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Read the per_transaction sheet and return valid successful
    transactions in actual sending order.

    Transactions with latency greater than MAX_LATENCY_SECONDS
    are excluded from all subsequent analysis.
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

    missing_columns = required_columns.difference(
        df.columns
    )

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

    # Normalize status values.
    df["status"] = (
        df["status"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Convert block number and latency to numeric.
    df["block_number"] = pd.to_numeric(
        df["block_number"],
        errors="coerce",
    )

    df[LATENCY_COLUMN] = pd.to_numeric(
        df[LATENCY_COLUMN],
        errors="coerce",
    )

    # --------------------------------------------------------
    # First select successful transactions with required fields.
    # --------------------------------------------------------

    valid_base_mask = (
        (df["status"] == "SUCCESS")
        & df["tx_hash"].notna()
        & df["block_number"].notna()
        & df[LATENCY_COLUMN].notna()
        & np.isfinite(df[LATENCY_COLUMN])
    )

    valid_base_df = df[
        valid_base_mask
    ].copy()

    successful_valid_rows = len(valid_base_df)

    # Count latency values excluded for being negative.
    negative_latency_count = int(
        (
            valid_base_df[LATENCY_COLUMN]
            < MIN_LATENCY_SECONDS
        ).sum()
    )

    # Count latency values excluded for exceeding 1000 seconds.
    above_max_latency_count = int(
        (
            valid_base_df[LATENCY_COLUMN]
            > MAX_LATENCY_SECONDS
        ).sum()
    )

    # Apply final latency range.
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

    # --------------------------------------------------------
    # Sort by actual transaction send order.
    # --------------------------------------------------------

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

    # Create a sequential transaction number after filtering.
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
    """Print information about excluded transactions."""

    print("\n{} filtering".format(case_name))
    print("=" * 70)

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
            information[
                "invalid_or_unsuccessful_rows"
            ]
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
    """Print statistics for one experiment."""

    print("\n{}".format(statistics["case"]))
    print("=" * 70)

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
            statistics[
                "standard_deviation_seconds"
            ]
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


def print_comparison(
    normal: pd.DataFrame,
    modified: pd.DataFrame,
) -> None:
    """Print normal versus modified latency comparison."""

    normal_latency = normal[LATENCY_COLUMN]
    modified_latency = modified[LATENCY_COLUMN]

    comparisons = [
        (
            "Average",
            normal_latency.mean(),
            modified_latency.mean(),
        ),
        (
            "Median",
            normal_latency.median(),
            modified_latency.median(),
        ),
        (
            "P90",
            normal_latency.quantile(0.90),
            modified_latency.quantile(0.90),
        ),
        (
            "P95",
            normal_latency.quantile(0.95),
            modified_latency.quantile(0.95),
        ),
        (
            "P99",
            normal_latency.quantile(0.99),
            modified_latency.quantile(0.99),
        ),
    ]

    print("\nLatency comparison")
    print("=" * 105)

    print(
        "{:<10} {:>15} {:>15} {:>15} {:>16}".format(
            "Metric",
            "Normal",
            "Modified",
            "Difference",
            "Improvement",
        )
    )

    print("-" * 105)

    for (
        metric_name,
        normal_value,
        modified_value,
    ) in comparisons:

        difference = (
            normal_value - modified_value
        )

        if normal_value > 0:
            improvement_percentage = (
                difference / normal_value
            ) * 100.0
        else:
            improvement_percentage = float("nan")

        print(
            "{:<10} {:>13.3f} s {:>13.3f} s "
            "{:>13.3f} s {:>14.2f}%".format(
                metric_name,
                normal_value,
                modified_value,
                difference,
                improvement_percentage,
            )
        )


# ============================================================
# Axis calculations
# ============================================================

def calculate_combined_percentile_limit(
    normal: pd.DataFrame,
    modified: pd.DataFrame,
    percentile: float,
    padding: float,
) -> Optional[float]:
    """
    Calculate an axis limit from the combined latency
    distribution of both experiments.
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
            normal[LATENCY_COLUMN],
            modified[LATENCY_COLUMN],
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

    return float(
        percentile_value * padding
    )


def determine_cdf_x_axis_limit(
    normal: pd.DataFrame,
    modified: pd.DataFrame,
) -> Optional[float]:
    """Determine the readable CDF x-axis upper limit."""

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
        normal=normal,
        modified=modified,
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

    # Never extend past the configured maximum latency.
    return min(
        limit,
        MAX_LATENCY_SECONDS,
    )


# ============================================================
# Per-transaction latency plot
# ============================================================

def plot_transaction_latency(
    normal: pd.DataFrame,
    modified: pd.DataFrame,
) -> None:
    """Plot latency versus transaction sending order."""

    if PLOT_EVERY_N < 1:
        raise ValueError(
            "PLOT_EVERY_N must be at least 1."
        )

    normal_plot = normal.iloc[
        ::PLOT_EVERY_N
    ].copy()

    modified_plot = modified.iloc[
        ::PLOT_EVERY_N
    ].copy()

    normal_average = normal[
        LATENCY_COLUMN
    ].mean()

    modified_average = modified[
        LATENCY_COLUMN
    ].mean()

    y_axis_limit = None

    if LIMIT_TRANSACTION_Y_AXIS_TO_PERCENTILE:
        y_axis_limit = calculate_combined_percentile_limit(
            normal=normal,
            modified=modified,
            percentile=(
                TRANSACTION_Y_AXIS_PERCENTILE
            ),
            padding=TRANSACTION_Y_AXIS_PADDING,
        )

        if y_axis_limit is not None:
            y_axis_limit = min(
                y_axis_limit,
                MAX_LATENCY_SECONDS,
            )

    figure, axis = plt.subplots(
        figsize=(15, 7)
    )

    axis.plot(
        normal_plot["transaction_number"],
        normal_plot[LATENCY_COLUMN],
        marker="o",
        markersize=2.5,
        linewidth=0.9,
        label=(
            "Normal case - average {:.2f} s"
        ).format(normal_average),
    )

    axis.plot(
        modified_plot["transaction_number"],
        modified_plot[LATENCY_COLUMN],
        marker="o",
        markersize=2.5,
        linewidth=0.9,
        label=(
            "Modified solution - average {:.2f} s"
        ).format(modified_average),
    )

    axis.set_ylim(bottom=0)

    if y_axis_limit is not None:
        axis.set_ylim(
            bottom=0,
            top=y_axis_limit,
        )

    axis.set_title(
        "Per-Transaction Block Inclusion Latency "
        "(Latency <= {:.0f} Seconds)".format(
            MAX_LATENCY_SECONDS
        ),
        fontsize=16,
    )

    axis.set_xlabel(
        "Transaction Number After Filtering",
        fontsize=12,
    )

    axis.set_ylabel(
        "Block Timestamp Latency (seconds)",
        fontsize=12,
    )

    axis.grid(
        visible=True,
        linestyle="--",
        alpha=0.5,
    )

    axis.legend(
        loc="best",
        fontsize=11,
    )

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


# ============================================================
# CDF calculations
# ============================================================

def calculate_cdf(
    df: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate the empirical cumulative distribution function.
    """

    sorted_latency = np.sort(
        df[LATENCY_COLUMN]
        .dropna()
        .to_numpy(dtype=float)
    )

    if len(sorted_latency) == 0:
        raise ValueError(
            "Cannot calculate CDF because the "
            "latency data is empty."
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


def percentage_within_threshold(
    latency_values: pd.Series,
    threshold_seconds: float,
) -> float:
    """
    Calculate the percentage of transactions whose latency
    is less than or equal to a threshold.
    """

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
    normal: pd.DataFrame,
    modified: pd.DataFrame,
    thresholds: List[float],
) -> pd.DataFrame:
    """
    Create a table showing the percentage of transactions
    completed within each threshold.
    """

    normal_latency = normal[LATENCY_COLUMN]
    modified_latency = modified[LATENCY_COLUMN]

    rows = []

    for threshold in thresholds:
        if threshold < 0:
            raise ValueError(
                "CDF thresholds cannot be negative."
            )

        if threshold > MAX_LATENCY_SECONDS:
            continue

        normal_percentage = (
            percentage_within_threshold(
                normal_latency,
                threshold,
            )
        )

        modified_percentage = (
            percentage_within_threshold(
                modified_latency,
                threshold,
            )
        )

        rows.append(
            {
                "latency_threshold_seconds": (
                    float(threshold)
                ),
                "normal_within_threshold_percent": (
                    normal_percentage
                ),
                "modified_within_threshold_percent": (
                    modified_percentage
                ),
                "modified_minus_normal_percentage_points": (
                    modified_percentage
                    - normal_percentage
                ),
            }
        )

    return pd.DataFrame(rows)


def print_cdf_threshold_table(
    table: pd.DataFrame,
) -> None:
    """Print the CDF threshold comparison table."""

    print("\nCDF threshold comparison")
    print("=" * 100)

    print(
        "{:<16} {:>22} {:>22} {:>28}".format(
            "Threshold",
            "Normal within",
            "Modified within",
            "Modified - normal",
        )
    )

    print("-" * 100)

    for _, row in table.iterrows():
        print(
            "{:<16} {:>21.2f}% {:>21.2f}% "
            "{:>25.2f} pp".format(
                "{:.2f} s".format(
                    row[
                        "latency_threshold_seconds"
                    ]
                ),
                row[
                    "normal_within_threshold_percent"
                ],
                row[
                    "modified_within_threshold_percent"
                ],
                row[
                    "modified_minus_normal_percentage_points"
                ],
            )
        )


# ============================================================
# CDF graph helpers
# ============================================================

def add_percentile_reference_line(
    axis,
    value: float,
    label: str,
    y_position: float,
) -> None:
    """Add a vertical percentile line and annotation."""

    axis.axvline(
        x=value,
        linestyle=":",
        linewidth=1.0,
        alpha=0.65,
    )

    axis.text(
        value,
        y_position,
        "{}\n{:.2f} s".format(
            label,
            value,
        ),
        rotation=90,
        verticalalignment="top",
        horizontalalignment="right",
        fontsize=8,
        alpha=0.8,
    )


# ============================================================
# Readable percentile-limited CDF graph
# ============================================================

def plot_latency_cdf(
    normal: pd.DataFrame,
    modified: pd.DataFrame,
) -> None:
    """
    Plot a readable empirical CDF using only transactions with
    latency at or below MAX_LATENCY_SECONDS.
    """

    normal_latency, normal_cdf = calculate_cdf(
        normal
    )

    modified_latency, modified_cdf = calculate_cdf(
        modified
    )

    if CDF_AS_PERCENTAGE:
        normal_y = normal_cdf * 100.0
        modified_y = modified_cdf * 100.0

        y_axis_label = (
            "Cumulative Percentage of Transactions"
        )

        y_axis_maximum = 100.0

    else:
        normal_y = normal_cdf
        modified_y = modified_cdf

        y_axis_label = "Cumulative Probability"
        y_axis_maximum = 1.0

    cdf_x_axis_limit = determine_cdf_x_axis_limit(
        normal,
        modified,
    )

    normal_median = float(
        normal[LATENCY_COLUMN].median()
    )

    modified_median = float(
        modified[LATENCY_COLUMN].median()
    )

    normal_p95 = float(
        normal[LATENCY_COLUMN].quantile(0.95)
    )

    modified_p95 = float(
        modified[LATENCY_COLUMN].quantile(0.95)
    )

    normal_p99 = float(
        normal[LATENCY_COLUMN].quantile(0.99)
    )

    modified_p99 = float(
        modified[LATENCY_COLUMN].quantile(0.99)
    )

    figure, axis = plt.subplots(
        figsize=(12, 7)
    )

    axis.plot(
        normal_latency,
        normal_y,
        linewidth=2.2,
        drawstyle="steps-post",
        label=(
            "Normal case "
            "(median {:.2f} s, P95 {:.2f} s)"
        ).format(
            normal_median,
            normal_p95,
        ),
    )

    axis.plot(
        modified_latency,
        modified_y,
        linewidth=2.2,
        drawstyle="steps-post",
        label=(
            "Modified solution "
            "(median {:.2f} s, P95 {:.2f} s)"
        ).format(
            modified_median,
            modified_p95,
        ),
    )

    axis.set_xlim(left=0)

    if cdf_x_axis_limit is not None:
        axis.set_xlim(
            left=0,
            right=cdf_x_axis_limit,
        )

        normal_beyond_visible = int(
            (
                normal[LATENCY_COLUMN]
                > cdf_x_axis_limit
            ).sum()
        )

        modified_beyond_visible = int(
            (
                modified[LATENCY_COLUMN]
                > cdf_x_axis_limit
            ).sum()
        )

        print("\nCDF visible range")
        print("=" * 70)

        print(
            "Visible x-axis upper limit: "
            "{:.3f} seconds".format(
                cdf_x_axis_limit
            )
        )

        print(
            "Normal values beyond visible x-axis  : {:,}".format(
                normal_beyond_visible
            )
        )

        print(
            "Modified values beyond visible x-axis: {:,}".format(
                modified_beyond_visible
            )
        )

        print(
            "These values remain included in the CDF because "
            "they are at or below {:.0f} seconds.".format(
                MAX_LATENCY_SECONDS
            )
        )

    axis.set_ylim(
        bottom=0,
        top=y_axis_maximum,
    )

    if SHOW_CDF_PERCENTILE_LINES:
        if CDF_AS_PERCENTAGE:
            reference_values = [
                (
                    normal_median,
                    "Normal median",
                    78.0,
                ),
                (
                    modified_median,
                    "Modified median",
                    64.0,
                ),
                (
                    normal_p95,
                    "Normal P95",
                    99.0,
                ),
                (
                    modified_p95,
                    "Modified P95",
                    86.0,
                ),
            ]
        else:
            reference_values = [
                (
                    normal_median,
                    "Normal median",
                    0.78,
                ),
                (
                    modified_median,
                    "Modified median",
                    0.64,
                ),
                (
                    normal_p95,
                    "Normal P95",
                    0.99,
                ),
                (
                    modified_p95,
                    "Modified P95",
                    0.86,
                ),
            ]

        for value, label, y_position in reference_values:
            if (
                cdf_x_axis_limit is None
                or value <= cdf_x_axis_limit
            ):
                add_percentile_reference_line(
                    axis=axis,
                    value=value,
                    label=label,
                    y_position=y_position,
                )

    axis.set_title(
        "CDF of Block Inclusion Latency "
        "(Latency <= {:.0f} Seconds)".format(
            MAX_LATENCY_SECONDS
        ),
        fontsize=16,
    )

    axis.set_xlabel(
        "Block Timestamp Latency (seconds)",
        fontsize=12,
    )

    axis.set_ylabel(
        y_axis_label,
        fontsize=12,
    )

    axis.grid(
        visible=True,
        linestyle="--",
        alpha=0.5,
    )

    axis.legend(
        loc="lower right",
        fontsize=10,
    )

    p99_text = (
        "Normal P99: {:.2f} s\n"
        "Modified P99: {:.2f} s"
    ).format(
        normal_p99,
        modified_p99,
    )

    axis.text(
        0.985,
        0.20,
        p99_text,
        transform=axis.transAxes,
        horizontalalignment="right",
        verticalalignment="top",
        fontsize=9,
        bbox={
            "boxstyle": "round",
            "alpha": 0.75,
        },
    )

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

def plot_full_range_latency_cdf(
    normal: pd.DataFrame,
    modified: pd.DataFrame,
) -> None:
    """
    Plot the complete CDF range after excluding values greater
    than MAX_LATENCY_SECONDS.
    """

    normal_latency, normal_cdf = calculate_cdf(
        normal
    )

    modified_latency, modified_cdf = calculate_cdf(
        modified
    )

    if CDF_AS_PERCENTAGE:
        normal_y = normal_cdf * 100.0
        modified_y = modified_cdf * 100.0

        y_axis_label = (
            "Cumulative Percentage of Transactions"
        )

        y_axis_maximum = 100.0

    else:
        normal_y = normal_cdf
        modified_y = modified_cdf

        y_axis_label = "Cumulative Probability"
        y_axis_maximum = 1.0

    figure, axis = plt.subplots(
        figsize=(12, 7)
    )

    axis.plot(
        normal_latency,
        normal_y,
        linewidth=2.0,
        drawstyle="steps-post",
        label="Normal case",
    )

    axis.plot(
        modified_latency,
        modified_y,
        linewidth=2.0,
        drawstyle="steps-post",
        label="Modified solution",
    )

    axis.set_xlim(
        left=0,
        right=MAX_LATENCY_SECONDS,
    )

    axis.set_ylim(
        bottom=0,
        top=y_axis_maximum,
    )

    axis.set_title(
        "CDF of Block Inclusion Latency — "
        "Complete Filtered Range",
        fontsize=16,
    )

    axis.set_xlabel(
        "Block Timestamp Latency (seconds)",
        fontsize=12,
    )

    axis.set_ylabel(
        y_axis_label,
        fontsize=12,
    )

    axis.grid(
        visible=True,
        linestyle="--",
        alpha=0.5,
    )

    axis.legend(
        loc="lower right",
        fontsize=10,
    )

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
            "Normal case",
        )

        modified, modified_filter_information = load_latency(
            MODIFIED_FILE,
            "Modified solution",
        )

        print_filter_information(
            "Normal case",
            NORMAL_FILE,
            normal_filter_information,
        )

        print_filter_information(
            "Modified solution",
            MODIFIED_FILE,
            modified_filter_information,
        )

        normal_statistics = calculate_statistics(
            "Normal case",
            normal,
            normal_filter_information,
        )

        modified_statistics = calculate_statistics(
            "Modified solution",
            modified,
            modified_filter_information,
        )

        print_statistics(
            normal_statistics
        )

        print_statistics(
            modified_statistics
        )

        print_comparison(
            normal,
            modified,
        )

        # Save statistics.
        statistics_table = pd.DataFrame(
            [
                normal_statistics,
                modified_statistics,
            ]
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

        # Create and save the CDF threshold table.
        cdf_threshold_table = (
            create_cdf_threshold_table(
                normal=normal,
                modified=modified,
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
            normal,
            modified,
        )

        plot_latency_cdf(
            normal,
            modified,
        )

        plot_full_range_latency_cdf(
            normal,
            modified,
        )

        print("\nCompleted successfully.")
        print("=" * 70)

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