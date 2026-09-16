from web3 import Web3

RPC = "http://el-01-geth-lighthouse:8545"

MASTER_PRIVATE_KEY = (
    "bcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31"
)

# Your CURRENT local USDT address
USDT_LOCAL = "0xb4B46bdAA835F8E4b4d8e208B6559cD267851051"

w3 = Web3(Web3.HTTPProvider(RPC))

if not w3.is_connected():
    raise RuntimeError("Cannot connect to geth")

account = w3.eth.account.from_key(
    MASTER_PRIVATE_KEY
)

master = Web3.to_checksum_address(
    account.address
)

usdt_address = Web3.to_checksum_address(
    USDT_LOCAL
)

ABI = [
    {
        "constant": True,
        "inputs": [
            {
                "name": "_owner",
                "type": "address"
            }
        ],
        "name": "balanceOf",
        "outputs": [
            {
                "name": "balance",
                "type": "uint256"
            }
        ],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {
                "name": "amount",
                "type": "uint256"
            }
        ],
        "name": "issue",
        "outputs": [],
        "type": "function"
    }
]

usdt = w3.eth.contract(
    address=usdt_address,
    abi=ABI
)

# ============================================================
# Check current balance
# ============================================================

before = usdt.functions.balanceOf(
    master
).call()

print("Master:", master)

print(
    "USDT before:",
    before / 1_000_000
)

# ============================================================
# Mint an additional 10,000,000 USDT
#
# USDT has 6 decimals
# ============================================================

MINT_USDT = 100_000_000

mint_raw = (
    MINT_USDT
    * 10**6
)

nonce = w3.eth.get_transaction_count(
    master,
    "pending"
)

tx = usdt.functions.issue(
    mint_raw
).build_transaction({
    "from":
        master,

    "nonce":
        nonce,

    "gas":
        200000,

    "gasPrice":
        w3.to_wei(
            10,
            "gwei"
        ),

    "chainId":
        w3.eth.chain_id,
})

signed = w3.eth.account.sign_transaction(
    tx,
    MASTER_PRIVATE_KEY
)

tx_hash = w3.eth.send_raw_transaction(
    signed.raw_transaction
)

print(
    "TX:",
    tx_hash.hex()
)

receipt = (
    w3.eth.wait_for_transaction_receipt(
        tx_hash,
        timeout=600
    )
)

print(
    "Status:",
    receipt.status
)

# ============================================================
# Verify new balance
# ============================================================

after = usdt.functions.balanceOf(
    master
).call()

print(
    "USDT after:",
    after / 1_000_000
)

print(
    "Increase:",
    (after - before) / 1_000_000
)