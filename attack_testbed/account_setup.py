import json
import os
import time
from web3 import Web3

# ----------------- CONFIGURATION -----------------
GETH_URL = 'http://127.0.0.1:32003'
MASTER_PRIVATE_KEY = 'bcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31'
PRIVATE_KEYS_FILE = 'wallet_private_keys.json'
INITIAL_FUND_ETH = 0.05
GAS_LIMIT = 21000
GAS_PRICE_GWEI = 10
NUM_ACCOUNTS = 10  # Number of accounts to create

# ----------------- WEB3 SETUP -----------------
web3 = Web3(Web3.HTTPProvider(GETH_URL))
if not web3.is_connected():
    raise Exception("Geth is not connected")

master_account = web3.eth.account.from_key(MASTER_PRIVATE_KEY)
master_address = master_account.address
print(f"[INFO] Connected. Master wallet: {master_address}")

# ----------------- PRIVATE KEYS -----------------
def load_private_keys():
    if os.path.exists(PRIVATE_KEYS_FILE):
        with open(PRIVATE_KEYS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_private_keys(private_keys):
    with open(PRIVATE_KEYS_FILE, 'w') as f:
        json.dump(private_keys, f, indent=4)

private_keys = load_private_keys()

# ----------------- CREATE & FUND ACCOUNTS -----------------
def create_account(private_keys, initial_fund_wei):
    account = web3.eth.account.create()
    address = account.address
    key = account.key.hex()
    private_keys[address] = key
    save_private_keys(private_keys)
    print(f"[ACCOUNT] Created: {address}")

    # Fund the account from master wallet
    tx = {
        'from': master_address,
        'to': address,
        'value': initial_fund_wei,
        'gas': GAS_LIMIT,
        'gasPrice': web3.to_wei(GAS_PRICE_GWEI, 'gwei'),
        'nonce': web3.eth.get_transaction_count(master_address),
        'chainId': web3.eth.chain_id
    }
    signed_tx = web3.eth.account.sign_transaction(tx, MASTER_PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    web3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"[FUNDED] {web3.from_wei(initial_fund_wei,'ether')} ETH | TX: {tx_hash.hex()}")
    time.sleep(0.5)
    return address, key

# ----------------- RUN -----------------
initial_fund_wei = web3.to_wei(INITIAL_FUND_ETH, 'ether')
for i in range(NUM_ACCOUNTS):
    create_account(private_keys, initial_fund_wei)

print(f"[DONE] {NUM_ACCOUNTS} accounts created and funded.")
