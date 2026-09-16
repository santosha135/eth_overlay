import { ethers } from "hardhat";

import fs from "fs";
import path from "path";
import solc from "solc";


// ============================================================
// Configuration
// ============================================================

const ROOT =
    path.resolve("etherscan_contracts");

const MANIFEST_FILE =
    path.join(ROOT, "manifest.json");

const OUTPUT_FILE =
    path.join(ROOT, "deployment_results.json");


// ============================================================
// Types
// ============================================================

interface ContractInfo {
    address: string;
    contractName?: string;
    compilerVersion?: string;
    constructorArguments?: string;
    verified?: boolean;
    proxy?: boolean;
    implementation?: string;
    relation?: string;
}

interface DeploymentResult {
    originalAddress: string;
    contractName: string;
    compilerVersion: string;

    localAddress?: string;

    proxy: boolean;

    implementation?: string;

    status:
        | "SUCCESS"
        | "FAILED"
        | "SKIPPED_UNVERIFIED"
        | "SKIPPED_PROXY"
        | "SKIPPED_NO_BYTECODE"
        | "SKIPPED_LIBRARY_LINKING";

    txHash?: string;

    error?: string;
}


// ============================================================
// Load compiler
// ============================================================

function loadCompiler(
    version: string
): Promise<any> {

    return new Promise(
        (resolve, reject) => {

            console.log(
                `Loading Solidity compiler ${version} ...`
            );

            solc.loadRemoteVersion(
                version,
                (
                    error: Error | null,
                    compiler: any
                ) => {

                    if (error) {
                        reject(error);
                        return;
                    }

                    resolve(compiler);
                }
            );
        }
    );
}


// ============================================================
// Compile
// ============================================================

async function compileContract(
    info: ContractInfo
): Promise<{
    abi: any[];
    bytecode: string;
}> {

    const contractDirectory =
        path.join(
            ROOT,
            info.address.toLowerCase()
        );

    const compilerInputFile =
        path.join(
            contractDirectory,
            "compiler_input.json"
        );

    if (
        !fs.existsSync(
            compilerInputFile
        )
    ) {

        throw new Error(
            `compiler_input.json not found`
        );
    }

    const compilerInput =
        JSON.parse(
            fs.readFileSync(
                compilerInputFile,
                "utf8"
            )
        );

    if (
        !info.compilerVersion
    ) {

        throw new Error(
            "Compiler version is empty"
        );
    }

    const compiler =
        await loadCompiler(
            info.compilerVersion
        );

    console.log(
        `Compiling ${info.contractName} ...`
    );

    const outputRaw =
        compiler.compile(
            JSON.stringify(
                compilerInput
            )
        );

    const output =
        JSON.parse(
            outputRaw
        );

    // ========================================================
    // Compiler diagnostics
    // ========================================================

    if (output.errors) {

        let fatal = false;

        for (
            const error of output.errors
        ) {

            if (
                error.severity === "error"
            ) {

                fatal = true;

                console.error(
                    `[SOLC ERROR] ${error.formattedMessage}`
                );

            } else {

                console.log(
                    `[SOLC WARNING] ${error.formattedMessage}`
                );
            }
        }

        if (fatal) {

            throw new Error(
                "Solidity compilation failed"
            );
        }
    }

    // ========================================================
    // Find contract
    // ========================================================

    const targetName =
        info.contractName || "";

    let found:
        | {
            abi: any[];
            bytecode: string;
        }
        | undefined;

    for (
        const sourceName
        of Object.keys(
            output.contracts || {}
        )
    ) {

        const sourceContracts =
            output.contracts[
                sourceName
            ];

        for (
            const compiledName
            of Object.keys(
                sourceContracts
            )
        ) {

            if (
                compiledName !== targetName
            ) {
                continue;
            }

            const compiled =
                sourceContracts[
                    compiledName
                ];

            const bytecode =
                compiled?.evm
                    ?.bytecode
                    ?.object || "";

            found = {
                abi:
                    compiled.abi || [],
                bytecode:
                    bytecode,
            };

            console.log(
                `Found ${compiledName} in ${sourceName}`
            );

            break;
        }

        if (found) {
            break;
        }
    }

    if (!found) {

        throw new Error(
            `Could not find compiled contract '${targetName}'`
        );
    }

    return found;
}


// ============================================================
// Check bytecode
// ============================================================

function isPureHex(
    value: string
): boolean {

    return /^[0-9a-fA-F]*$/.test(
        value
    );
}


// ============================================================
// Deploy one
// ============================================================

async function deployOne(
    info: ContractInfo,
    signer: any
): Promise<DeploymentResult> {

    const name =
        info.contractName || "UNKNOWN";

    console.log();
    console.log(
        "=".repeat(80)
    );

    console.log(
        `Contract: ${name}`
    );

    console.log(
        `Ethereum: ${info.address}`
    );

    console.log(
        `Compiler: ${info.compilerVersion}`
    );

    console.log(
        `Proxy:    ${info.proxy}`
    );

    console.log(
        "=".repeat(80)
    );

    // ========================================================
    // Unverified contract
    // ========================================================

    if (!info.verified) {

        console.log(
            "[SKIP] Contract is not verified."
        );

        return {
            originalAddress:
                info.address,

            contractName:
                name,

            compilerVersion:
                info.compilerVersion || "",

            proxy:
                Boolean(info.proxy),

            implementation:
                info.implementation,

            status:
                "SKIPPED_UNVERIFIED",
        };
    }

    // ========================================================
    // Proxy
    //
    // IMPORTANT:
    //
    // An Ethereum proxy's constructor arguments normally
    // contain the ORIGINAL Ethereum implementation address.
    //
    // Automatically deploying it unchanged would produce a
    // proxy pointing back to the Ethereum address, where there
    // is no implementation code on your private chain.
    //
    // We therefore skip proxies in this first pass.
    // ========================================================

    if (info.proxy) {

        console.log(
            "[SKIP] Proxy contract."
        );

        console.log(
            `Implementation: ${info.implementation}`
        );

        return {
            originalAddress:
                info.address,

            contractName:
                name,

            compilerVersion:
                info.compilerVersion || "",

            proxy: true,

            implementation:
                info.implementation,

            status:
                "SKIPPED_PROXY",
        };
    }

    try {

        const compiled =
            await compileContract(
                info
            );

        let bytecode =
            compiled.bytecode;

        if (
            !bytecode
            || bytecode === "0x"
        ) {

            console.log(
                "[SKIP] No creation bytecode."
            );

            return {
                originalAddress:
                    info.address,

                contractName:
                    name,

                compilerVersion:
                    info.compilerVersion || "",

                proxy:
                    false,

                status:
                    "SKIPPED_NO_BYTECODE",
            };
        }

        if (
            bytecode.startsWith("0x")
        ) {

            bytecode =
                bytecode.substring(2);
        }

        // ====================================================
        // Linked library placeholders
        // ====================================================

        if (
            !isPureHex(bytecode)
        ) {

            console.log(
                "[SKIP] Bytecode contains unresolved library references."
            );

            return {
                originalAddress:
                    info.address,

                contractName:
                    name,

                compilerVersion:
                    info.compilerVersion || "",

                proxy:
                    false,

                status:
                    "SKIPPED_LIBRARY_LINKING",
            };
        }

        // ====================================================
        // Constructor arguments from Etherscan
        //
        // They are already ABI encoded.
        //
        // Therefore:
        //
        // deploy data =
        //
        // creation bytecode
        //        +
        // constructor arguments
        //
        // ====================================================

        let constructorArgs =
            info.constructorArguments || "";

        if (
            constructorArgs.startsWith(
                "0x"
            )
        ) {

            constructorArgs =
                constructorArgs.substring(
                    2
                );
        }

        const deployData =
            "0x"
            + bytecode
            + constructorArgs;

        console.log(
            "Sending deployment transaction..."
        );

        // ====================================================
        // Estimate gas
        // ====================================================

        let estimatedGas;

        try {

            estimatedGas =
                await signer.estimateGas({
                    data: deployData
                });

            console.log(
                `Estimated gas: ${estimatedGas.toString()}`
            );

        } catch (
            estimateError: any
        ) {

            throw new Error(
                "Gas estimation / constructor execution failed: "
                + (
                    estimateError?.shortMessage
                    || estimateError?.message
                    || String(
                        estimateError
                    )
                )
            );
        }

        // Add 20% headroom
        const gasLimit =
            estimatedGas
            + estimatedGas / 5n;

        const tx =
            await signer.sendTransaction({
                data:
                    deployData,

                gasLimit:
                    gasLimit,
            });

        console.log(
            `TX: ${tx.hash}`
        );

        const receipt =
            await tx.wait();

        if (!receipt) {

            throw new Error(
                "No transaction receipt"
            );
        }

        const localAddress =
            receipt.contractAddress;

        if (!localAddress) {

            throw new Error(
                "Receipt contains no contract address"
            );
        }

        console.log(
            `[SUCCESS] ${name}`
        );

        console.log(
            `Ethereum address: ${info.address}`
        );

        console.log(
            `Local address:    ${localAddress}`
        );

        return {
            originalAddress:
                info.address,

            contractName:
                name,

            compilerVersion:
                info.compilerVersion || "",

            localAddress:
                localAddress,

            proxy:
                false,

            status:
                "SUCCESS",

            txHash:
                tx.hash,
        };

    } catch (error: any) {

        const message =
            error?.shortMessage
            || error?.message
            || String(error);

        console.error(
            `[FAILED] ${name}: ${message}`
        );

        return {
            originalAddress:
                info.address,

            contractName:
                name,

            compilerVersion:
                info.compilerVersion || "",

            proxy:
                Boolean(
                    info.proxy
                ),

            implementation:
                info.implementation,

            status:
                "FAILED",

            error:
                message,
        };
    }
}


// ============================================================
// Main
// ============================================================

async function main() {

    if (
        !fs.existsSync(
            MANIFEST_FILE
        )
    ) {

        throw new Error(
            `Manifest not found: ${MANIFEST_FILE}`
        );
    }

    const manifest =
        JSON.parse(
            fs.readFileSync(
                MANIFEST_FILE,
                "utf8"
            )
        );

    const [
        signer
    ] =
        await ethers.getSigners();

    console.log();
    console.log(
        "=".repeat(80)
    );

    console.log(
        "DEPLOYER"
    );

    console.log(
        "=".repeat(80)
    );

    console.log(
        `Address: ${signer.address}`
    );

    const balance =
        await ethers.provider
            .getBalance(
                signer.address
            );

    console.log(
        `Balance: ${ethers.formatEther(balance)} ETH`
    );

    const network =
        await ethers.provider
            .getNetwork();

    console.log(
        `Chain ID: ${network.chainId.toString()}`
    );

    const results:
        DeploymentResult[] = [];

    // ========================================================
    // Only deploy the original TOP 20 here.
    //
    // Implementation contracts downloaded recursively are
    // available, but handled separately for proxy reconstruction.
    // ========================================================

    for (
        const address
        of manifest.top20
    ) {

        const normalized =
            address.toLowerCase();

        const info:
            ContractInfo =
            manifest.contracts[
                normalized
            ];

        if (!info) {

            console.error(
                `No metadata for ${address}`
            );

            continue;
        }

        const result =
            await deployOne(
                info,
                signer
            );

        results.push(
            result
        );

        // Save after every contract so progress
        // survives a later failure.

        fs.writeFileSync(
            OUTPUT_FILE,
            JSON.stringify(
                results,
                null,
                2
            )
        );
    }

    // ========================================================
    // Summary
    // ========================================================

    console.log();
    console.log(
        "=".repeat(80)
    );

    console.log(
        "DEPLOYMENT SUMMARY"
    );

    console.log(
        "=".repeat(80)
    );

    let success = 0;
    let failed = 0;
    let skipped = 0;

    for (
        const result
        of results
    ) {

        if (
            result.status
            === "SUCCESS"
        ) {

            success++;

        } else if (
            result.status
            === "FAILED"
        ) {

            failed++;

        } else {

            skipped++;
        }

        console.log(
            `${result.originalAddress} | `
            + `${result.contractName} | `
            + `${result.status} | `
            + `${result.localAddress || "-"}`
        );
    }

    console.log();
    console.log(
        `Success: ${success}`
    );

    console.log(
        `Failed:  ${failed}`
    );

    console.log(
        `Skipped: ${skipped}`
    );

    console.log();
    console.log(
        `Results saved to: ${OUTPUT_FILE}`
    );
}


// ============================================================
// Run
// ============================================================

main()
    .then(() => {
        process.exit(0);
    })
    .catch((error) => {

        console.error(error);

        process.exit(1);
    });