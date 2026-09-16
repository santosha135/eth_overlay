#!/usr/bin/env node

const { Web3 } = require("web3");
const fs = require("fs");

// ============================================================
// Configuration
// ============================================================

const RPC_URL =
    process.env.RPC_URL ||
    "http://el-01-geth-lighthouse:8545";

const ABI_PATH =
    process.env.ABI_PATH ||
    "/root/attack_testbed/artifacts/contracts/resource_ex_att_contract.sol/resource_ex_att_contract.json";

const CONTRACT_ADDRESS =
    process.env.CONTRACT_ADDRESS ||
    "0xb4B46bdAA835F8E4b4d8e208B6559cD267851051";

const MASTER_ADDRESS =
    process.env.MASTER_ADDRESS ||
    "0x2c57d1CFC6d5f8E4182a56b4cf75421472eBAEa4";

// Do not hard-code the private key in the source file.
const MASTER_PRIVATE_KEY = process.env.MASTER_PRIVATE_KEY ||
		"0x7ff1a4c1d57e5e784d327c4c7651e952350bc271f156afb3d00d20f5ef924856";

const ACCOUNT_COUNT = Number(process.env.ACCOUNT_COUNT || 200);

// One contract transaction from each generated account.
const TRANSACTIONS_PER_ACCOUNT = Number(
    process.env.TRANSACTIONS_PER_ACCOUNT || 1
);

const COMPLEXITY = Number(process.env.COMPLEXITY || 500);

const CONTRACT_GAS_LIMIT = BigInt(
    process.env.CONTRACT_GAS_LIMIT || "600000"
);

const GAS_PRICE_GWEI =
    process.env.GAS_PRICE_GWEI || "300";

// Each child account needs enough ETH for:
//
// 600,000 gas × 300 gwei = maximum 0.18 ETH
//
// Default funding is therefore 0.25 ETH per account.
const FUND_AMOUNT_ETH =
    process.env.FUND_AMOUNT_ETH || "0.25";

const ACCOUNTS_FILE =
    process.env.ACCOUNTS_FILE || "generated_200_accounts.json";

const web3 = new Web3(RPC_URL);

// ============================================================
// Validation
// ============================================================

function validateConfiguration() {
    if (!MASTER_PRIVATE_KEY) {
        throw new Error(
            "MASTER_PRIVATE_KEY is missing. Set it as an environment variable."
        );
    }

    if (!/^0x[0-9a-fA-F]{64}$/.test(MASTER_PRIVATE_KEY)) {
        throw new Error(
            "MASTER_PRIVATE_KEY must start with 0x and contain 64 hexadecimal characters."
        );
    }

    if (!Number.isInteger(ACCOUNT_COUNT) || ACCOUNT_COUNT <= 0) {
        throw new Error("ACCOUNT_COUNT must be a positive integer.");
    }

    if (
        !Number.isInteger(TRANSACTIONS_PER_ACCOUNT) ||
        TRANSACTIONS_PER_ACCOUNT <= 0
    ) {
        throw new Error(
            "TRANSACTIONS_PER_ACCOUNT must be a positive integer."
        );
    }
}

function verifyMasterWallet() {
    const derivedAccount =
        web3.eth.accounts.privateKeyToAccount(MASTER_PRIVATE_KEY);

    if (
        derivedAccount.address.toLowerCase() !==
        MASTER_ADDRESS.toLowerCase()
    ) {
        throw new Error(
            [
                "The provided private key does not match MASTER_ADDRESS.",
                `Configured address: ${MASTER_ADDRESS}`,
                `Derived address:    ${derivedAccount.address}`
            ].join("\n")
        );
    }
}

// ============================================================
// Wallet generation
// ============================================================

function generateAccounts(count) {
    const accounts = [];

    for (let index = 0; index < count; index++) {
        const account = web3.eth.accounts.create();

        accounts.push({
            index,
            address: account.address,
            privateKey: account.privateKey
        });
    }

    fs.writeFileSync(
        ACCOUNTS_FILE,
        JSON.stringify(accounts, null, 2),
        {
            encoding: "utf8",
            mode: 0o600
        }
    );

    console.log(
        `Generated ${accounts.length} accounts and saved them to ${ACCOUNTS_FILE}`
    );

    return accounts;
}

// ============================================================
// Raw transaction broadcasting
// ============================================================

function broadcastSignedTransaction(rawTransaction, description) {
    return new Promise((resolve, reject) => {
        let transactionHash = null;

        web3.eth
            .sendSignedTransaction(rawTransaction)
            .once("transactionHash", hash => {
                transactionHash = hash;
                console.log(`${description}: submitted ${hash}`);
            })
            .once("receipt", receipt => {
                resolve({
                    transactionHash:
                        receipt.transactionHash || transactionHash,
                    blockNumber: receipt.blockNumber,
                    status: receipt.status,
                    gasUsed: receipt.gasUsed
                });
            })
            .once("error", error => {
                reject({
                    description,
                    transactionHash,
                    error
                });
            });
    });
}

// ============================================================
// Funding
// ============================================================

async function checkMasterBalance(fundAmountWei, gasPriceWei) {
    const masterBalance = BigInt(
        await web3.eth.getBalance(MASTER_ADDRESS)
    );

    const fundingValueRequired =
        fundAmountWei * BigInt(ACCOUNT_COUNT);

    const fundingGasRequired =
        21000n * gasPriceWei * BigInt(ACCOUNT_COUNT);

    const requiredBalance =
        fundingValueRequired + fundingGasRequired;

    console.log(
        `Master balance: ${web3.utils.fromWei(masterBalance.toString(), "ether")} ETH`
    );

    console.log(
        `Estimated funding requirement: ${web3.utils.fromWei(
            requiredBalance.toString(),
            "ether"
        )} ETH`
    );

    if (masterBalance < requiredBalance) {
        throw new Error(
            [
                "Master wallet does not have enough balance.",
                `Required: ${web3.utils.fromWei(
                    requiredBalance.toString(),
                    "ether"
                )} ETH`,
                `Available: ${web3.utils.fromWei(
                    masterBalance.toString(),
                    "ether"
                )} ETH`
            ].join("\n")
        );
    }
}

async function fundAccounts(
    accounts,
    chainId,
    gasPriceWei,
    fundAmountWei
) {
    console.log(
        `\nPreparing ${accounts.length} funding transactions...`
    );

    const startingNonce = BigInt(
        await web3.eth.getTransactionCount(
            MASTER_ADDRESS,
            "pending"
        )
    );

    const signedTransactions = [];

    // Sign funding transactions with consecutive master-wallet nonces.
    for (let index = 0; index < accounts.length; index++) {
        const account = accounts[index];

        const transaction = {
            from: MASTER_ADDRESS,
            to: account.address,
            value: fundAmountWei.toString(),
            gas: "21000",
            gasPrice: gasPriceWei.toString(),
            nonce: (startingNonce + BigInt(index)).toString(),
            chainId: Number(chainId)
        };

        const signed =
            await web3.eth.accounts.signTransaction(
                transaction,
                MASTER_PRIVATE_KEY
            );

        if (!signed.rawTransaction) {
            throw new Error(
                `Failed to sign funding transaction ${index}`
            );
        }

        signedTransactions.push({
            index,
            address: account.address,
            rawTransaction: signed.rawTransaction
        });
    }

    console.log(
        `Broadcasting all ${signedTransactions.length} funding transactions...`
    );

    const fundingPromises = signedTransactions.map(item =>
        broadcastSignedTransaction(
            item.rawTransaction,
            `Funding account ${item.index + 1}/${accounts.length} ${item.address}`
        )
    );

    const results = await Promise.allSettled(fundingPromises);

    const successful = results.filter(
        result =>
            result.status === "fulfilled" &&
            result.value.status !== false
    );

    const failed = results.filter(
        result =>
            result.status === "rejected" ||
            result.value?.status === false
    );

    console.log("\nFunding completed.");
    console.log(`Successful funding transactions: ${successful.length}`);
    console.log(`Failed funding transactions:     ${failed.length}`);

    if (failed.length > 0) {
        failed.slice(0, 10).forEach((result, index) => {
            if (result.status === "rejected") {
                console.error(
                    `Funding failure ${index + 1}:`,
                    result.reason?.error?.message ||
                    result.reason?.error ||
                    result.reason
                );
            }
        });

        throw new Error(
            "Some accounts were not funded. Contract calls were not started."
        );
    }
}

// ============================================================
// Contract transactions
// ============================================================

async function prepareContractTransactions(
    accounts,
    contract,
    chainId,
    gasPriceWei
) {
    const encodedCall =
        contract.methods.DoS(COMPLEXITY).encodeABI();

    const signedTransactions = [];

    console.log(
        `\nPreparing ${
            accounts.length * TRANSACTIONS_PER_ACCOUNT
        } contract transactions...`
    );

    for (
        let accountIndex = 0;
        accountIndex < accounts.length;
        accountIndex++
    ) {
        const account = accounts[accountIndex];

        const startingNonce = BigInt(
            await web3.eth.getTransactionCount(
                account.address,
                "pending"
            )
        );

        for (
            let txIndex = 0;
            txIndex < TRANSACTIONS_PER_ACCOUNT;
            txIndex++
        ) {
            const nonce =
                startingNonce + BigInt(txIndex);

            const transaction = {
                from: account.address,
                to: CONTRACT_ADDRESS,
                value: "0",
                gas: CONTRACT_GAS_LIMIT.toString(),
                gasPrice: gasPriceWei.toString(),
                nonce: nonce.toString(),
                chainId: Number(chainId),
                data: encodedCall
            };

            const signed =
                await web3.eth.accounts.signTransaction(
                    transaction,
                    account.privateKey
                );

            if (!signed.rawTransaction) {
                throw new Error(
                    `Failed to sign transaction for account ${account.address}`
                );
            }

            signedTransactions.push({
                accountIndex,
                txIndex,
                address: account.address,
                nonce,
                rawTransaction: signed.rawTransaction
            });
        }
    }

    return signedTransactions;
}

async function sendAllAccountsAtOnce(signedTransactions) {
    console.log("\n==================================================");
    console.log(
        `Broadcasting ${signedTransactions.length} transactions concurrently`
    );
    console.log("==================================================\n");

    const startTime = Date.now();

    // Calling map starts every RPC submission without waiting for
    // previous accounts to finish.
    const transactionPromises = signedTransactions.map(item =>
        broadcastSignedTransaction(
            item.rawTransaction,
            `Account ${item.accountIndex + 1}, transaction ${item.txIndex + 1}`
        )
    );

    const results =
        await Promise.allSettled(transactionPromises);

    const endTime = Date.now();

    const successful = results.filter(
        result =>
            result.status === "fulfilled" &&
            result.value.status !== false
    );

    const reverted = results.filter(
        result =>
            result.status === "fulfilled" &&
            result.value.status === false
    );

    const failed = results.filter(
        result => result.status === "rejected"
    );

    console.log("\n==================================================");
    console.log("Concurrent transaction test completed");
    console.log("==================================================");
    console.log(`Total transactions: ${results.length}`);
    console.log(`Successful:         ${successful.length}`);
    console.log(`Reverted:           ${reverted.length}`);
    console.log(`RPC/send failures:  ${failed.length}`);
    console.log(
        `Elapsed time:       ${((endTime - startTime) / 1000).toFixed(3)} seconds`
    );

    if (failed.length > 0) {
        console.log("\nFirst send failures:");

        failed.slice(0, 20).forEach((result, index) => {
            console.error(
                `${index + 1}.`,
                result.reason?.error?.message ||
                result.reason?.error ||
                result.reason
            );
        });
    }

    const output = results.map((result, index) => {
        const input = signedTransactions[index];

        if (result.status === "fulfilled") {
            return {
                accountIndex: input.accountIndex,
                address: input.address,
                transactionIndex: input.txIndex,
                nonce: input.nonce.toString(),
                success: result.value.status !== false,
                transactionHash:
                    result.value.transactionHash,
                blockNumber:
                    result.value.blockNumber?.toString(),
                gasUsed:
                    result.value.gasUsed?.toString(),
                error: null
            };
        }

        return {
            accountIndex: input.accountIndex,
            address: input.address,
            transactionIndex: input.txIndex,
            nonce: input.nonce.toString(),
            success: false,
            transactionHash:
                result.reason?.transactionHash || null,
            blockNumber: null,
            gasUsed: null,
            error:
                result.reason?.error?.message ||
                String(result.reason?.error || result.reason)
        };
    });

    fs.writeFileSync(
        "concurrent_transaction_results.json",
        JSON.stringify(output, null, 2),
        "utf8"
    );

    console.log(
        "Results saved to concurrent_transaction_results.json"
    );
}

// ============================================================
// Main
// ============================================================

async function main() {
    validateConfiguration();
    verifyMasterWallet();

    const artifact = require(ABI_PATH);
    const contractABI = artifact.abi;

    if (!contractABI) {
        throw new Error(
            `ABI was not found in ${ABI_PATH}`
        );
    }

    const contract = new web3.eth.Contract(
        contractABI,
        CONTRACT_ADDRESS
    );

    const chainId = await web3.eth.getChainId();

    const gasPriceWei = BigInt(
        web3.utils.toWei(GAS_PRICE_GWEI, "gwei")
    );

    const fundAmountWei = BigInt(
        web3.utils.toWei(FUND_AMOUNT_ETH, "ether")
    );

    console.log(`RPC:                 ${RPC_URL}`);
    console.log(`Chain ID:            ${chainId}`);
    console.log(`Master address:      ${MASTER_ADDRESS}`);
    console.log(`Contract address:    ${CONTRACT_ADDRESS}`);
    console.log(`Accounts:            ${ACCOUNT_COUNT}`);
    console.log(`Transactions/account:${TRANSACTIONS_PER_ACCOUNT}`);
    console.log(`Complexity:          ${COMPLEXITY}`);
    console.log(`Gas limit:           ${CONTRACT_GAS_LIMIT}`);
    console.log(`Gas price:           ${GAS_PRICE_GWEI} gwei`);
    console.log(`Funding/account:     ${FUND_AMOUNT_ETH} ETH`);

    await checkMasterBalance(
        fundAmountWei,
        gasPriceWei
    );

    const accounts = generateAccounts(ACCOUNT_COUNT);

    await fundAccounts(
        accounts,
        chainId,
        gasPriceWei,
        fundAmountWei
    );

    const signedContractTransactions =
        await prepareContractTransactions(
            accounts,
            contract,
            chainId,
            gasPriceWei
        );

    await sendAllAccountsAtOnce(
        signedContractTransactions
    );
}

main()
    .then(() => {
        console.log("\nTest finished.");
        process.exit(0);
    })
    .catch(error => {
        console.error("\nFatal error:");
        console.error(error);
        process.exit(1);
    });