#!/usr/bin/env python3
"""
Replay Ethereum transactions in clean phases:

PHASE 1   Read CSV
PHASE 2   Create/resolve all sender/receiver accounts
PHASE 3   Send funding tx to all required sender accounts and store hashes
PHASE 3.5 Wait for all funding receipts
PHASE 4   Start replay timer
PHASE 5   Send replay tx at TX_PER_SECOND
PHASE 6   Collect receipts/block timestamps
PHASE 7   Calculate latency and write Excel report

"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from web3 import Web3
from web3.exceptions import TransactionNotFound

csv.field_size_limit(sys.maxsize)

# ============================================================
# TOP 10 MAINNET CONTRACT -> LOCAL CONTRACT
# ============================================================

CONTRACT_ADDRESS_MAP = {
  "0xdac17f958d2ee523a2206206994597c13d831ec7":
        "0xb4B46bdAA835F8E4b4d8e208B6559cD267851051",

    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad":
        "0x17435ccE3d1B4fA2e5f8A08eD921D57C6762A180",

    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48":
        "0x0643D39D47CF0ea95Dbea69Bf11a7F8C4Bc34968",

    "0xd5ceb3e748ef3296a68b930c1810c5884278410e":
        "0x9f9F5Fd89ad648f2C000C954d8d9C87743243eC5",

    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2":
        "0x8F0342A7060e76dfc7F6e9dEbfAD9b9eC919952c",

    "0x32400084c286cf3e17e7b677ea9583e60a000324":
        "0x00c042C4D5D913277CE16611a2ce6e9003554aD5",

    "0x881d40237659c251811cec9c364ef91dc08d300c":
        "0x9fCF7D13d10dEdF17d0f24C62f0cf4ED462f65b7",

    "0x29469395eaf6f95920e59f858042f0e28d98a20b":
        "0x9f5eaC3d8e082f47631F1551F1343F23cd427162",

    "0xdef1c0ded9bec7f1a1670819833240f027b25eff":
        "0x72bCbB3f339aF622c28a26488Eed9097a2977404",

    "0x00000000000000adc04c56bf30ac9d3c0aaf14dc":
        "0xEE0fCB8E5cCAD0b4197BAabd633333886f5C364d"

}

CONTRACT_ADDRESS_MAP = {
    k.lower(): Web3.to_checksum_address(v)
    for k, v in CONTRACT_ADDRESS_MAP.items()
}

# ============================================================
# CONTRACT FUNCTION SELECTORS
# ============================================================

SELECTOR_TRANSFER = "0xa9059cbb"
SELECTOR_TRANSFER_FROM = "0x23b872dd"
SELECTOR_APPROVE = "0x095ea7b3"

SELECTOR_WETH_DEPOSIT = "0xd0e30db0"
SELECTOR_WETH_WITHDRAW = "0x2e1a7d4d"

USDT_MAINNET = (
    "0xdac17f958d2ee523a2206206994597c13d831ec7"
)

WETH_MAINNET = (
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
)

# =========================
# SYSTEM PARAMETERS
# =========================
GETH_URL = os.getenv("GETH_URL", "http://el-01-geth-lighthouse:8545")
MASTER_PRIVATE_KEY = os.getenv(
    "MASTER_PRIVATE_KEY",
    "bcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31",
)


CSV_FILE = os.getenv("CSV_FILE", "mempool.csv")
# PRIVATE_KEYS_FILE = os.getenv("PRIVATE_KEYS_FILE", "wallet_private_keys.json")
SCRIPT_ID = os.path.basename(__file__).replace(".py", "")
PRIVATE_KEYS_FILE = f"wallet_private_keys_{SCRIPT_ID}.json"
OUTPUT_XLSX = os.getenv("OUTPUT_XLSX", f"replay_phased_fixed_metrics_{SCRIPT_ID}.xlsx")
# ACCOUNT_MAP_FILE = os.getenv("ACCOUNT_MAP_FILE", "csv_sender_replacement_map.json")
ACCOUNT_MAP_FILE = (
    f"csv_sender_replacement_map_{SCRIPT_ID}.json"
)

RAW_TX_FILE = os.getenv(
    "RAW_TX_FILE",
    f"transactions_{SCRIPT_ID}.txt"
)

START_INDEX = int(os.getenv("START_INDEX", "0"))
LIMIT_ROWS = int(os.getenv("LIMIT_ROWS", "38000"))

# Example: TX_PER_SECOND=10 means wait 1/10 = 0.1 sec between replay tx sends.
TX_PER_SECOND = float(os.getenv("TX_PER_SECOND", "10"))
SEND_INTERVAL_SEC = 1.0 / TX_PER_SECOND if TX_PER_SECOND > 0 else 0.0



GAS_LIMIT = int(os.getenv("GAS_LIMIT", "21000"))
GAS_PRICE_GWEI = float(os.getenv("GAS_PRICE_GWEI", "10"))
INITIAL_FUND_ETH = float(os.getenv("INITIAL_FUND_ETH", "0.05"))
FUNDING_EXTRA_ETH = float(os.getenv("FUNDING_EXTRA_ETH", "0.01"))

# Funding phase settings.
FUNDING_SEND_INTERVAL_SEC = float(os.getenv("FUNDING_SEND_INTERVAL_SEC", "0.05"))
FUNDING_RECEIPT_TIMEOUT_SEC = int(os.getenv("FUNDING_RECEIPT_TIMEOUT_SEC", "600"))
FUNDING_RECEIPT_POLL_SEC = float(os.getenv("FUNDING_RECEIPT_POLL_SEC", "1"))

# Replay receipt/finality polling after all replay transactions are sent.
RECEIPT_TIMEOUT_SEC = int(os.getenv("RECEIPT_TIMEOUT_SEC", "600"))
RECEIPT_POLL_SEC = float(os.getenv("RECEIPT_POLL_SEC", "1"))
WAIT_FOR_FINALIZATION = os.getenv("WAIT_FOR_FINALIZATION", "false").lower() in ("1", "true", "yes")
FINALITY_TIMEOUT_SEC = int(os.getenv("FINALITY_TIMEOUT_SEC", "900"))
FINALITY_POLL_SEC = float(os.getenv("FINALITY_POLL_SEC", "2"))

web3 = Web3(Web3.HTTPProvider(GETH_URL))
if not web3.is_connected():
    raise RuntimeError(f"Geth is not connected: {GETH_URL}")

master_account = web3.eth.account.from_key(MASTER_PRIVATE_KEY)
master_address = Web3.to_checksum_address(master_account.address)
chain_id = int(web3.eth.chain_id)

print(f"[INFO] Connected to Geth: {GETH_URL}")
print(f"[INFO] Chain ID: {chain_id}")
print(f"[INFO] Master wallet: {master_address}")
print(f"[INFO] TX_PER_SECOND={TX_PER_SECOND}, SEND_INTERVAL_SEC={SEND_INTERVAL_SEC}")

def print_top10_contract_requirements(
    replay_plan: List[Dict[str, Any]]
) -> None:

    print()
    print("=" * 80)
    print("TOP-10 SMART CONTRACT CALL ANALYSIS")
    print("=" * 80)

    stats = {}

    for plan in replay_plan:

        if not plan.get(
            "contract_address_mapped",
            False
        ):
            continue

        original = str(
            plan.get("original_to", "")
        ).lower()

        data = str(
            plan.get("input", "0x")
        )

        selector = calldata_selector(
            data
        )

        value = int(
            plan.get("value_wei", 0)
        )

        if original not in stats:
            stats[original] = {
                "calls": 0,
                "value_wei": 0,
                "selectors": {},
                "senders": set(),
            }

        stats[original]["calls"] += 1
        stats[original]["value_wei"] += value
        stats[original]["senders"].add(
            plan["from"]
        )

        stats[original]["selectors"][selector] = (
            stats[original]["selectors"].get(
                selector,
                0
            )
            + 1
        )

    for address, info in stats.items():

        print()
        print("-" * 80)

        print(
            f"Contract: {address}"
        )

        print(
            f"Total calls: {info['calls']}"
        )

        print(
            f"Unique replay senders: "
            f"{len(info['senders'])}"
        )

        print(
            f"Total ETH value: "
            f"{web3.from_wei(info['value_wei'], 'ether')}"
        )

        print("Function selectors:")

        for selector, count in sorted(
            info["selectors"].items(),
            key=lambda x: x[1],
            reverse=True
        ):

            print(
                f"    {selector}: {count}"
            )

    print()
    print("=" * 80)

# ============================================================
# MINIMAL TOKEN ABIs FOR STATE PREPARATION
# ============================================================

ERC20_ABI = [
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "_owner",
                "type": "address"
            }
        ],
        "name": "balanceOf",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },

    {
        "inputs": [
            {
                "internalType": "address",
                "name": "_to",
                "type": "address"
            },
            {
                "internalType": "uint256",
                "name": "_value",
                "type": "uint256"
            }
        ],
        "name": "transfer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]


WETH_ABI = [
    {
        "inputs": [
            {
                "name": "",
                "type": "address"
            }
        ],
        "name": "balanceOf",
        "outputs": [
            {
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },

    {
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },

    {
        "inputs": [
            {
                "name": "dst",
                "type": "address"
            },
            {
                "name": "wad",
                "type": "uint256"
            }
        ],
        "name": "transfer",
        "outputs": [
            {
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]


def parse_input_data(value: Any) -> str:
    if pd.isna(value):
        return "0x"

    data = str(value).strip()

    if not data:
        return "0x"

    if not data.startswith("0x"):
        data = "0x" + data

    return data

def calldata_selector(data: str) -> str:
    if not data:
        return "0x"

    data = str(data).lower()

    if len(data) < 10:
        return data

    return data[:10]


def decode_uint256_word(
    data: str,
    word_index: int
) -> int:
    """
    Decode a uint256 ABI argument.

    word_index=0 -> first argument
    word_index=1 -> second argument
    """

    clean = data[2:] if data.startswith("0x") else data

    # 4-byte function selector = 8 hex characters
    start = 8 + word_index * 64
    end = start + 64

    if len(clean) < end:
        raise ValueError(
            f"Calldata too short: word={word_index}"
        )

    return int(
        clean[start:end],
        16
    )


def decode_address_word(
    data: str,
    word_index: int
) -> str:

    clean = data[2:] if data.startswith("0x") else data

    start = 8 + word_index * 64
    end = start + 64

    if len(clean) < end:
        raise ValueError(
            f"Calldata too short: word={word_index}"
        )

    word = clean[start:end]

    return Web3.to_checksum_address(
        "0x" + word[-40:]
    )

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_json_file(path: str, default: Any) -> Any:
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json_file(path: str, data: Any) -> None:
    # tmp = path + ".tmp"
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, path)


private_keys: Dict[str, str] = load_json_file(PRIVATE_KEYS_FILE, {})
# Maps original CSV sender address or synthetic key to generated replacement sender address.
csv_sender_map: Dict[str, str] = load_json_file(ACCOUNT_MAP_FILE, {})


def save_private_keys() -> None:
    save_json_file(PRIVATE_KEYS_FILE, private_keys)


def save_sender_map() -> None:
    save_json_file(ACCOUNT_MAP_FILE, csv_sender_map)


def normalize_status(status: Any) -> bool:
    return status in [1, True, "1", "0x1"]


def get_pending_nonce(address: str) -> int:
    return int(web3.eth.get_transaction_count(Web3.to_checksum_address(address), "pending"))


def parse_address(value: Any) -> Optional[str]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or not web3.is_address(text):
        return None
    return Web3.to_checksum_address(text)


def parse_int(value: Any, default: int) -> int:
    if pd.isna(value):
        return default
    try:
        return int(value)
    except Exception:
        return default


def create_account(label: str = "account") -> Tuple[str, str]:
    acct = web3.eth.account.create()
    address = Web3.to_checksum_address(acct.address)
    private_keys[address] = acct.key.hex()
    save_private_keys()
    print(f"[ACCOUNT] Created {label}: {address}")
    return address, acct.key.hex()


def get_or_create_replacement_sender(csv_sender: Optional[str], row_number: int) -> Tuple[str, str, str]:
    """
    Return a signable sender address/private key.

    If CSV sender has a private key, use it.
    If CSV sender has no private key, map that CSV sender to exactly one generated account.
    If CSV sender is invalid/missing, map a synthetic row key to one generated account for that row.
    """
    if csv_sender and csv_sender in private_keys:
        return csv_sender, private_keys[csv_sender], "csv_sender_with_private_key"

    if csv_sender:
        map_key = csv_sender
    else:
        # Invalid/missing sender has no stable identity, so use row-specific generated account.
        map_key = f"__missing_sender_row_{row_number}"

    if map_key in csv_sender_map:
        replacement = Web3.to_checksum_address(csv_sender_map[map_key])
        if replacement not in private_keys:
            raise RuntimeError(
                f"Replacement sender {replacement} exists in {ACCOUNT_MAP_FILE}, "
                f"but private key is missing in {PRIVATE_KEYS_FILE}"
            )
        if csv_sender:
            print(f"[MAP] csv_row={row_number}: reuse replacement {replacement} for CSV sender {csv_sender}")
        else:
            print(f"[MAP] csv_row={row_number}: reuse replacement {replacement} for missing/invalid CSV sender")
        return replacement, private_keys[replacement], "generated_reused"

    replacement, priv = create_account(f"sender replacement for csv_row={row_number}")
    csv_sender_map[map_key] = replacement
    save_sender_map()

    if csv_sender:
        print(f"[WARN] csv_row={row_number}: no private key for CSV sender {csv_sender}; generated sender {replacement}")
    else:
        print(f"[WARN] csv_row={row_number}: missing/invalid CSV sender; generated sender {replacement}")

    return replacement, priv, "generated_new"


def get_or_create_receiver(csv_receiver: Optional[str], row_number: int) -> Tuple[str, str]:
    """
    Return receiver address. Receivers do not need private key for replay.
    If receiver is missing/invalid, create a generated receiver account.
    """
    if csv_receiver:
        return csv_receiver, "csv_receiver"

    receiver, _ = create_account(f"receiver replacement for csv_row={row_number}")
    return receiver, "generated_receiver"


def required_funding_for_sender(value: int, gas: int, gas_price: int) -> int:
    # Enough for this row plus configurable extra safety buffer.
    return int(value) + int(gas) * int(gas_price) + int(web3.to_wei(FUNDING_EXTRA_ETH, "ether"))


def read_csv_rows() -> pd.DataFrame:
    print("\n========== PHASE 1: Read CSV ==========")
    df = pd.read_csv(CSV_FILE, sep="\t", engine="python", on_bad_lines="skip")
    selected = df.iloc[START_INDEX:START_INDEX + LIMIT_ROWS].reset_index(drop=True)
    print(f"[INFO] Loaded {len(df)} rows from {CSV_FILE}")
    print(f"[INFO] Selected rows {START_INDEX} to {START_INDEX + len(selected) - 1}")
    return selected


def build_replay_plan(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    print("\n========== PHASE 2: Create all accounts ==========")
    replay_plan: List[Dict[str, Any]] = []
    sender_required_wei: Dict[str, int] = {}
    sender_next_nonce: Dict[str, int] = {}

    for i, row in df.iterrows():
        row_number = START_INDEX + i + 1

        value = parse_int(row.get("value"), 0)
        gas = parse_int(row.get("gas"), GAS_LIMIT)
        gas_price = parse_int(row.get("gasprice"), int(web3.to_wei(GAS_PRICE_GWEI, "gwei")))

        # csv_sender = parse_address(row.get("fromaddress"))
        # csv_receiver = parse_address(row.get("toaddress"))

        # sender, private_key, sender_source = get_or_create_replacement_sender(csv_sender, row_number)
        # receiver, receiver_source = get_or_create_receiver(csv_receiver, row_number)

        csv_sender = parse_address(row.get("fromaddress"))
        csv_receiver = parse_address(row.get("toaddress"))

        # Original smart-contract calldata
        input_data = parse_input_data(
            row.get("input")
        )

        # ------------------------------------------------------------
        # Keep OLD sender behavior unchanged
        # ------------------------------------------------------------

        sender, private_key, sender_source = (
            get_or_create_replacement_sender(
                csv_sender,
                row_number
            )
        )

        # ------------------------------------------------------------
        # NEW ADDITION:
        # only replace receiver if it is one of top 10 contracts
        # ------------------------------------------------------------

        contract_mapped = False

        if (
            csv_receiver
            and csv_receiver.lower() in CONTRACT_ADDRESS_MAP
        ):

            receiver = CONTRACT_ADDRESS_MAP[
                csv_receiver.lower()
            ]

            receiver_source = "mapped_local_contract"

            contract_mapped = True

            print(
                f"[CONTRACT MAP] "
                f"row={row_number} "
                f"original_to={csv_receiver} "
                f"local_to={receiver}"
            )

        else:

            # --------------------------------------------------------
            # OLD receiver behavior unchanged
            # --------------------------------------------------------

            receiver, receiver_source = (
                get_or_create_receiver(
                    csv_receiver,
                    row_number
                )
            )

        if sender not in sender_next_nonce:
            sender_next_nonce[sender] = get_pending_nonce(sender)
        nonce = sender_next_nonce[sender]
        sender_next_nonce[sender] += 1

        row_required = required_funding_for_sender(value, gas, gas_price)
        sender_required_wei[sender] = sender_required_wei.get(sender, 0) + row_required

        # replay_plan.append({
        #     "csv_row": row_number,
        #     "original_from": csv_sender or str(row.get("fromaddress", "")),
        #     "original_to": csv_receiver or str(row.get("toaddress", "")),
        #     "from": sender,
        #     "to": receiver,
        #     "sender_source": sender_source,
        #     "receiver_source": receiver_source,
        #     "private_key": private_key,
        #     "value_wei": int(value),
        #     "value_eth": float(web3.from_wei(int(value), "ether")),
        #     "gas_limit": int(gas),
        #     "gas_price_wei": int(gas_price),
        #     "gas_price_gwei": float(web3.from_wei(int(gas_price), "gwei")),
        #     "nonce": int(nonce),
        #     "chainId": chain_id,
        # })
        replay_plan.append({
        "csv_row": row_number,

        "original_from":
            csv_sender or str(row.get("fromaddress", "")),

        "original_to":
            csv_receiver or str(row.get("toaddress", "")),

        "from": sender,
        "to": receiver,

        "contract_address_mapped":
            contract_mapped,

        "mapped_contract_address":
            receiver if contract_mapped else "",

        "input":
            input_data,

        "sender_source":
            sender_source,

        "receiver_source":
            receiver_source,

        "private_key":
            private_key,

        "value_wei":
            int(value),

        "value_eth":
            float(web3.from_wei(int(value), "ether")),

        "gas_limit":
            int(gas),

        "gas_price_wei":
            int(gas_price),

        "gas_price_gwei":
            float(web3.from_wei(int(gas_price), "gwei")),

        "nonce":
            int(nonce),

        "chainId":
            chain_id,
    })

    print(f"[INFO] Prepared {len(replay_plan)} replay transactions")
    print(f"[INFO] Unique senders requiring balance check/funding: {len(sender_required_wei)}")
    return replay_plan, sender_required_wei


def send_funding_only(address: str, amount_wei: int, nonce: int) -> Dict[str, Any]:
    tx = {
        "from": master_address,
        "to": Web3.to_checksum_address(address),
        "value": int(amount_wei),
        "gas": GAS_LIMIT,
        "gasPrice": int(web3.to_wei(GAS_PRICE_GWEI, "gwei")),
        "nonce": int(nonce),
        "chainId": chain_id,
    }
    signed = web3.eth.account.sign_transaction(tx, MASTER_PRIVATE_KEY)
    send_epoch = time.time()
    send_time = now_utc().isoformat()
    tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction).hex()
    print(f"[FUNDING SENT] to={address} amount={web3.from_wei(amount_wei, 'ether')} ETH hash={tx_hash} nonce={nonce}")
    return {
        "fund_to": address,
        "fund_amount_wei": int(amount_wei),
        "fund_amount_eth": float(web3.from_wei(amount_wei, "ether")),
        "funding_tx_hash": tx_hash,
        "funding_nonce": nonce,
        "funding_send_time_utc": send_time,
        "funding_send_epoch": send_epoch,
        "funding_status": "SENT",
        "funding_error": "",
    }

def calculate_token_requirements(
    replay_plan: List[Dict[str, Any]]
) -> Tuple[Dict[str, int], Dict[str, int]]:

    print(
        "\n========== PHASE 2.5A: "
        "CALCULATE TOKEN REQUIREMENTS =========="
    )

    usdt_required: Dict[str, int] = {}
    weth_required: Dict[str, int] = {}

    for plan in replay_plan:

        if not plan.get(
            "contract_address_mapped",
            False
        ):
            continue

        original_to = str(
            plan.get("original_to", "")
        ).lower()

        data = str(
            plan.get("input", "0x")
        )

        selector = calldata_selector(
            data
        )

        sender = Web3.to_checksum_address(
            plan["from"]
        )

        # ----------------------------------------------------
        # USDT
        # ----------------------------------------------------

        if original_to == USDT_MAINNET:

            # transfer(address,uint256)
            if selector == SELECTOR_TRANSFER:

                try:

                    amount = decode_uint256_word(
                        data,
                        1
                    )

                    usdt_required[sender] = (
                        usdt_required.get(
                            sender,
                            0
                        )
                        + amount
                    )

                    plan["state_prep_type"] = (
                        "USDT_BALANCE"
                    )

                except Exception as e:

                    print(
                        f"[USDT DECODE ERROR] "
                        f"row={plan['csv_row']} "
                        f"error={e}"
                    )

            elif selector == SELECTOR_APPROVE:

                # approve generally doesn't need token balance
                plan["state_prep_type"] = (
                    "NONE_APPROVE"
                )

            elif selector == SELECTOR_TRANSFER_FROM:

                # More complicated:
                # requires balance + allowance from another account
                plan["state_prep_type"] = (
                    "NEEDS_ALLOWANCE"
                )

        # ----------------------------------------------------
        # WETH
        # ----------------------------------------------------

        elif original_to == WETH_MAINNET:

            # WETH transfer(address,uint256)
            if selector == SELECTOR_TRANSFER:

                try:

                    amount = decode_uint256_word(
                        data,
                        1
                    )

                    weth_required[sender] = (
                        weth_required.get(
                            sender,
                            0
                        )
                        + amount
                    )

                    plan["state_prep_type"] = (
                        "WETH_BALANCE"
                    )

                except Exception as e:

                    print(
                        f"[WETH TRANSFER DECODE ERROR] "
                        f"row={plan['csv_row']} "
                        f"error={e}"
                    )

            # WETH withdraw(uint256)
            elif selector == SELECTOR_WETH_WITHDRAW:

                try:

                    amount = decode_uint256_word(
                        data,
                        0
                    )

                    weth_required[sender] = (
                        weth_required.get(
                            sender,
                            0
                        )
                        + amount
                    )

                    plan["state_prep_type"] = (
                        "WETH_BALANCE"
                    )

                except Exception as e:

                    print(
                        f"[WETH WITHDRAW DECODE ERROR] "
                        f"row={plan['csv_row']} "
                        f"error={e}"
                    )

            elif selector == SELECTOR_WETH_DEPOSIT:

                # deposit only needs ETH value
                plan["state_prep_type"] = (
                    "NONE_DEPOSIT"
                )

            elif selector == SELECTOR_APPROVE:

                plan["state_prep_type"] = (
                    "NONE_APPROVE"
                )

            elif selector == SELECTOR_TRANSFER_FROM:

                plan["state_prep_type"] = (
                    "NEEDS_ALLOWANCE"
                )

    print(
        f"[STATE PREP] USDT accounts: "
        f"{len(usdt_required)}"
    )

    print(
        f"[STATE PREP] WETH accounts: "
        f"{len(weth_required)}"
    )

    return (
        usdt_required,
        weth_required
    )

def send_state_preparation_transaction(
    tx: Dict[str, Any],
    label: str
) -> None:

    signed = web3.eth.account.sign_transaction(
        tx,
        MASTER_PRIVATE_KEY
    )

    tx_hash = web3.eth.send_raw_transaction(
        signed.raw_transaction
    )

    print(
        f"[STATE PREP SENT] "
        f"{label} "
        f"hash={tx_hash.hex()}"
    )

    receipt = (
        web3.eth.wait_for_transaction_receipt(
            tx_hash,
            timeout=600
        )
    )

    if not normalize_status(
        receipt.status
    ):

        raise RuntimeError(
            f"State preparation failed: {label}"
        )

    print(
        f"[STATE PREP SUCCESS] "
        f"{label} "
        f"block={receipt.blockNumber}"
    )

def prepare_usdt_balances(
    requirements: Dict[str, int]
) -> None:

    print(
        "\n========== PREPARE USDT BALANCES =========="
    )

    if not requirements:
        print("[USDT] Nothing to prepare.")
        return

    local_usdt = CONTRACT_ADDRESS_MAP.get(
        USDT_MAINNET
    )

    if not local_usdt:

        print(
            "[USDT WARN] "
            "USDT local contract not mapped."
        )

        return

    usdt = web3.eth.contract(
        address=local_usdt,
        abi=ERC20_ABI
    )

    master_token_balance = int(
        usdt.functions.balanceOf(
            master_address
        ).call()
    )

    total_needed = sum(
        requirements.values()
    )

    print(
        f"[USDT] Master balance: "
        f"{master_token_balance}"
    )

    print(
        f"[USDT] Total required: "
        f"{total_needed}"
    )

    if master_token_balance < total_needed:

        raise RuntimeError(
            "Master wallet does not have enough "
            f"local USDT. balance={master_token_balance}, "
            f"required={total_needed}"
        )

    nonce = get_pending_nonce(
        master_address
    )

    for sender, required in requirements.items():

        sender = Web3.to_checksum_address(
            sender
        )

        current = int(
            usdt.functions.balanceOf(
                sender
            ).call()
        )

        missing = max(
            0,
            required - current
        )

        if missing == 0:

            print(
                f"[USDT SKIP] "
                f"{sender} already has enough"
            )

            continue

        tx = (
            usdt.functions
            .transfer(
                sender,
                missing
            )
            .build_transaction({
                "from":
                    master_address,

                "nonce":
                    nonce,

                "gas":
                    150000,

                "gasPrice":
                    int(
                        web3.to_wei(
                            GAS_PRICE_GWEI,
                            "gwei"
                        )
                    ),

                "chainId":
                    chain_id,
            })
        )

        send_state_preparation_transaction(
            tx,
            (
                f"USDT amount={missing} "
                f"to={sender}"
            )
        )

        nonce += 1

    print(
        "[USDT] Preparation complete."
    )

def prepare_weth_balances(
    requirements: Dict[str, int]
) -> None:

    print(
        "\n========== PREPARE WETH BALANCES =========="
    )

    if not requirements:
        print("[WETH] Nothing to prepare.")
        return

    local_weth = CONTRACT_ADDRESS_MAP.get(
        WETH_MAINNET
    )

    if not local_weth:

        print(
            "[WETH WARN] "
            "WETH local contract not mapped."
        )

        return

    weth = web3.eth.contract(
        address=local_weth,
        abi=WETH_ABI
    )

    total_needed = sum(
        requirements.values()
    )

    master_weth = int(
        weth.functions.balanceOf(
            master_address
        ).call()
    )

    nonce = get_pending_nonce(
        master_address
    )

    print(
        "[WETH] Total required:",
        web3.from_wei(
            total_needed,
            "ether"
        )
    )

    print(
        "[WETH] Master currently has:",
        web3.from_wei(
            master_weth,
            "ether"
        )
    )

    # ========================================================
    # Create WETH from ETH
    # ========================================================

    if master_weth < total_needed:

        missing = (
            total_needed
            - master_weth
        )

        tx = (
            weth.functions
            .deposit()
            .build_transaction({
                "from":
                    master_address,

                "value":
                    missing,

                "nonce":
                    nonce,

                "gas":
                    150000,

                "gasPrice":
                    int(
                        web3.to_wei(
                            GAS_PRICE_GWEI,
                            "gwei"
                        )
                    ),

                "chainId":
                    chain_id,
            })
        )

        send_state_preparation_transaction(
            tx,
            (
                "WETH deposit "
                f"{web3.from_wei(missing, 'ether')} ETH"
            )
        )

        nonce += 1

    # ========================================================
    # Give WETH to replay senders
    # ========================================================

    for sender, required in requirements.items():

        sender = Web3.to_checksum_address(
            sender
        )

        current = int(
            weth.functions.balanceOf(
                sender
            ).call()
        )

        missing = max(
            0,
            required - current
        )

        if missing == 0:

            print(
                f"[WETH SKIP] "
                f"{sender} already has enough"
            )

            continue

        tx = (
            weth.functions
            .transfer(
                sender,
                missing
            )
            .build_transaction({
                "from":
                    master_address,

                "nonce":
                    nonce,

                "gas":
                    150000,

                "gasPrice":
                    int(
                        web3.to_wei(
                            GAS_PRICE_GWEI,
                            "gwei"
                        )
                    ),

                "chainId":
                    chain_id,
            })
        )

        send_state_preparation_transaction(
            tx,
            (
                f"WETH={web3.from_wei(missing, 'ether')} "
                f"to={sender}"
            )
        )

        nonce += 1

    print(
        "[WETH] Preparation complete."
    )

def prepare_smart_contract_state(
    replay_plan: List[Dict[str, Any]]
) -> None:

    print()
    print("=" * 70)
    print("PHASE 3.6: PREPARE SMART CONTRACT STATE")
    print("=" * 70)

    # NEW
    print_top10_contract_requirements(
        replay_plan
    )

    (
        usdt_required,
        weth_required
    ) = calculate_token_requirements(
        replay_plan
    )

    prepare_usdt_balances(
        usdt_required
    )

    prepare_weth_balances(
        weth_required
    )    
# def prepare_smart_contract_state(
#     replay_plan: List[Dict[str, Any]]
# ) -> None:

#     print()
#     print("=" * 70)
#     print("PHASE 3.6: PREPARE SMART CONTRACT STATE")
#     print("=" * 70)

#     (
#         usdt_required,
#         weth_required
#     ) = calculate_token_requirements(
#         replay_plan
#     )

#     prepare_usdt_balances(
#         usdt_required
#     )

#     prepare_weth_balances(
#         weth_required
#     )

#     print()
#     print(
#         "[STATE PREP] "
#         "Smart-contract state preparation finished."
#     )           

def preflight_contract_calls(
    replay_plan: List[Dict[str, Any]]
) -> None:

    print()
    print("=" * 70)
    print("PHASE 3.7: PREFLIGHT CONTRACT CALLS")
    print("=" * 70)

    passed = 0
    reverted = 0

    for plan in replay_plan:

        if not plan.get(
            "contract_address_mapped",
            False
        ):
            continue

        call_tx = {
            "from":
                Web3.to_checksum_address(
                    plan["from"]
                ),

            "to":
                Web3.to_checksum_address(
                    plan["to"]
                ),

            "value":
                int(
                    plan["value_wei"]
                ),

            "data":
                plan.get(
                    "input",
                    "0x"
                ),
        }

        try:

            web3.eth.call(
                call_tx,
                "latest"
            )

            plan["preflight_status"] = "PASS"
            plan["preflight_error"] = ""

            passed += 1

        except Exception as e:

            plan["preflight_status"] = "REVERT"

            plan["preflight_error"] = str(
                e
            )

            reverted += 1

            print(
                f"[PREFLIGHT REVERT] "
                f"row={plan['csv_row']} "
                f"original_to={plan['original_to']} "
                f"selector={calldata_selector(plan['input'])} "
                f"error={e}"
            )

    print()
    print(
        f"[PREFLIGHT SUMMARY] "
        f"PASS={passed} "
        f"REVERT={reverted}"
    )




def send_all_funding(sender_required_wei: Dict[str, int]) -> List[Dict[str, Any]]:
    print("\n========== PHASE 3: Send funding tx to all accounts ==========")
    funding_records: List[Dict[str, Any]] = []
    master_nonce = get_pending_nonce(master_address)

    for idx, (address, required_wei) in enumerate(sender_required_wei.items()):
        balance = int(web3.eth.get_balance(address))
        fund_needed = max(0, int(required_wei) - balance)

        if fund_needed <= 0:
            print(f"[FUNDING SKIP] {address} already has enough balance: {web3.from_wei(balance, 'ether')} ETH")
            funding_records.append({
                "fund_to": address,
                "fund_amount_wei": 0,
                "fund_amount_eth": 0.0,
                "funding_tx_hash": "",
                "funding_nonce": "",
                "funding_send_time_utc": now_utc().isoformat(),
                "funding_send_epoch": time.time(),
                "funding_status": "SKIPPED_ALREADY_FUNDED",
                "funding_error": "",
            })
            continue

        try:
            rec = send_funding_only(address, fund_needed, master_nonce)
            funding_records.append(rec)
            master_nonce += 1
            if FUNDING_SEND_INTERVAL_SEC > 0 and idx < len(sender_required_wei) - 1:
                time.sleep(FUNDING_SEND_INTERVAL_SEC)
        except Exception as e:
            print(f"[FUNDING SEND ERROR] to={address} error={e}")
            funding_records.append({
                "fund_to": address,
                "fund_amount_wei": int(fund_needed),
                "fund_amount_eth": float(web3.from_wei(fund_needed, "ether")),
                "funding_tx_hash": "",
                "funding_nonce": master_nonce,
                "funding_send_time_utc": now_utc().isoformat(),
                "funding_send_epoch": time.time(),
                "funding_status": "SEND_ERROR",
                "funding_error": str(e),
            })
            master_nonce += 1

    print(f"[INFO] Funding tx sent/stored: {len([r for r in funding_records if r.get('funding_tx_hash')])}")
    return funding_records


def wait_for_one_receipt(tx_hash: str, timeout_sec: int, poll_sec: float) -> Tuple[bool, Optional[Any], str]:
    deadline = time.time() + timeout_sec
    last_error = ""
    while time.time() < deadline:
        try:
            receipt = web3.eth.get_transaction_receipt(tx_hash)
            if receipt is not None:
                return True, receipt, ""
        except TransactionNotFound:
            pass
        except Exception as e:
            last_error = str(e)
        time.sleep(poll_sec)
    return False, None, f"receipt not found within {timeout_sec}s" + (f"; last error: {last_error}" if last_error else "")


def wait_for_all_funding_receipts(funding_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    print("\n========== PHASE 3.5: Wait for all funding receipts ==========")
    updated: List[Dict[str, Any]] = []

    for rec in funding_records:
        tx_hash = rec.get("funding_tx_hash")
        if not tx_hash:
            updated.append(rec)
            continue

        ok, receipt, error = wait_for_one_receipt(tx_hash, FUNDING_RECEIPT_TIMEOUT_SEC, FUNDING_RECEIPT_POLL_SEC)
        if ok and receipt is not None:
            status_ok = normalize_status(receipt.status)
            rec.update({
                "funding_status": "SUCCESS" if status_ok else "FAILED",
                "funding_block_number": int(receipt.blockNumber),
                "funding_gas_used": int(receipt.gasUsed),
                "funding_receipt_time_utc": now_utc().isoformat(),
                "funding_error": "" if status_ok else "funding transaction failed on-chain",
            })
            print(f"[FUNDING RECEIPT] hash={tx_hash} block={receipt.blockNumber} status={rec['funding_status']}")
        else:
            rec.update({
                "funding_status": "TIMEOUT",
                "funding_block_number": "",
                "funding_gas_used": "",
                "funding_receipt_time_utc": now_utc().isoformat(),
                "funding_error": error,
            })
            print(f"[FUNDING TIMEOUT] hash={tx_hash} error={error}")
        updated.append(rec)

    bad = [r for r in updated if r.get("funding_status") in ("FAILED", "TIMEOUT", "SEND_ERROR")]
    if bad:
        print(f"[WARN] {len(bad)} funding transactions failed/timed out. Replay will still try; those senders may fail.")
    else:
        print("[INFO] All required funding completed or was skipped because balance was already enough.")
    return updated


# def sign_replay_transaction(plan: Dict[str, Any]) -> Any:
#     tx = {
#         "from": plan["from"],
#         "to": plan["to"],
#         "value": int(plan["value_wei"]),
#         "gas": int(plan["gas_limit"]),
#         "gasPrice": int(plan["gas_price_wei"]),
#         "nonce": int(plan["nonce"]),
#         "chainId": chain_id,
#     }
#     return web3.eth.account.sign_transaction(tx, plan["private_key"])
def sign_replay_transaction(
    plan: Dict[str, Any]
) -> Any:

    # =========================================================
    # OLD replay transaction
    # =========================================================
    tx = {
        "from": plan["from"],
        "to": plan["to"],
        "value": int(plan["value_wei"]),
        "gas": int(plan["gas_limit"]),
        "gasPrice": int(plan["gas_price_wei"]),
        "nonce": int(plan["nonce"]),
        "chainId": chain_id,
    }

    # =========================================================
    # NEW ADDITION:
    # Only for top-10 mapped smart contracts,
    # replay the ORIGINAL contract calldata.
    # =========================================================
    if plan.get("contract_address_mapped", False):

        tx["data"] = plan.get(
            "input",
            "0x"
        )

    return web3.eth.account.sign_transaction(
        tx,
        plan["private_key"]
    )
# def sign_replay_transaction(
#     plan: Dict[str, Any]
# ) -> Any:

#     tx = {
#         "from": plan["from"],
#         "to": plan["to"],

#         "value": int(plan["value_wei"]),

#         "gas": int(plan["gas_limit"]),

#         "gasPrice": int(
#             plan["gas_price_wei"]
#         ),

#         "nonce": int(plan["nonce"]),

#         "chainId": chain_id,

#         # Preserve original CSV contract calldata.
#         # For ordinary ETH transfers this will usually be 0x.
#         "data": plan.get("input", "0x"),
#     }

#     return web3.eth.account.sign_transaction(
#         tx,
#         plan["private_key"]
#     )

def append_transaction_bytes(raw_tx: bytes):
    hex_array = [f"0x{b:02x}" for b in raw_tx]

    with open(RAW_TX_FILE, "a") as f:
        f.write("[\n")

        rows = [
            ", ".join(hex_array[i:i+8])
            for i in range(0, len(hex_array), 8)
        ]

        for i, row in enumerate(rows):
            if i < len(rows) - 1:
                f.write(f"    {row},\n")
            else:
                f.write(f"    {row}\n")

        f.write("],\n")

def send_replay_transactions(replay_plan: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], float]:
    print("\n========== PHASE 4: Start replay timer ==========")
    replay_start = time.time()
    print(f"[INFO] Replay timer started at {now_utc().isoformat()}")

    print("\n========== PHASE 5: Send replay tx at TX_PER_SECOND ==========")
    send_results: List[Dict[str, Any]] = []
    next_send_time = replay_start

    for idx, plan in enumerate(replay_plan):
        now = time.time()
        if now < next_send_time:
            time.sleep(next_send_time - now)

        record = {k: v for k, v in plan.items() if k != "private_key"}
        record["send_time_utc"] = now_utc().isoformat()
        record["send_epoch"] = time.time()
        record["send_error"] = ""

        try:
            signed = sign_replay_transaction(plan)
            append_transaction_bytes(signed.raw_transaction)
            tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction).hex()
            record["tx_hash"] = tx_hash
            record["status"] = "SENT"
            print(
                f"[SENT] row={plan['csv_row']} hash={tx_hash} "
                f"nonce={plan['nonce']} from={plan['from']} to={plan['to']}"
            )

            # if plan.get("contract_address_mapped", False):

            #     print(
            #         f"[CONTRACT SENT] "
            #         f"row={plan['csv_row']} "
            #         f"hash={tx_hash} "
            #         f"nonce={plan['nonce']} "
            #         f"from={plan['from']} "
            #         f"original_to={plan['original_to']} "
            #         f"local_to={plan['to']} "
            #         f"input={plan.get('input', '0x')[:18]}..."
            #     )

            # else:

            #     print(
            #         f"[SENT] "
            #         f"row={plan['csv_row']} "
            #         f"hash={tx_hash} "
            #         f"nonce={plan['nonce']} "
            #         f"from={plan['from']} "
            #         f"to={plan['to']}"
            #     )
        except Exception as e:
            record["tx_hash"] = ""
            record["status"] = "SEND_ERROR"
            record["send_error"] = str(e)
            record["error"] = str(e)
            print(f"[SEND ERROR] row={plan['csv_row']} error={e}")

        send_results.append(record)
        next_send_time += SEND_INTERVAL_SEC

    send_duration = time.time() - replay_start
    print(f"[INFO] Finished replay send phase in {send_duration:.3f} sec")
    return send_results, send_duration


def collect_receipt_and_block(record: Dict[str, Any]) -> Dict[str, Any]:
    tx_hash = record.get("tx_hash")
    if not tx_hash:
        return record

    ok, receipt, error = wait_for_one_receipt(tx_hash, RECEIPT_TIMEOUT_SEC, RECEIPT_POLL_SEC)
    if not ok or receipt is None:
        record.update({
            "block_number": "",
            "status_raw": "",
            "status": "DROPPED_OR_TIMEOUT",
            "gas_used": "",
            "receipt_fetch_time_utc": now_utc().isoformat(),
            "block_timestamp_utc": "",
            "block_timestamp_latency_sec": "",
            "receipt_observed_latency_sec": "",
            "error": error,
        })
        print(f"[RECEIPT TIMEOUT] row={record.get('csv_row')} hash={tx_hash}")
        return record

    block = web3.eth.get_block(receipt.blockNumber)
    block_ts_epoch = int(block.timestamp)
    block_dt = datetime.fromtimestamp(block_ts_epoch, tz=timezone.utc)
    send_epoch = float(record["send_epoch"])
    fetch_epoch = time.time()
    status_ok = normalize_status(receipt.status)

    record.update({
        "block_number": int(receipt.blockNumber),
        "status_raw": receipt.status,
        "status": "SUCCESS" if status_ok else "FAILED",
        "gas_used": int(receipt.gasUsed),
        "receipt_fetch_time_utc": now_utc().isoformat(),
        "block_timestamp_utc": block_dt.isoformat(),
        "block_timestamp_latency_sec": block_ts_epoch - send_epoch,
        "receipt_observed_latency_sec": fetch_epoch - send_epoch,
        "error": "" if status_ok else "transaction failed on-chain",
    })
    print(f"[RECEIPT] row={record.get('csv_row')} block={receipt.blockNumber} status={record['status']}")
    return record


# def collect_all_replay_receipts(send_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     print("\n========== PHASE 6: Collect receipts ==========")
#     final_records = []
#     for rec in send_results:
#         final_records.append(collect_receipt_and_block(rec))
#     return final_records

# def collect_all_replay_receipts(send_results):
#     print("\n========== PHASE 6: Collect receipts ==========")

#     pending = {}
#     completed = []

#     for rec in send_results:
#         if rec.get("tx_hash"):
#             pending[rec["tx_hash"]] = rec
#         else:
#             completed.append(rec)

#     deadline = time.time() + RECEIPT_TIMEOUT_SEC

#     while pending and time.time() < deadline:

#         for tx_hash in list(pending.keys()):

#             try:
#                 receipt = web3.eth.get_transaction_receipt(tx_hash)

#                 if receipt is None:
#                     continue

#                 rec = pending.pop(tx_hash)

#                 block = web3.eth.get_block(receipt.blockNumber)

#                 block_ts_epoch = int(block.timestamp)
#                 send_epoch = float(rec["send_epoch"])

#                 rec["block_number"] = int(receipt.blockNumber)
#                 rec["status_raw"] = receipt.status
#                 rec["status"] = "SUCCESS" if normalize_status(receipt.status) else "FAILED"
#                 rec["gas_used"] = int(receipt.gasUsed)

#                 rec["receipt_fetch_time_utc"] = now_utc().isoformat()
#                 rec["block_timestamp_utc"] = datetime.fromtimestamp(
#                     block_ts_epoch,
#                     tz=timezone.utc
#                 ).isoformat()

#                 rec["block_timestamp_latency_sec"] = (
#                     block_ts_epoch - send_epoch
#                 )

#                 # rec["receipt_observed_latency_sec"] = (
#                 #     time.time() - send_epoch
#                 # )
#                 receipt_fetch_epoch = time.time()

#                 rec["inclusion_observed_latency_sec"] = receipt_fetch_epoch - send_epoch
#                 rec["receipt_observed_latency_sec"] = receipt_fetch_epoch - send_epoch

#                 completed.append(rec)

#                 print(
#                     f"[RECEIPT] row={rec['csv_row']} "
#                     f"block={receipt.blockNumber}"
#                 )

#             except TransactionNotFound:
#                 pass

#         time.sleep(RECEIPT_POLL_SEC)
#     for tx_hash, rec in pending.items():
#         rec.update({
#                     "block_number": "",
#                     "status_raw": "",
#                     "status": "DROPPED_OR_TIMEOUT",
#                     "gas_used": "",
#                     "receipt_fetch_time_utc": now_utc().isoformat(),
#                     "block_timestamp_utc": "",
#                     "block_timestamp_latency_sec": "",
#                     "receipt_observed_latency_sec": "",
#                     "inclusion_observed_latency_sec": "",
#                     "error": f"receipt not found within {RECEIPT_TIMEOUT_SEC}s",
#                 })
#         completed.append(rec)           

#     return completed

# def wait_until_finalized(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     mined_blocks = [int(r["block_number"]) for r in records if str(r.get("block_number", "")).isdigit()]
#     if not mined_blocks:
#         return records

#     target_block = max(mined_blocks)
#     deadline = time.time() + FINALITY_TIMEOUT_SEC
#     last_finalized = None

#     while time.time() < deadline:
#         try:
#             finalized = web3.eth.get_block("finalized")
#             last_finalized = int(finalized.number)
#             print(f"[FINALITY] finalized={last_finalized}, target={target_block}")
#             if last_finalized >= target_block:
#                 observed_epoch = time.time()
#                 observed_dt = now_utc().isoformat()
#                 finalized_ts = datetime.fromtimestamp(int(finalized.timestamp), tz=timezone.utc).isoformat()
#                 for r in records:
#                     if str(r.get("block_number", "")).isdigit() and int(r["block_number"]) <= last_finalized:
#                         send_epoch = float(r["send_epoch"])
#                         r["finalized_block_number_seen"] = last_finalized
#                         r["finalized_block_timestamp_utc"] = finalized_ts
#                         r["finalization_observed_time_utc"] = observed_dt
#                         r["finalization_observed_latency_sec"] = observed_epoch - send_epoch
#                 return records
#         except Exception as e:
#             print(f"[FINALITY WARN] Could not read finalized block yet: {e}")
#         time.sleep(FINALITY_POLL_SEC)

#     for r in records:
#         if str(r.get("block_number", "")).isdigit():
#             r["finalized_block_number_seen"] = last_finalized if last_finalized is not None else ""
#             r["finalized_block_timestamp_utc"] = ""
#             r["finalization_observed_time_utc"] = ""
#             r["finalization_observed_latency_sec"] = ""
#     return records

def collect_all_replay_receipts(send_results):
    print("\n========== PHASE 6: Collect receipts ==========")

    pending = {}
    completed = []

    for rec in send_results:
        if rec.get("tx_hash"):
            pending[rec["tx_hash"]] = rec
        else:
            completed.append(rec)

    deadline = time.time() + RECEIPT_TIMEOUT_SEC
    block_cache = {}

    last_checked_block = -1

    while pending and time.time() < deadline:
        try:
            latest_block = int(web3.eth.block_number)
        except Exception as e:
            print(f"[RECEIPT WARN] Could not get latest block: {e}")
            time.sleep(RECEIPT_POLL_SEC)
            continue

        # Do not re-scan 37k txs if no new block was produced.
        if latest_block == last_checked_block and len(pending) > 100:
            time.sleep(RECEIPT_POLL_SEC)
            continue

        last_checked_block = latest_block
        found_this_round = 0

        print(
            f"[RECEIPT POLL] latest_block={latest_block} "
            f"pending_before={len(pending)}"
        )

        for tx_hash in list(pending.keys()):
            try:
                receipt = web3.eth.get_transaction_receipt(tx_hash)

                if receipt is None:
                    continue

                rec = pending.pop(tx_hash)
                receipt_fetch_epoch = time.time()

                block_number = int(receipt.blockNumber)

                if block_number in block_cache:
                    block = block_cache[block_number]
                else:
                    block = web3.eth.get_block(block_number)
                    block_cache[block_number] = block

                block_ts_epoch = int(block.timestamp)
                send_epoch = float(rec["send_epoch"])
                status_ok = normalize_status(receipt.status)

                rec["block_number"] = block_number
                rec["status_raw"] = receipt.status
                rec["status"] = "SUCCESS" if status_ok else "FAILED"
                rec["gas_used"] = int(receipt.gasUsed)

                rec["receipt_fetch_time_utc"] = now_utc().isoformat()
                rec["block_timestamp_utc"] = datetime.fromtimestamp(
                    block_ts_epoch,
                    tz=timezone.utc,
                ).isoformat()

                # TRUE blockchain inclusion latency.
                rec["inclusion_latency_sec"] = block_ts_epoch - send_epoch

                # Python/RPC observation delay. Do not use this as blockchain latency.
                rec["receipt_observed_latency_sec"] = receipt_fetch_epoch - send_epoch

                # Compatibility with old column name.
                rec["block_timestamp_latency_sec"] = rec["inclusion_latency_sec"]

                rec["error"] = "" if status_ok else "transaction failed on-chain"

                completed.append(rec)
                found_this_round += 1

                print(
                    f"[RECEIPT] row={rec['csv_row']} "
                    f"block={block_number} "
                    f"inclusion_latency={rec['inclusion_latency_sec']:.3f}s "
                    f"observed_latency={rec['receipt_observed_latency_sec']:.3f}s"
                )

            except TransactionNotFound:
                pass
            except Exception as e:
                print(f"[RECEIPT ERROR] tx={tx_hash} error={e}")

        print(
            f"[RECEIPT POLL DONE] found={found_this_round} "
            f"pending_after={len(pending)} completed={len(completed)}"
        )

        # if pending:
        if pending and found_this_round == 0:
            time.sleep(RECEIPT_POLL_SEC)

    for tx_hash, rec in pending.items():
        rec.update({
            "block_number": "",
            "status_raw": "",
            "status": "DROPPED_OR_TIMEOUT",
            "gas_used": "",
            "receipt_fetch_time_utc": now_utc().isoformat(),
            "block_timestamp_utc": "",
            "block_timestamp_latency_sec": "",
            "inclusion_latency_sec": "",
            "receipt_observed_latency_sec": "",
            "error": f"receipt not found within {RECEIPT_TIMEOUT_SEC}s",
        })
        completed.append(rec)

    return completed

def summarize_and_write_excel(
    final_records: List[Dict[str, Any]],
    funding_records: List[Dict[str, Any]],
    send_duration: float,
    total_duration: float,
) -> None:
    print("\n========== PHASE 7: Calculate latency ==========")
    

    detail_df = pd.DataFrame(final_records)

    if not detail_df.empty and "csv_row" in detail_df.columns:
        detail_df = detail_df.sort_values(by="csv_row")

    funding_df = pd.DataFrame(funding_records)

    total_tx = len(detail_df)
    sent_tx = detail_df["tx_hash"].replace("", pd.NA).dropna().shape[0] if "tx_hash" in detail_df else 0
    mined_tx = detail_df["block_number"].replace("", pd.NA).dropna().shape[0] if "block_number" in detail_df else 0
    success_tx = (detail_df.get("status", pd.Series(dtype=str)) == "SUCCESS").sum()
    failed_tx = (detail_df.get("status", pd.Series(dtype=str)) == "FAILED").sum()
    timeout_tx = (detail_df.get("status", pd.Series(dtype=str)) == "DROPPED_OR_TIMEOUT").sum()
    send_error_tx = (detail_df.get("status", pd.Series(dtype=str)) == "SEND_ERROR").sum()

    funding_sent = funding_df["funding_tx_hash"].replace("", pd.NA).dropna().shape[0] if not funding_df.empty else 0
    funding_success = (funding_df.get("funding_status", pd.Series(dtype=str)) == "SUCCESS").sum() if not funding_df.empty else 0
    funding_skipped = (funding_df.get("funding_status", pd.Series(dtype=str)) == "SKIPPED_ALREADY_FUNDED").sum() if not funding_df.empty else 0
    funding_problem = funding_df[funding_df.get("funding_status", pd.Series(dtype=str)).isin(["FAILED", "TIMEOUT", "SEND_ERROR"])].shape[0] if not funding_df.empty else 0

    # block_latencies = pd.to_numeric(detail_df.get("block_timestamp_latency_sec", pd.Series(dtype=float)), errors="coerce").dropna()
    # observed_latencies = pd.to_numeric(detail_df.get("receipt_observed_latency_sec", pd.Series(dtype=float)), errors="coerce").dropna()
    # inclusion_latencies = pd.to_numeric(detail_df.get("inclusion_observed_latency_sec", pd.Series(dtype=float)),errors="coerce").dropna()
    
    inclusion_latencies = pd.to_numeric(
        detail_df.get("inclusion_latency_sec", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()

    observed_latencies = pd.to_numeric(
        detail_df.get("receipt_observed_latency_sec", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()

    block_latencies = pd.to_numeric(
        detail_df.get("block_timestamp_latency_sec", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    
    finality_latencies = pd.to_numeric(detail_df.get("finalization_observed_latency_sec", pd.Series(dtype=float)), errors="coerce").dropna()


    summary = {
        "Total rows selected": total_tx,
        "Sent replay transactions": sent_tx,
        "Mined replay transactions": mined_tx,
        "Successful replay transactions": success_tx,
        "Failed replay transactions": failed_tx,
        "Receipt timeout replay transactions": timeout_tx,
        "Send error replay transactions": send_error_tx,
        "Funding tx sent": funding_sent,
        "Funding successful": funding_success,
        "Funding skipped already funded": funding_skipped,
        "Funding failed/timeout/send_error": funding_problem,
        "Configured tx/sec": TX_PER_SECOND,
        "Configured wait between replay sends sec": SEND_INTERVAL_SEC,
        "Replay send phase duration sec": send_duration,
        "Actual replay send rate tx/sec": sent_tx / send_duration if send_duration else 0,
        "Total run duration sec": total_duration,
        "Average inclusion latency sec": inclusion_latencies.mean() if len(inclusion_latencies) else 0,
        "Min inclusion latency sec": inclusion_latencies.min() if len(inclusion_latencies) else 0,
        "Max inclusion latency sec": inclusion_latencies.max() if len(inclusion_latencies) else 0,

        "Average receipt observed latency sec": observed_latencies.mean() if len(observed_latencies) else 0,
        "Min receipt observed latency sec": observed_latencies.min() if len(observed_latencies) else 0,
        "Max receipt observed latency sec": observed_latencies.max() if len(observed_latencies) else 0,

        "Average block timestamp latency sec": block_latencies.mean() if len(block_latencies) else 0,
        "Min block timestamp latency sec": block_latencies.min() if len(block_latencies) else 0,
        "Max block timestamp latency sec": block_latencies.max() if len(block_latencies) else 0,
        # "Average block timestamp latency sec": block_latencies.mean() if len(block_latencies) else 0,
        # "Min block timestamp latency sec": block_latencies.min() if len(block_latencies) else 0,
        # "Max block timestamp latency sec": block_latencies.max() if len(block_latencies) else 0,
        # "Average receipt observed latency sec": observed_latencies.mean() if len(observed_latencies) else 0,
        # "Min receipt observed latency sec": observed_latencies.min() if len(observed_latencies) else 0,
        # "Max receipt observed latency sec": observed_latencies.max() if len(observed_latencies) else 0,
        # "Average inclusion observed latency sec": inclusion_latencies.mean() if len(inclusion_latencies) else 0,
        # "Min inclusion observed latency sec": inclusion_latencies.min() if len(inclusion_latencies) else 0,
        # "Max inclusion observed latency sec": inclusion_latencies.max() if len(inclusion_latencies) else 0,
    }

    if WAIT_FOR_FINALIZATION:
        summary.update({
            "Average finalization observed latency sec": finality_latencies.mean() if len(finality_latencies) else 0,
            "Min finalization observed latency sec": finality_latencies.min() if len(finality_latencies) else 0,
            "Max finalization observed latency sec": finality_latencies.max() if len(finality_latencies) else 0,
        })

    summary_df = pd.DataFrame(summary.items(), columns=["Metric", "Value"])

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        detail_df.to_excel(writer, sheet_name="per_transaction", index=False)
        funding_df.to_excel(writer, sheet_name="funding", index=False)
        summary_df.to_excel(writer, sheet_name="overall_summary", index=False)

    print("\n================ FINAL SUMMARY ================")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"\n[INFO] Excel saved to: {OUTPUT_XLSX}")

def main() -> None:
    run_start = time.time()

# Start with an empty transaction file
    with open(RAW_TX_FILE, "w"):
        pass
    df = read_csv_rows()
    replay_plan, sender_required_wei = build_replay_plan(df)

    funding_records = send_all_funding(sender_required_wei)
    funding_records = wait_for_all_funding_receipts(funding_records)

    # STEP 1: funding activity completed, now verify receipt status
    bad_funding = [
        r for r in funding_records
        if r.get("funding_status") not in ("SUCCESS", "SKIPPED_ALREADY_FUNDED")
    ]

    if bad_funding:
        print("\n========== FUNDING FAILED ==========")
        print(f"[FATAL] {len(bad_funding)} funding txs failed/timed out.")
        print("[FATAL] Replay stopped. No replay transactions will be sent.")

        total_duration = time.time() - run_start
        summarize_and_write_excel([], funding_records, 0.0, total_duration)
        sys.exit(1)

    # STEP 2: receipt success is not enough; verify actual balance on-chain
    print("\n========== VERIFY FUNDED BALANCES ==========")

    BALANCE_TIMEOUT_SEC = int(
        os.getenv("BALANCE_TIMEOUT_SEC", "300")
    )

    deadline = time.time() + BALANCE_TIMEOUT_SEC
    # deadline = time.time() + 300      # wait up to 5 minutes
    remaining = dict(sender_required_wei)
    last_checked_block = -1


    while remaining and time.time() < deadline:

        try:
            current_block = web3.eth.block_number
        except Exception as e:
            print(f"[BALANCE WARN] Cannot read block number: {e}")
            time.sleep(1)
            continue

        if current_block == last_checked_block:
            time.sleep(1)
            continue

        last_checked_block = current_block

        print(
            f"[BALANCE CHECK] block={current_block} "
            f"remaining_accounts={len(remaining)}"
        )

    # while remaining and time.time() < deadline:

        for address in list(remaining.keys()):

            # balance = int(
            #     web3.eth.get_balance(
            #         Web3.to_checksum_address(address),
            #         "latest",
            #     )
            # )

            # if balance >= remaining[address]:
            #     print(f"[BALANCE OK] {address}")
            #     del remaining[address]
            try:
                balance = int(
                    web3.eth.get_balance(
                        Web3.to_checksum_address(address),
                        "latest",
                    )
                )
            except Exception as e:
                print(f"[BALANCE ERROR] {address}: {e}")
                continue

            if balance >= remaining[address]:
                print(f"[BALANCE OK] {address}")
                del remaining[address]

    #     if remaining:
    #         time.sleep(2)

    if remaining:

        print("\n========== BALANCE CHECK FAILED ==========")

        for address, required in remaining.items():

            # balance = int(
            #     web3.eth.get_balance(
            #         Web3.to_checksum_address(address),
            #         "latest",
            #     )
            # )
            try:
                balance = int(
                    web3.eth.get_balance(
                        Web3.to_checksum_address(address),
                        "latest",
                    )
                )
            except Exception as e:
                print(f"[BALANCE ERROR] {address}: {e}")
                balance = "UNKNOWN"

            print(
                f"[FATAL] {address}"
                f" balance={balance}"
                f" required={required}"
            )

        summarize_and_write_excel(
            [],
            funding_records,
            0.0,
            time.time()-run_start,
        )

        sys.exit(1)

    # print("[INFO] All funding confirmed on-chain and all balances are enough.")
    # print("[INFO] Starting replay now.")

    # send_results, send_duration = send_replay_transactions(replay_plan)
    print(
    "[INFO] All ETH funding confirmed on-chain "
    "and all balances are enough."
    )

    # ============================================================
    # NEW:
    # Prepare token/application state BEFORE the timer starts
    # ============================================================

    prepare_smart_contract_state(
        replay_plan
    )

    # ============================================================
    # NEW:
    # Simulate contract calls after preparation
    # ============================================================

    preflight_contract_calls(
        replay_plan
    )

    print(
        "[INFO] Contract state preparation complete."
    )

    print(
        "[INFO] Starting timed replay now."
    )

    # ============================================================
    # IMPORTANT:
    # Timer starts only here, exactly like before.
    # Therefore preparation does NOT affect replay latency.
    # ============================================================

    send_results, send_duration = (
        send_replay_transactions(
            replay_plan
        )
    )

    final_records = (
        collect_all_replay_receipts(
            send_results
        )
    )

    final_records = collect_all_replay_receipts(send_results)

    if WAIT_FOR_FINALIZATION:
        print("\n[INFO] Waiting until finalized block covers all mined replay transactions...")
        final_records = wait_until_finalized(final_records)

    total_duration = time.time() - run_start
    summarize_and_write_excel(final_records, funding_records, send_duration, total_duration)
# def main() -> None:
#     run_start = time.time()

#     df = read_csv_rows()
#     replay_plan, sender_required_wei = build_replay_plan(df)

#     funding_records = send_all_funding(sender_required_wei)
#     funding_records = wait_for_all_funding_receipts(funding_records)

#     send_results, send_duration = send_replay_transactions(replay_plan)
#     final_records = collect_all_replay_receipts(send_results)

#     if WAIT_FOR_FINALIZATION:
#         print("\n[INFO] Waiting until finalized block covers all mined replay transactions...")
#         final_records = wait_until_finalized(final_records)

#     total_duration = time.time() - run_start
#     summarize_and_write_excel(final_records, funding_records, send_duration, total_duration)


if __name__ == "__main__":
    main()
