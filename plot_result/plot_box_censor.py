#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# Configuration
# ============================================================

MODIFIED_FILE = (
    "replay_phased_fixed_metrics_replay_tx_v1_sm_modified_censor.xlsx"
)

NORMAL_FILE = (
    "replay_phased_fixed_metrics_replay_tx_v1_sm_normal_censor.xlsx"
)

SHEET_NAME = "per_transaction"
LATENCY_COLUMN = "block_timestamp_latency_sec"

OUTPUT_FILE = (
    "selected_100_addresses_modified_vs_normal_latency_boxplot.png"
)

TITLE_FONT_SIZE = 22
AXIS_LABEL_FONT_SIZE = 20
TICK_FONT_SIZE = 17
LEGEND_FONT_SIZE = 15


# ============================================================
# Selected 100 TO addresses
# ============================================================

TARGET_ADDRESSES = [
    "0x857679d69fE50E7B722f94aCd2629d80C355163d",
    "0x52310B1585E2dBCBAeAd85da535e6700Ab28fB57",
    "0xd036CbeCbF0102138E1a93a2F9418e267DD0F92c",
    "0x5caDCF74A14a6aa67e95E418625b82831b241b58",
    "0x33ba46C5EEFFda843e356e9d24cd02DA35D8f9F1",
    "0x343Cf59a43BD7DDD38B7236a478139A86a26222b",
    "0x636d585F40A7a445dA7403FCf92E03F89dc3eBd0",
    "0x42Baf1f659D765C65ADE5BB7E08eb2C680360d9d",
    "0x9E32b13ce7f2E80A01932B42553652E053D6ed8e",
    "0x70A237b702E9BaffbbF60eeb19C875dE3fF071e4",
    "0x4fFf0C5eCFfD952cdab52A1Eb860fD28cBd665d6",
    "0x762340B8a40Cdd5BFC3eDD94265899FDa345D0E3",
    "0x48FDCC7839CC7Fb7a9cfA429a873d02A56a72c00",
    "0xa87328808aFc62b276A67Dff09D2DBE3849d02D8",
    "0xdAf1695c41327b61B9b9965Ac6A5843A3198cf07",
    "0x7Be8076f4EA4A4AD08075C2508e481d6C946D12b",
    "0x9C070027cdC9dc8F82416B2e5314E11DFb4FE3CD",
    "0xDDFba7c0FB09f3cD8cA8e7d237ABD2673557Ae7b",
    "0xb951DA3870f7b7d1e3f9249c18e93D5CC5c3565c",
    "0x02feC6966AaE34777c0f01CBF6513D5621742b75",
    "0x4025ee6512DBbda97049Bcf5AA5D38C54aF6bE8a",
    "0x2A6d6a082C410a195157EC4caf67CB9fD718f087",
    "0x1A3496C18d558bd9C6C8f609E1B129f67AB08163",
    "0xc25a272A4D2Ef4c80173187Bf69f4238c5b6564f",
    "0x9347310340c7cb023A10a193e57fcdEF246a5189",
    "0x328a268b191ef593B72498a9e8a481C086EB21be",
    "0x0b1172BB30708E59b89C514AB9823Fd93dD19036",
    "0x1E6d8170B7450297F9eEBe77e8A22210A528c471",
    "0x20F780A973856B93f63670377900C1d2a50a77c4",
    "0xC7C962e44316E0C052448A0fdd1da15EA24fa9a9",
    "0xD404c291F1AC0cFeC369361f4511715E927cabDB",
    "0xF1F3ca6268f330fDa08418db12171c3173eE39C9",
    "0x59A828B8B1fC885D8e669F53098a532f96443e50",
    "0x37f0d86EdD00c4df59017ee46F848886D1104126",
    "0x7b448C4fD2906706a4b69BfEbd5a74409460965a",
    "0x80160739D7f9535FCd88F3052B178a8185665EAc",
    "0x2c6b47D107E3b40Fb576d2F347056c8D795719e4",
    "0x2EDfFbc62C3dfFD2a8FbAE3cd83A986B5bbB5495",
    "0x0367FFd1Abf5066c61d3BC49D75819c24F0F6B5e",
    "0xE47b8C21a641567420c30221B3F2c866E3a14633",
    "0x6aF49606D941cdA32de1Ee94397dc821ceB09DAc",
    "0x7273d1671fCd37Ef5b949Ebf88234AA9c3E43957",
    "0x5E7eBE2599b7a336091665421c3582D151D510d0",
    "0x8d2feA76b699a16d93496f76be833c832b9269aE",
    "0xd7Be8A4BB3Bcb47d37F6B54dA399e208720b3feA",
    "0x8201E54811746E8387B02A000c4d8eb34896B998",
    "0x20807Cf61AD17c31837776fA39847A2Fa1839E81",
    "0x3ee18B2214AFF97000D974cf647E7C347E8fa585",
    "0xe2970CD6B1bEC6bd0f31B181EFd77DA6368a33d1",
    "0x9F9c8ec3534c3cE16F928381372BfbFBFb9F4D24",
    "0xC7BFec6FF6D581187C704dE86e86506EB171A019",
    "0x8400D94A5cb0fa0D041a3788e395285d61c9ee5e",
    "0x859a5d9aD4eb04d8bd9F91D7923857f2DfD0cc51",
    "0x4E5B2e1dc63F6b91cb6Cd759936495434C7e972F",
    "0x5DcD7D85Ac0EB27a12E8b458E7D2c8c7BF637862",
    "0x2b82C78AE3c973c1Ce39D63b5d63c6CB8DB199EA",
    "0x29e378fc25bdD09Ff74389845B297Fd97dcCf242",
    "0x3e08213Ab311813F1dCAFE2644D3c1374cd37deE",
    "0x6Fe728f8b5cC9aD03497E010F038b1d872cC45d9",
    "0x00000000000000447e69651d841bD8D104Bed493",
    "0x690F188554DdEa41987cb39989b6F15dd9F6d66F",
    "0xbEd2135c950494Bcc2cDc915FC95A09D17b5DC10",
    "0x669c01CAF0eDcaD7c2b8Dc771474aD937A7CA4AF",
    "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
    "0x826BB51954b93f1972A3472aBf6DCd6672aDB462",
    "0xEDbcCECFC905701451c7D345CFCee68EF32A94d5",
    "0x5550D13389bB70F45fCeF58f19f6b6e87F6e747d",
    "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    "0xceFe986EA0A935c597e6A497138c1f52e4b985Be",
    "0xd7bB18da2Fc92eD97ED189e56B3071d5C0FFD207",
    "0xc15AC9D42aD03C4F5bbDa5d458eAf8340509E520",
    "0x8EB0123ae0bcbCdcA144DbB800fC3F69665a38db",
    "0x31CC70C6AE6978a00a7B2287893379898530746a",
    "0x3D60D4919A6476D882d5A63d732291F82edE5aa8",
    "0x89847Ff76F658d07188F5C3af723d325F40C4ea7",
    "0x6Ced9A7Adc0084513b7CCBB4EB6ae968FaEAb526",
    "0x2D9F5d2763D7c9fB8B3237C133d599bAdCC4f0B1",
    "0xD101dCC414F310268c37eEb4cD376CcFA507F571",
    "0xC2c862322E9c97D6244a3506655DA95F05246Fd8",
    "0x10718A931DC4dbD7DBA0fCC8b1c8D409Af8f1D58",
    "0x9B90D30ff7C8ED856d937aCBf4a98F423F76B810",
    "0xF93be1F6c7336E78F4A3859a9d01F44595a82Ab4",
    "0xf3eBE80b72f66C11e09865d782975BD57577DaE4",
    "0x373f8b25e91BAa8E04E086ff1B786777c341b0B8",
    "0xcAe798C0C6958df8299dF4f13726da433B8BA7bA",
    "0x6c6EE5e31d828De241282B9606C8e98Ea48526E2",
    "0x2Ec705D306b51e486B1bC0D6ebEE708E0661ADd1",
    "0x495f947276749Ce646f68AC8c248420045cb7b5e",
    "0x379448d48Fc6e3954DE03B52cfC5FcB288506AB8",
    "0x35AD5B51b4D2661F90520BEbC4f7aC8B9Eb76211",
    "0x5650ba5807a079AA1c5Bf230B8F2E6067d8C853A",
    "0xc9848F4bDFEA472C6580622745C65A81AB906c70",
    "0x000000000060C4Ca14CfC4325359062ace33Fe3D",
    "0x0B7B9504f57e45D2825A8D4e3ca5E52B45087a8B",
    "0x29d7139271398D0C2E22523fDA06e023DcB07F8f",
    "0x8CdFf319bD9DF8Cbf2e773FCCB8cA8A067f82E6A",
    "0xDD6Dce66F11D2460B3b4A8Be8174749BC8d5e403",
    "0x2da10A1e27bF85cEdD8FFb1AbBe97e53391C0295",
    "0x29A3B78Ae02dCC885D885B9945846B8718460E7b",
    "0xfAE87d6657c7650bBD2E8B41FEAE2051e604AcB3"

    # --------------------------------------------------------
    # Paste the remaining 90 addresses here
    # --------------------------------------------------------
]


# Use a set for faster lookup and normalize case
TARGET_ADDRESSES = {
    address.strip().lower()
    for address in TARGET_ADDRESSES
}


print(
    "Number of target addresses: {:,}".format(
        len(TARGET_ADDRESSES)
    )
)


# ============================================================
# Load + filter
# ============================================================

def load_target_address_latency(
    file_path,
    case_name,
):

    print()
    print("=" * 80)
    print("Loading {}".format(case_name))
    print("=" * 80)

    df = pd.read_excel(
        file_path,
        sheet_name=SHEET_NAME,
        engine="openpyxl",

        # Read only columns needed for this experiment
        usecols=[
            "tx_hash",
            "to",
            "contract_address_mapped",
            "successful_call_reused",
            "status",
            LATENCY_COLUMN,
        ],
    )

    print(
        "Total rows loaded                 : {:,}".format(
            len(df)
        )
    )

    # ========================================================
    # Normalize TO address
    # ========================================================

    df["to_normalized"] = (
        df["to"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # ========================================================
    # Normalize booleans
    # ========================================================

    df["contract_address_mapped"] = (
        df["contract_address_mapped"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )

    df["successful_call_reused"] = (
        df["successful_call_reused"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )

    # ========================================================
    # Normalize status
    # ========================================================

    df["status"] = (
        df["status"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # ========================================================
    # Convert latency to numeric
    # ========================================================

    df[LATENCY_COLUMN] = pd.to_numeric(
        df[LATENCY_COLUMN],
        errors="coerce",
    )

    # ========================================================
    # Step 1: transactions to selected 100 addresses
    # ========================================================

    target_df = df[
        df["to_normalized"].isin(
            TARGET_ADDRESSES
        )
    ].copy()

    print(
        "Rows to selected addresses        : {:,}".format(
            len(target_df)
        )
    )

    print(
        "Selected addresses actually found : {:,}".format(
            target_df["to_normalized"].nunique()
        )
    )

    # ========================================================
    # Step 2: Apply all qualifying conditions
    # ========================================================

    filtered = target_df[
        # (target_df["contract_address_mapped"] == True)
        # & (target_df["successful_call_reused"] == True)
        (target_df["status"] == "SUCCESS")
        & (target_df[LATENCY_COLUMN].notna())
        & (target_df[LATENCY_COLUMN] >= 0)
    ].copy()

    print(
        "Qualifying transactions           : {:,}".format(
            len(filtered)
        )
    )

    print(
        "Addresses with qualifying txs      : {:,}".format(
            filtered["to_normalized"].nunique()
        )
    )

    print("\n--- FILTER DIAGNOSTICS ---")



    print("Target rows:", len(target_df))

    print(
        "contract_address_mapped == True:",
        (target_df["contract_address_mapped"] == True).sum()
    )

    print(
        "successful_call_reused == True:",
        (target_df["successful_call_reused"] == True).sum()
    )

    print(
        "status == SUCCESS:",
        (target_df["status"] == "SUCCESS").sum()
    )

    print(
        "latency not NaN:",
        target_df[LATENCY_COLUMN].notna().sum()
    )

    print(
        "latency >= 0:",
        (target_df[LATENCY_COLUMN] >= 0).sum()
    )

    print("\nContract mapped values:")
    print(target_df["contract_address_mapped"].value_counts(dropna=False))

    print("\nSuccessful call reused values:")
    print(target_df["successful_call_reused"].value_counts(dropna=False))

    print("\nStatus values:")
    print(target_df["status"].value_counts(dropna=False))

    print("\nLatency description:")
    print(target_df[LATENCY_COLUMN].describe())

    # ========================================================
    # Check missing target addresses
    # ========================================================

    found_addresses = set(
        filtered["to_normalized"].unique()
    )

    missing_addresses = (
        TARGET_ADDRESSES - found_addresses
    )

    print(
        "Target addresses with no qualifying tx: {:,}".format(
            len(missing_addresses)
        )
    )

    if len(missing_addresses) > 0:

        print()
        print(
            "Addresses with no qualifying transactions:"
        )

        for address in sorted(
            missing_addresses
        ):
            print(
                "  {}".format(address)
            )

    return filtered


# ============================================================
# Load both protocols
# ============================================================

modified_filtered = load_target_address_latency(
    MODIFIED_FILE,
    "Modified Protocol",
)

normal_filtered = load_target_address_latency(
    NORMAL_FILE,
    "PBS Normal",
)


# ============================================================
# Latency values
# ============================================================

modified_values = modified_filtered[
    LATENCY_COLUMN
].copy()

normal_values = normal_filtered[
    LATENCY_COLUMN
].copy()


# ============================================================
# Statistics
# ============================================================

def calculate_statistics(values):

    return {
        "count": int(len(values)),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "median": float(values.median()),
        "minimum": float(values.min()),
        "q1": float(values.quantile(0.25)),
        "q3": float(values.quantile(0.75)),
        "maximum": float(values.max()),
        "p90": float(values.quantile(0.90)),
        "p95": float(values.quantile(0.95)),
        "p99": float(values.quantile(0.99)),
    }


modified_stats = calculate_statistics(
    modified_values
)

normal_stats = calculate_statistics(
    normal_values
)


# ============================================================
# Print statistics helper
# ============================================================

def print_statistics(
    name,
    stats,
):

    print()
    print("=" * 80)
    print(name)
    print("=" * 80)

    print(
        "Transactions       : {:,}".format(
            stats["count"]
        )
    )

    print(
        "Average            : {:.3f} seconds".format(
            stats["mean"]
        )
    )

    print(
        "Standard deviation : {:.3f} seconds".format(
            stats["std"]
        )
    )

    print(
        "Median             : {:.3f} seconds".format(
            stats["median"]
        )
    )

    print(
        "Minimum            : {:.3f} seconds".format(
            stats["minimum"]
        )
    )

    print(
        "Q1                 : {:.3f} seconds".format(
            stats["q1"]
        )
    )

    print(
        "Q3                 : {:.3f} seconds".format(
            stats["q3"]
        )
    )

    print(
        "P90                : {:.3f} seconds".format(
            stats["p90"]
        )
    )

    print(
        "P95                : {:.3f} seconds".format(
            stats["p95"]
        )
    )

    print(
        "P99                : {:.3f} seconds".format(
            stats["p99"]
        )
    )

    print(
        "Maximum            : {:.3f} seconds".format(
            stats["maximum"]
        )
    )


print_statistics(
    "MODIFIED PROTOCOL - SELECTED 100 ADDRESSES",
    modified_stats,
)

print_statistics(
    "PBS NORMAL - SELECTED 100 ADDRESSES",
    normal_stats,
)


# ============================================================
# Comparison
# ============================================================

mean_reduction = (
    normal_stats["mean"]
    - modified_stats["mean"]
)

if normal_stats["mean"] > 0:

    improvement_percent = (
        mean_reduction
        / normal_stats["mean"]
        * 100.0
    )

else:

    improvement_percent = float("nan")


print()
print("=" * 80)
print("COMPARISON")
print("=" * 80)

print(
    "Modified average    : {:.3f} s".format(
        modified_stats["mean"]
    )
)

print(
    "PBS Normal average  : {:.3f} s".format(
        normal_stats["mean"]
    )
)

print(
    "Mean reduction      : {:.3f} s".format(
        mean_reduction
    )
)

print(
    "Improvement         : {:.2f}%".format(
        improvement_percent
    )
)

print(
    "Modified std dev    : {:.3f} s".format(
        modified_stats["std"]
    )
)

print(
    "PBS Normal std dev  : {:.3f} s".format(
        normal_stats["std"]
    )
)


# ============================================================
# Combined box plot
# ============================================================

figure, axis = plt.subplots(
    figsize=(11, 8)
)


axis.boxplot(
    [
        modified_values,
        normal_values,
    ],
    widths=0.50,
    showmeans=False,
    showfliers=True,
    whis=1.5,
)


# ============================================================
# Mean ± standard deviation
# ============================================================

axis.errorbar(
    [1, 2],
    [
        modified_stats["mean"],
        normal_stats["mean"],
    ],
    yerr=[
        modified_stats["std"],
        normal_stats["std"],
    ],
    fmt="o",
    capsize=8,
    linewidth=2,
    markersize=7,
    label="Mean ± Standard Deviation",
)


# ============================================================
# Labels
# ============================================================

axis.set_title(
    "Latency Distribution for Transactions to "
    "Selected 100 Addresses",
    fontsize=TITLE_FONT_SIZE,
    pad=15,
)


axis.set_ylabel(
    "Block Timestamp Latency (seconds)",
    fontsize=AXIS_LABEL_FONT_SIZE,
)


axis.set_xlabel(
    "Protocol",
    fontsize=AXIS_LABEL_FONT_SIZE,
)


axis.set_xticks(
    [1, 2]
)


axis.set_xticklabels(
    [
        "Modified Protocol",
        "PBS Normal",
    ],
    fontsize=TICK_FONT_SIZE,
)


axis.tick_params(
    axis="y",
    labelsize=TICK_FONT_SIZE,
)


axis.grid(
    axis="y",
    linestyle="--",
    alpha=0.5,
)


# ============================================================
# Statistics box
# ============================================================

statistics_text = (
    "Modified Protocol\n"
    "N = {:,}\n"
    "Mean = {:.2f} s\n"
    "Std Dev = {:.2f} s\n"
    "Median = {:.2f} s\n"
    "P95 = {:.2f} s\n\n"
    "PBS Normal\n"
    "N = {:,}\n"
    "Mean = {:.2f} s\n"
    "Std Dev = {:.2f} s\n"
    "Median = {:.2f} s\n"
    "P95 = {:.2f} s"
).format(
    modified_stats["count"],
    modified_stats["mean"],
    modified_stats["std"],
    modified_stats["median"],
    modified_stats["p95"],

    normal_stats["count"],
    normal_stats["mean"],
    normal_stats["std"],
    normal_stats["median"],
    normal_stats["p95"],
)


axis.text(
    1.02,
    0.97,
    statistics_text,
    transform=axis.transAxes,
    fontsize=14,
    verticalalignment="top",
    bbox=dict(
        boxstyle="round",
        alpha=0.15,
    ),
)


axis.legend(
    loc="upper left",
    fontsize=LEGEND_FONT_SIZE,
)


figure.tight_layout()


figure.savefig(
    OUTPUT_FILE,
    dpi=300,
    bbox_inches="tight",
)


# ============================================================
# Save filtered transaction lists
# ============================================================

modified_filtered.to_csv(
    "modified_selected_100_addresses_transactions.csv",
    index=False,
)

normal_filtered.to_csv(
    "normal_selected_100_addresses_transactions.csv",
    index=False,
)


print()
print("=" * 80)
print("Plot saved:")
print(OUTPUT_FILE)

print()
print("Filtered transaction data saved:")
print(
    "modified_selected_100_addresses_transactions.csv"
)
print(
    "normal_selected_100_addresses_transactions.csv"
)
print("=" * 80)


plt.close(
    figure
)
