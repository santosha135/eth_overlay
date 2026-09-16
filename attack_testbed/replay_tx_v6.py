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

# =========================
# SYSTEM PARAMETERS
# =========================
GETH_URL = os.getenv("GETH_URL", "http://el-06-geth-lighthouse:8545")
MASTER_PRIVATE_KEY = os.getenv(
    "MASTER_PRIVATE_KEY",
    "27515f805127bebad2fb9b183508bdacb8c763da16f54e0678b16e8f28ef3fff",
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

START_INDEX = int(os.getenv("START_INDEX", "190000"))
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

        csv_sender = parse_address(row.get("fromaddress"))
        csv_receiver = parse_address(row.get("toaddress"))

        sender, private_key, sender_source = get_or_create_replacement_sender(csv_sender, row_number)
        receiver, receiver_source = get_or_create_receiver(csv_receiver, row_number)

        if sender not in sender_next_nonce:
            sender_next_nonce[sender] = get_pending_nonce(sender)
        nonce = sender_next_nonce[sender]
        sender_next_nonce[sender] += 1

        row_required = required_funding_for_sender(value, gas, gas_price)
        sender_required_wei[sender] = sender_required_wei.get(sender, 0) + row_required

        replay_plan.append({
            "csv_row": row_number,
            "original_from": csv_sender or str(row.get("fromaddress", "")),
            "original_to": csv_receiver or str(row.get("toaddress", "")),
            "from": sender,
            "to": receiver,
            "sender_source": sender_source,
            "receiver_source": receiver_source,
            "private_key": private_key,
            "value_wei": int(value),
            "value_eth": float(web3.from_wei(int(value), "ether")),
            "gas_limit": int(gas),
            "gas_price_wei": int(gas_price),
            "gas_price_gwei": float(web3.from_wei(int(gas_price), "gwei")),
            "nonce": int(nonce),
            "chainId": chain_id,
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


def sign_replay_transaction(plan: Dict[str, Any]) -> Any:
    tx = {
        "from": plan["from"],
        "to": plan["to"],
        "value": int(plan["value_wei"]),
        "gas": int(plan["gas_limit"]),
        "gasPrice": int(plan["gas_price_wei"]),
        "nonce": int(plan["nonce"]),
        "chainId": chain_id,
    }
    return web3.eth.account.sign_transaction(tx, plan["private_key"])


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

    print("[INFO] All funding confirmed on-chain and all balances are enough.")
    print("[INFO] Starting replay now.")

    send_results, send_duration = send_replay_transactions(replay_plan)
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
