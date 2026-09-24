#!/usr/bin/env node

const { Web3 } = require("web3");
const fs = require("fs");

// ============================================================
// CONFIGURATION
// ============================================================

const CONTROL_RPC =
    process.env.RPC_URL ||
    "http://el-01-geth-lighthouse:8545";

const MASTER_ADDRESS =
    process.env.MASTER_ADDRESS ||
    "0x2c57d1CFC6d5f8E4182a56b4cf75421472eBAEa4";

// SECURITY:
// Do not hard-code your private key.
//
// Run:
//
// export MASTER_PRIVATE_KEY="0x...."
//
// const MASTER_PRIVATE_KEY =
//     process.env.MASTER_PRIVATE_KEY || "";
const MASTER_PRIVATE_KEY = process.env.MASTER_PRIVATE_KEY ||
		"0x7ff1a4c1d57e5e784d327c4c7651e952350bc271f156afb3d00d20f5ef924856";

// ============================================================
// ACCOUNT CONFIGURATION
// ============================================================

const ACCOUNT_COUNT =
    Number(
        process.env.ACCOUNT_COUNT ||
        1000
    );

// ============================================================
// FUNDING CONFIGURATION
// ============================================================

const FUND_AMOUNT_ETH =
    process.env.FUND_AMOUNT_ETH ||
    "0.25";

const FUND_GAS_PRICE_GWEI =
    process.env.FUND_GAS_PRICE_GWEI ||
    "1";

// Number of funding transactions submitted together.
//
// Recommended:
// 10-50.
//
// Start with 25.
const FUNDING_BATCH_SIZE =
    Number(
        process.env.FUNDING_BATCH_SIZE ||
        25
    );

// ============================================================
// NONCE/BALANCE READ BATCH
// ============================================================

const READ_BATCH_SIZE =
    Number(
        process.env.READ_BATCH_SIZE ||
        100
    );

// ============================================================
// OUTPUT
// ============================================================

const ACCOUNTS_FILE =
    process.env.ACCOUNTS_FILE ||
    "generated_1000_accounts.json";

// Optional setup report.
const SETUP_REPORT_FILE =
    process.env.SETUP_REPORT_FILE ||
    "account_setup_report.csv";

// ============================================================
// WEB3
// ============================================================

const web3 =
    new Web3(
        CONTROL_RPC
    );

// ============================================================
// HELPERS
// ============================================================

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


function escapeCSV(value) {

    return `"${String(value ?? "")
        .replace(/"/g, '""')}"`;
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
            "Set it with:\n" +
            "export MASTER_PRIVATE_KEY='0x...'"
        );
    }

    if (
        !Number.isInteger(ACCOUNT_COUNT) ||
        ACCOUNT_COUNT <= 0
    ) {

        throw new Error(
            "ACCOUNT_COUNT must be a positive integer."
        );
    }

    if (
        !Number.isInteger(FUNDING_BATCH_SIZE) ||
        FUNDING_BATCH_SIZE <= 0
    ) {

        throw new Error(
            "FUNDING_BATCH_SIZE must be a positive integer."
        );
    }

    if (
        !Number.isInteger(READ_BATCH_SIZE) ||
        READ_BATCH_SIZE <= 0
    ) {

        throw new Error(
            "READ_BATCH_SIZE must be a positive integer."
        );
    }
}

// ============================================================
// VERIFY MASTER PRIVATE KEY
// ============================================================

function verifyMasterWallet() {

    const derived =
        web3.eth.accounts
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
                `Configured : ${MASTER_ADDRESS}`,
                `Derived    : ${derived.address}`
            ].join("\n")
        );
    }

    console.log(
        `Master wallet verified: ${MASTER_ADDRESS}`
    );
}

// ============================================================
// RPC CHECK
// ============================================================

async function checkRPC() {

    console.log(
        "\n============================================================"
    );

    console.log(
        "CHECKING RPC"
    );

    console.log(
        "============================================================"
    );

    const block =
        await web3.eth
            .getBlockNumber();

    const chainId =
        await web3.eth
            .getChainId();

    console.log(
        `RPC      : ${CONTROL_RPC}`
    );

    console.log(
        `Block    : ${block}`
    );

    console.log(
        `Chain ID : ${chainId}`
    );

    return chainId;
}

// ============================================================
// CHECK MASTER BALANCE
// ============================================================

async function checkMasterBalance(
    fundAmountWei,
    fundingGasPriceWei
) {

    console.log(
        "\n============================================================"
    );

    console.log(
        "MASTER BALANCE"
    );

    console.log(
        "============================================================"
    );

    const balance =
        BigInt(
            await web3.eth
                .getBalance(
                    MASTER_ADDRESS
                )
        );

    const totalFunding =
        fundAmountWei *
        BigInt(
            ACCOUNT_COUNT
        );

    const totalGas =
        21000n *
        fundingGasPriceWei *
        BigInt(
            ACCOUNT_COUNT
        );

    const required =
        totalFunding +
        totalGas;

    console.log(
        `Available : ${web3.utils.fromWei(
            balance.toString(),
            "ether"
        )} ETH`
    );

    console.log(
        `Funding   : ${web3.utils.fromWei(
            totalFunding.toString(),
            "ether"
        )} ETH`
    );

    console.log(
        `Gas est.  : ${web3.utils.fromWei(
            totalGas.toString(),
            "ether"
        )} ETH`
    );

    console.log(
        `Required  : ${web3.utils.fromWei(
            required.toString(),
            "ether"
        )} ETH`
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
// GENERATE ACCOUNTS
// ============================================================

function generateAccounts() {

    console.log(
        "\n============================================================"
    );

    console.log(
        `GENERATING ${ACCOUNT_COUNT} ACCOUNTS`
    );

    console.log(
        "============================================================"
    );

    const accounts =
        [];

    for (
        let i = 0;
        i < ACCOUNT_COUNT;
        i++
    ) {

        const wallet =
            web3.eth.accounts
                .create();

        accounts.push({

            index:
                i,

            address:
                wallet.address,

            privateKey:
                wallet.privateKey
        });

        if (
            (i + 1) % 100 === 0 ||
            i === ACCOUNT_COUNT - 1
        ) {

            console.log(
                `Generated ${i + 1}/${ACCOUNT_COUNT}`
            );
        }
    }

    return accounts;
}

// ============================================================
// SAVE ACCOUNTS
// ============================================================

function saveAccounts(
    accounts
) {

    fs.writeFileSync(

        ACCOUNTS_FILE,

        JSON.stringify(
            accounts,
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
        "\n============================================================"
    );

    console.log(
        "ACCOUNTS SAVED"
    );

    console.log(
        "============================================================"
    );

    console.log(
        `File     : ${ACCOUNTS_FILE}`
    );

    console.log(
        `Accounts : ${accounts.length}`
    );

    console.log(
        "File mode: 0600"
    );
}

// ============================================================
// FUND ONE ACCOUNT
// ============================================================

// async function fundOneAccount(
//     account,
//     accountIndex,
//     nonce,
//     chainId,
//     fundAmountWei,
//     fundingGasPriceWei
// ) {

//     const transaction = {

//         from:
//             MASTER_ADDRESS,

//         to:
//             account.address,

//         value:
//             fundAmountWei.toString(),

//         gas:
//             "21000",

//         gasPrice:
//             fundingGasPriceWei.toString(),

//         nonce:
//             nonce.toString(),

//         chainId:
//             Number(chainId)
//     };

//     const signed =
//         await web3.eth.accounts
//             .signTransaction(
//                 transaction,
//                 MASTER_PRIVATE_KEY
//             );

//     if (
//         !signed.rawTransaction
//     ) {

//         throw new Error(
//             `Unable to sign funding transaction for account ${accountIndex + 1}`
//         );
//     }

//     // --------------------------------------------------------
//     // Send using raw JSON-RPC.
//     //
//     // This returns as soon as Geth accepts the transaction.
//     // We do NOT wait for every transaction receipt here.
//     // --------------------------------------------------------

//     const hash =
//         await web3.request({

//             method:
//                 "eth_sendRawTransaction",

//             params:
//                 [
//                     signed.rawTransaction
//                 ]
//         });

//     console.log(
//         `[FUND] ` +
//         `${accountIndex + 1}/${ACCOUNT_COUNT} ` +
//         `nonce=${nonce} ` +
//         `address=${account.address} ` +
//         `hash=${hash}`
//     );

//     return {

//         accountIndex,

//         address:
//             account.address,

//         nonce,

//         hash
//     };
// }
async function fundOneAccount(
    account,
    accountIndex,
    nonce,
    chainId,
    fundAmountWei,
    fundingGasPriceWei
) {
    const transaction = {
        from: MASTER_ADDRESS,
        to: account.address,
        value: fundAmountWei.toString(),
        gas: "21000",
        gasPrice: fundingGasPriceWei.toString(),
        nonce: nonce.toString(),
        chainId: Number(chainId)
    };

    // ========================================================
    // SIGN FUNDING TRANSACTION
    // ========================================================

    const signed =
        await web3.eth.accounts.signTransaction(
            transaction,
            MASTER_PRIVATE_KEY
        );

    if (!signed.rawTransaction) {
        throw new Error(
            `Unable to sign funding transaction for account ${accountIndex + 1}`
        );
    }

    // ========================================================
    // BROADCAST
    //
    // IMPORTANT:
    // Do not use:
    //
    //     web3.request(...)
    //
    // because your Web3 instance does not expose request().
    //
    // sendSignedTransaction() is supported by your installed
    // Web3 version.
    //
    // Resolve as soon as transactionHash is returned.
    // We DO NOT wait for the receipt here.
    // ========================================================

    return new Promise((resolve, reject) => {

        let finished = false;

        const finishSuccess = (hash) => {

            if (finished) {
                return;
            }

            finished = true;

            console.log(
                `[FUND] ` +
                `${accountIndex + 1}/${ACCOUNT_COUNT} ` +
                `nonce=${nonce} ` +
                `address=${account.address} ` +
                `hash=${hash}`
            );

            resolve({
                accountIndex,
                address: account.address,
                nonce,
                hash
            });
        };

        const finishError = (error) => {

            if (finished) {
                return;
            }

            finished = true;

            console.error(
                `[FUND ERROR] ` +
                `account=${accountIndex + 1} ` +
                `nonce=${nonce} ` +
                `address=${account.address} ` +
                `error=${getErrorMessage(error)}`
            );

            reject(error);
        };

        try {

            const promiEvent =
                web3.eth.sendSignedTransaction(
                    signed.rawTransaction
                );

            promiEvent.once(
                "transactionHash",
                hash => {
                    finishSuccess(hash);
                }
            );

            promiEvent.once(
                "error",
                error => {
                    finishError(error);
                }
            );

            // Some Web3 versions also expose the PromiEvent
            // as a thenable Promise. Attach a rejection handler
            // so an RPC error cannot become an unhandled
            // promise rejection.
            if (
                promiEvent &&
                typeof promiEvent.catch === "function"
            ) {
                promiEvent.catch(
                    error => {
                        finishError(error);
                    }
                );
            }

        } catch (error) {

            finishError(error);
        }
    });
}

// ============================================================
// WAIT UNTIL MASTER NONCE ADVANCES
// ============================================================

async function waitForFundingConfirmation(
    expectedNonce,
    timeoutSeconds = 120
) {

    const deadline =
        Date.now() +
        (
            timeoutSeconds *
            1000
        );

    while (
        Date.now() <
        deadline
    ) {

        const latestNonce =
            BigInt(
                await web3.eth
                    .getTransactionCount(
                        MASTER_ADDRESS,
                        "latest"
                    )
            );

        console.log(
            `[WAIT] master latest nonce=${latestNonce}, ` +
            `expected>=${expectedNonce}`
        );

        if (
            latestNonce >=
            expectedNonce
        ) {

            return true;
        }

        await new Promise(
            resolve =>
                setTimeout(
                    resolve,
                    1000
                )
        );
    }

    return false;
}

// ============================================================
// FUND ACCOUNTS
// ============================================================

async function fundAccounts(
    accounts,
    chainId,
    fundAmountWei,
    fundingGasPriceWei
) {

    console.log(
        "\n============================================================"
    );

    console.log(
        "PARALLEL/BATCHED ACCOUNT FUNDING"
    );

    console.log(
        "============================================================"
    );

    console.log(
        `Accounts        : ${accounts.length}`
    );

    console.log(
        `Batch size      : ${FUNDING_BATCH_SIZE}`
    );

    const startingNonce =
        BigInt(
            await web3.eth
                .getTransactionCount(
                    MASTER_ADDRESS,
                    "pending"
                )
        );

    console.log(
        `Starting master pending nonce: ${startingNonce}`
    );

    const fundingResults =
        [];

    // ========================================================
    // BATCH LOOP
    // ========================================================

    for (
        let start = 0;
        start < accounts.length;
        start += FUNDING_BATCH_SIZE
    ) {

        const end =
            Math.min(
                start +
                FUNDING_BATCH_SIZE,

                accounts.length
            );

        console.log(
            "\n------------------------------------------------------------"
        );

        console.log(
            `Funding accounts ${start + 1}-${end}`
        );

        console.log(
            "------------------------------------------------------------"
        );

        const batch =
            [];

        for (
            let i = start;
            i < end;
            i++
        ) {

            // Every funding transaction gets its own
            // unique master nonce.
            const nonce =
                startingNonce +
                BigInt(i);

            batch.push(

                fundOneAccount(

                    accounts[i],

                    i,

                    nonce,

                    chainId,

                    fundAmountWei,

                    fundingGasPriceWei
                )
            );
        }

        // Submit this group concurrently.
        const results =
            await Promise.all(
                batch
            );

        fundingResults.push(
            ...results
        );

        console.log(
            `[BATCH ACCEPTED] ${end}/${accounts.length}`
        );
    }

    console.log(
        "\n============================================================"
    );

    console.log(
        "ALL FUNDING TRANSACTIONS SUBMITTED"
    );

    console.log(
        "============================================================"
    );

    const expectedFinalMasterNonce =
        startingNonce +
        BigInt(
            accounts.length
        );

    console.log(
        `Waiting until master latest nonce reaches ${expectedFinalMasterNonce}...`
    );

    const confirmed =
        await waitForFundingConfirmation(
            expectedFinalMasterNonce,
            180
        );

    if (
        !confirmed
    ) {

        throw new Error(
            "Timed out waiting for all funding transactions to be mined."
        );
    }

    console.log(
        "\nAll funding transactions have been consumed/mined."
    );

    return fundingResults;
}

// ============================================================
// VERIFY ACCOUNTS
// ============================================================

async function verifyAccounts(
    accounts
) {

    console.log(
        "\n============================================================"
    );

    console.log(
        "VERIFYING FUNDED ACCOUNTS"
    );

    console.log(
        "============================================================"
    );

    const results =
        [];

    let funded =
        0;

    let zeroBalance =
        0;

    let totalBalance =
        0n;

    for (
        let start = 0;
        start < accounts.length;
        start += READ_BATCH_SIZE
    ) {

        const end =
            Math.min(
                start +
                READ_BATCH_SIZE,

                accounts.length
            );

        const batchAccounts =
            accounts.slice(
                start,
                end
            );

        const batchResults =
            await Promise.all(

                batchAccounts.map(

                    async (
                        account,
                        offset
                    ) => {

                        const index =
                            start +
                            offset;

                        const [
                            balanceRaw,
                            latestNonceRaw,
                            pendingNonceRaw
                        ] =
                            await Promise.all([

                                web3.eth
                                    .getBalance(
                                        account.address
                                    ),

                                web3.eth
                                    .getTransactionCount(
                                        account.address,
                                        "latest"
                                    ),

                                web3.eth
                                    .getTransactionCount(
                                        account.address,
                                        "pending"
                                    )
                            ]);

                        const balance =
                            BigInt(
                                balanceRaw
                            );

                        return {

                            index,

                            address:
                                account.address,

                            balance,

                            latestNonce:
                                BigInt(
                                    latestNonceRaw
                                ),

                            pendingNonce:
                                BigInt(
                                    pendingNonceRaw
                                )
                        };
                    }
                )
            );

        for (
            const result of batchResults
        ) {

            results.push(
                result
            );

            totalBalance +=
                result.balance;

            if (
                result.balance >
                0n
            ) {

                funded++;

            } else {

                zeroBalance++;
            }
        }

        console.log(
            `Verified ${end}/${accounts.length}`
        );
    }

    console.log(
        "\n============================================================"
    );

    console.log(
        "VERIFICATION SUMMARY"
    );

    console.log(
        "============================================================"
    );

    console.log(
        `Total accounts       : ${accounts.length}`
    );

    console.log(
        `Funded accounts      : ${funded}`
    );

    console.log(
        `Zero balance         : ${zeroBalance}`
    );

    console.log(
        `Total balance        : ` +
        `${web3.utils.fromWei(
            totalBalance.toString(),
            "ether"
        )} ETH`
    );

    console.log(
        "============================================================"
    );

    return results;
}

// ============================================================
// SAVE SETUP REPORT
// ============================================================

function saveSetupReport(
    results
) {

    const header = [

        "account_index",

        "address",

        "balance_wei",

        "balance_eth",

        "latest_nonce",

        "pending_nonce"

    ].join(",");

    const rows =
        [
            header
        ];

    for (
        const result of results
    ) {

        rows.push(

            [

                result.index + 1,

                escapeCSV(
                    result.address
                ),

                result.balance.toString(),

                escapeCSV(
                    web3.utils.fromWei(
                        result.balance.toString(),
                        "ether"
                    )
                ),

                result.latestNonce.toString(),

                result.pendingNonce.toString()

            ].join(",")
        );
    }

    fs.writeFileSync(
        SETUP_REPORT_FILE,
        rows.join("\n") + "\n",
        "utf8"
    );

    console.log(
        `Setup report: ${SETUP_REPORT_FILE}`
    );
}

// ============================================================
// MAIN
// ============================================================

async function main() {

    console.log(
        "\n============================================================"
    );

    console.log(
        "ACCOUNT CREATION + FUNDING SETUP"
    );

    console.log(
        "============================================================"
    );

    validateConfiguration();

    verifyMasterWallet();

    // ========================================================
    // RPC / CHAIN
    // ========================================================

    const chainId =
        await checkRPC();

    // ========================================================
    // VALUES
    // ========================================================

    const fundAmountWei =
        BigInt(
            web3.utils.toWei(
                FUND_AMOUNT_ETH,
                "ether"
            )
        );

    const fundingGasPriceWei =
        BigInt(
            web3.utils.toWei(
                FUND_GAS_PRICE_GWEI,
                "gwei"
            )
        );

    // ========================================================
    // CONFIGURATION
    // ========================================================

    console.log(
        "\n============================================================"
    );

    console.log(
        "SETUP CONFIGURATION"
    );

    console.log(
        "============================================================"
    );

    console.log(
        `RPC                 : ${CONTROL_RPC}`
    );

    console.log(
        `Master              : ${MASTER_ADDRESS}`
    );

    console.log(
        `Chain ID            : ${chainId}`
    );

    console.log(
        `Accounts            : ${ACCOUNT_COUNT}`
    );

    console.log(
        `Funding/account     : ${FUND_AMOUNT_ETH} ETH`
    );

    console.log(
        `Funding gas         : ${FUND_GAS_PRICE_GWEI} gwei`
    );

    console.log(
        `Funding batch       : ${FUNDING_BATCH_SIZE}`
    );

    console.log(
        `Account file        : ${ACCOUNTS_FILE}`
    );

    console.log(
        "============================================================"
    );

    // ========================================================
    // CHECK MASTER FUNDS
    // ========================================================

    await checkMasterBalance(
        fundAmountWei,
        fundingGasPriceWei
    );

    // ========================================================
    // CREATE
    // ========================================================

    const accounts =
        generateAccounts();

    // Save BEFORE funding.
    //
    // This means that if funding fails partway through,
    // the generated account keys are not lost.
    saveAccounts(
        accounts
    );

    // ========================================================
    // FUND
    // ========================================================

    await fundAccounts(
        accounts,
        chainId,
        fundAmountWei,
        fundingGasPriceWei
    );

    // ========================================================
    // VERIFY
    // ========================================================

    const verification =
        await verifyAccounts(
            accounts
        );

    // ========================================================
    // REPORT
    // ========================================================

    saveSetupReport(
        verification
    );

    const zeroBalance =
        verification.filter(
            result =>
                result.balance === 0n
        );

    console.log(
        "\n============================================================"
    );

    if (
        zeroBalance.length === 0
    ) {

        console.log(
            "SETUP COMPLETED SUCCESSFULLY"
        );

        console.log(
            `${accounts.length}/${accounts.length} accounts funded.`
        );

    } else {

        console.log(
            "SETUP COMPLETED WITH WARNING"
        );

        console.log(
            `${zeroBalance.length} account(s) have zero balance.`
        );
    }

    console.log(
        `Accounts file : ${ACCOUNTS_FILE}`
    );

    console.log(
        `Report        : ${SETUP_REPORT_FILE}`
    );

    console.log(
        "============================================================"
    );
}

// ============================================================
// START
// ============================================================

main()

    .then(
        () => {

            process.exit(
                0
            );
        }
    )

    .catch(
        error => {

            console.error(
                "\nFatal setup error:"
            );

            console.error(
                getErrorMessage(
                    error
                )
            );

            process.exit(
                1
            );
        }
    );