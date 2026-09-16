import { ethers } from "hardhat";

import fs from "fs";
import path from "path";
import solc from "solc";


// ============================================================
// Configuration
// ============================================================

const ROOT = path.resolve("etherscan_contracts");

const MANIFEST_FILE =
    path.join(ROOT, "manifest.json");

const OLD_RESULTS_FILE =
    path.join(ROOT, "deployment_results.json");

const FINAL_RESULTS_FILE =
    path.join(ROOT, "deployment_all20_results.json");

const ADDRESS_MAPPING_FILE =
    path.join(ROOT, "address_mapping.json");

// const ETHERSCAN_API_KEY =
//     process.env.ETHERSCAN_API_KEY || "";
const ETHERSCAN_API_KEY = "96T7J8YK2715HRUUB2XMCRXEJ14H1Z8WVD";

const ETHERSCAN_API =
    "https://api.etherscan.io/v2/api";

const ETHEREUM_CHAIN_ID = "1";


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


interface Result {
    originalAddress: string;

    contractName: string;

    localAddress?: string;

    implementationOriginal?: string;

    implementationLocal?: string;

    status:
        | "REUSED_EXISTING"
        | "NORMAL_DEPLOYMENT"
        | "PROXY_DEPLOYMENT"
        | "IMPLEMENTATION_DEPLOYMENT"
        | "RUNTIME_FALLBACK"
        | "FAILED";

    txHash?: string;

    error?: string;
}


// ============================================================
// Global data
// ============================================================

const manifest =
    JSON.parse(
        fs.readFileSync(
            MANIFEST_FILE,
            "utf8"
        )
    );


const mapping:
    Record<string, string> = {};


const finalResults:
    Result[] = [];


// Prevent recursive deployment loops
const deploying =
    new Set<string>();


// ============================================================
// Utility
// ============================================================

function normalizeAddress(
    address: string
): string {

    return address.toLowerCase();
}


function strip0x(
    value: string
): string {

    if (
        value.startsWith("0x")
    ) {

        return value.substring(2);
    }

    return value;
}


function saveProgress() {

    fs.writeFileSync(
        FINAL_RESULTS_FILE,

        JSON.stringify(
            finalResults,
            null,
            2
        )
    );

    fs.writeFileSync(
        ADDRESS_MAPPING_FILE,

        JSON.stringify(
            mapping,
            null,
            2
        )
    );
}


// ============================================================
// Load previous successful deployments
// ============================================================

function loadExistingDeployments() {

    if (
        !fs.existsSync(
            OLD_RESULTS_FILE
        )
    ) {

        console.log(
            "No previous deployment_results.json found."
        );

        return;
    }

    const oldResults =
        JSON.parse(
            fs.readFileSync(
                OLD_RESULTS_FILE,
                "utf8"
            )
        );

    for (
        const result
        of oldResults
    ) {

        if (
            result.status === "SUCCESS"
            &&
            result.localAddress
        ) {

            const original =
                normalizeAddress(
                    result.originalAddress
                );

            mapping[
                original
            ] =
                result.localAddress;

            finalResults.push({
                originalAddress:
                    original,

                contractName:
                    result.contractName,

                localAddress:
                    result.localAddress,

                status:
                    "REUSED_EXISTING",

                txHash:
                    result.txHash,
            });
        }
    }
}


// ============================================================
// Load compiler
// ============================================================

function loadCompiler(
    version: string
): Promise<any> {

    return new Promise(
        (
            resolve,
            reject
        ) => {

            console.log(
                `Loading compiler ${version}`
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

                    resolve(
                        compiler
                    );
                }
            );
        }
    );
}


// ============================================================
// Compile one Etherscan contract
// ============================================================

async function compileContract(
    info: ContractInfo
): Promise<string> {

    const address =
        normalizeAddress(
            info.address
        );

    const inputFile =
        path.join(
            ROOT,
            address,
            "compiler_input.json"
        );

    if (
        !fs.existsSync(
            inputFile
        )
    ) {

        throw new Error(
            `compiler_input.json missing for ${address}`
        );
    }

    if (
        !info.compilerVersion
    ) {

        throw new Error(
            `Compiler version missing for ${address}`
        );
    }

    const input =
        JSON.parse(
            fs.readFileSync(
                inputFile,
                "utf8"
            )
        );

    const compiler =
        await loadCompiler(
            info.compilerVersion
        );

    console.log(
        `Compiling ${info.contractName}`
    );

    const output =
        JSON.parse(
            compiler.compile(
                JSON.stringify(
                    input
                )
            )
        );


    // ========================================================
    // Print compiler errors
    // ========================================================

    if (
        output.errors
    ) {

        let fatal =
            false;

        for (
            const item
            of output.errors
        ) {

            if (
                item.severity
                ===
                "error"
            ) {

                fatal =
                    true;

                console.error(
                    item.formattedMessage
                );
            }
        }

        if (fatal) {

            throw new Error(
                "Compilation failed"
            );
        }
    }


    // ========================================================
    // Find target contract
    // ========================================================

    for (
        const source
        of Object.keys(
            output.contracts || {}
        )
    ) {

        for (
            const name
            of Object.keys(
                output.contracts[
                    source
                ]
            )
        ) {

            if (
                name !==
                info.contractName
            ) {

                continue;
            }

            let bytecode =
                output.contracts[
                    source
                ][
                    name
                ]?.evm
                    ?.bytecode
                    ?.object || "";

            bytecode =
                strip0x(
                    bytecode
                );

            if (
                !bytecode
            ) {

                throw new Error(
                    `Creation bytecode empty for ${name}`
                );
            }

            if (
                !/^[0-9a-fA-F]+$/.test(
                    bytecode
                )
            ) {

                throw new Error(
                    `Unresolved library references in ${name}`
                );
            }

            return bytecode;
        }
    }

    throw new Error(
        `Could not find contract ${info.contractName}`
    );
}


// ============================================================
// Rewrite ABI encoded addresses
//
// Original:
// 000000000000000000000000c02aaa....
//
// Local:
// 000000000000000000000000422a349....
//
// This is especially important for ERC1967Proxy,
// TransparentUpgradeableProxy, FiatTokenProxy, etc.
// ============================================================

function rewriteConstructorArguments(
    originalArgs: string
): string {

    let args =
        strip0x(
            originalArgs || ""
        ).toLowerCase();

    for (
        const [
            original,
            local
        ]
        of Object.entries(
            mapping
        )
    ) {

        const oldAddress =
            strip0x(
                original
            ).toLowerCase();

        const newAddress =
            strip0x(
                local
            ).toLowerCase();


        // Standard ABI encoded address:
        //
        // 12 bytes zero
        // + 20 byte address

        const oldWord =
            "000000000000000000000000"
            +
            oldAddress;

        const newWord =
            "000000000000000000000000"
            +
            newAddress;


        args =
            args.split(
                oldWord
            ).join(
                newWord
            );
    }

    return args;
}


// ============================================================
// Normal creation-bytecode deployment
// ============================================================

async function deployCreationBytecode(
    info: ContractInfo,
    signer: any
): Promise<{
    address: string;
    txHash: string;
}> {

    const bytecode =
        await compileContract(
            info
        );

    const args =
        rewriteConstructorArguments(
            info.constructorArguments
            ||
            ""
        );

    const data =
        "0x"
        +
        bytecode
        +
        args;


    console.log(
        "Estimating deployment gas..."
    );


    const estimate =
        await signer.estimateGas({
            data:
                data
        });


    console.log(
        `Estimated gas: ${estimate}`
    );


    const gasLimit =
        estimate
        +
        estimate / 4n;


    const tx =
        await signer.sendTransaction({

            data:
                data,

            gasLimit:
                gasLimit,
        });


    console.log(
        `Deployment TX: ${tx.hash}`
    );


    const receipt =
        await tx.wait();


    if (
        !receipt
        ||
        !receipt.contractAddress
    ) {

        throw new Error(
            "No contract address in receipt"
        );
    }


    return {

        address:
            receipt.contractAddress,

        txHash:
            tx.hash,
    };
}


// ============================================================
// Etherscan eth_getCode
// ============================================================

async function getMainnetRuntimeCode(
    address: string
): Promise<string> {

    if (
        !ETHERSCAN_API_KEY
    ) {

        throw new Error(
            "ETHERSCAN_API_KEY not set"
        );
    }


    const params =
        new URLSearchParams({

            chainid:
                ETHEREUM_CHAIN_ID,

            module:
                "proxy",

            action:
                "eth_getCode",

            address:
                address,

            tag:
                "latest",

            apikey:
                ETHERSCAN_API_KEY,
        });


    const url =
        `${ETHERSCAN_API}?${params.toString()}`;


    const response =
        await fetch(
            url
        );


    if (
        !response.ok
    ) {

        throw new Error(
            `Etherscan HTTP ${response.status}`
        );
    }


    const body: any =
        await response.json();


    if (
        !body.result
        ||
        body.result === "0x"
    ) {

        throw new Error(
            `No runtime code returned for ${address}`
        );
    }


    return body.result;
}


// ============================================================
// Build creation code that simply RETURNS runtime bytecode.
//
// This lets us deploy existing Ethereum runtime code without
// executing the original constructor.
//
// WARNING:
// Storage is zero/default. This is NOT a full mainnet-state
// recreation.
// ============================================================

function makeRuntimeDeploymentCode(
    runtimeCode: string
): string {

    const runtime =
        strip0x(
            runtimeCode
        );


    const length =
        runtime.length / 2;


    if (
        length >
        0xffffff
    ) {

        throw new Error(
            "Runtime code too large"
        );
    }


    const sizeHex =
        length
            .toString(16)
            .padStart(
                6,
                "0"
            );


    // Creation program = 18 bytes
    //
    // PUSH3 runtime_size
    // PUSH3 0x000012       <- runtime starts at byte 18
    // PUSH1 0
    // CODECOPY
    // PUSH3 runtime_size
    // PUSH1 0
    // RETURN

    const init =
        "62"
        + sizeHex
        + "62"
        + "000012"
        + "6000"
        + "39"
        + "62"
        + sizeHex
        + "6000"
        + "f3";


    return (
        "0x"
        +
        init
        +
        runtime
    );
}


// ============================================================
// Runtime bytecode fallback
// ============================================================

async function deployRuntimeFallback(
    originalAddress: string,
    signer: any
): Promise<{
    address: string;
    txHash: string;
}> {

    console.log(
        "Fetching runtime bytecode from Ethereum..."
    );


    const runtime =
        await getMainnetRuntimeCode(
            originalAddress
        );


    console.log(
        `Runtime bytecode size: ${
            (runtime.length - 2) / 2
        } bytes`
    );


    const creation =
        makeRuntimeDeploymentCode(
            runtime
        );


    const estimate =
        await signer.estimateGas({

            data:
                creation
        });


    const gasLimit =
        estimate
        +
        estimate / 4n;


    const tx =
        await signer.sendTransaction({

            data:
                creation,

            gasLimit:
                gasLimit,
        });


    console.log(
        `Fallback TX: ${tx.hash}`
    );


    const receipt =
        await tx.wait();


    if (
        !receipt
        ||
        !receipt.contractAddress
    ) {

        throw new Error(
            "Runtime deployment produced no address"
        );
    }


    return {

        address:
            receipt.contractAddress,

        txHash:
            tx.hash,
    };
}


// ============================================================
// Find info in manifest
// ============================================================

function getInfo(
    address: string
): ContractInfo | undefined {

    return manifest.contracts[
        normalizeAddress(
            address
        )
    ];
}


// ============================================================
// Deploy implementation recursively
// ============================================================

async function ensureImplementation(
    address: string,
    signer: any
): Promise<string> {

    const normalized =
        normalizeAddress(
            address
        );


    // Already deployed

    if (
        mapping[
            normalized
        ]
    ) {

        return mapping[
            normalized
        ];
    }


    // Recursive dependency loop protection

    if (
        deploying.has(
            normalized
        )
    ) {

        throw new Error(
            `Recursive deployment loop: ${normalized}`
        );
    }


    deploying.add(
        normalized
    );


    const info =
        getInfo(
            normalized
        );


    if (
        !info
    ) {

        deploying.delete(
            normalized
        );

        throw new Error(
            `Implementation metadata not downloaded: ${normalized}`
        );
    }


    console.log();
    console.log(
        "------------------------------------------------------------"
    );

    console.log(
        `IMPLEMENTATION: ${info.contractName}`
    );

    console.log(
        `Ethereum:       ${normalized}`
    );

    console.log(
        "------------------------------------------------------------"
    );


    // ========================================================
    // If implementation itself points to another implementation,
    // deploy that first.
    // ========================================================

    if (
        info.proxy
        &&
        info.implementation
        &&
        info.implementation.startsWith(
            "0x"
        )
    ) {

        try {

            await ensureImplementation(
                info.implementation,
                signer
            );

        } catch (
            error
        ) {

            console.log(
                `Nested implementation warning: ${error}`
            );
        }
    }


    // ========================================================
    // Try normal deployment first
    // ========================================================

    try {

        const deployed =
            await deployCreationBytecode(
                info,
                signer
            );


        mapping[
            normalized
        ] =
            deployed.address;


        finalResults.push({

            originalAddress:
                normalized,

            contractName:
                info.contractName
                ||
                "UNKNOWN",

            localAddress:
                deployed.address,

            status:
                "IMPLEMENTATION_DEPLOYMENT",

            txHash:
                deployed.txHash,
        });


        console.log(
            `[IMPLEMENTATION SUCCESS] ${normalized}`
        );

        console.log(
            `Local: ${deployed.address}`
        );


        deploying.delete(
            normalized
        );


        saveProgress();


        return deployed.address;

    } catch (
        normalError: any
    ) {

        console.log(
            `Normal implementation deployment failed: ${
                normalError?.shortMessage
                ||
                normalError?.message
                ||
                normalError
            }`
        );
    }


    // ========================================================
    // Runtime fallback
    // ========================================================

    const fallback =
        await deployRuntimeFallback(
            normalized,
            signer
        );


    mapping[
        normalized
    ] =
        fallback.address;


    finalResults.push({

        originalAddress:
            normalized,

        contractName:
            info.contractName
            ||
            "UNKNOWN",

        localAddress:
            fallback.address,

        status:
            "RUNTIME_FALLBACK",

        txHash:
            fallback.txHash,
    });


    console.log(
        `[IMPLEMENTATION FALLBACK] ${normalized}`
    );

    console.log(
        `Local: ${fallback.address}`
    );


    deploying.delete(
        normalized
    );


    saveProgress();


    return fallback.address;
}


// ============================================================
// Deploy one top-level contract
// ============================================================

async function deployTopLevel(
    address: string,
    signer: any
) {

    const normalized =
        normalizeAddress(
            address
        );


    // Already one of the 10 successful contracts

    if (
        mapping[
            normalized
        ]
    ) {

        console.log();
        console.log(
            `[REUSE] ${normalized}`
        );

        console.log(
            `Local: ${mapping[normalized]}`
        );

        return;
    }


    const info =
        getInfo(
            normalized
        );


    if (
        !info
    ) {

        throw new Error(
            `No metadata for ${normalized}`
        );
    }


    console.log();
    console.log(
        "============================================================"
    );

    console.log(
        `TOP LEVEL: ${info.contractName}`
    );

    console.log(
        `Ethereum:  ${normalized}`
    );

    console.log(
        `Proxy:     ${Boolean(info.proxy)}`
    );

    console.log(
        "============================================================"
    );


    let implementationLocal:
        string | undefined;


    // ========================================================
    // Proxy implementation first
    // ========================================================

    if (
        info.proxy
        &&
        info.implementation
        &&
        info.implementation.startsWith(
            "0x"
        )
    ) {

        console.log(
            `Mainnet implementation: ${info.implementation}`
        );


        implementationLocal =
            await ensureImplementation(
                info.implementation,
                signer
            );


        console.log(
            `Local implementation:   ${implementationLocal}`
        );
    }


    // ========================================================
    // Now constructor arguments are rewritten using mapping.
    //
    // This means:
    //
    // mainnet implementation
    //
    //      becomes
    //
    // local implementation
    // ========================================================

    try {

        const deployed =
            await deployCreationBytecode(
                info,
                signer
            );


        mapping[
            normalized
        ] =
            deployed.address;


        finalResults.push({

            originalAddress:
                normalized,

            contractName:
                info.contractName
                ||
                "UNKNOWN",

            localAddress:
                deployed.address,

            implementationOriginal:
                info.implementation,

            implementationLocal:
                implementationLocal,

            status:
                info.proxy
                    ?
                    "PROXY_DEPLOYMENT"
                    :
                    "NORMAL_DEPLOYMENT",

            txHash:
                deployed.txHash,
        });


        console.log();
        console.log(
            `[SUCCESS] ${info.contractName}`
        );

        console.log(
            `Ethereum: ${normalized}`
        );

        console.log(
            `Local:    ${deployed.address}`
        );


        saveProgress();


        return;
    }

    catch (
        normalError: any
    ) {

        console.log();
        console.log(
            `[NORMAL DEPLOYMENT FAILED]`
        );

        console.log(
            normalError?.shortMessage
            ||
            normalError?.message
            ||
            normalError
        );
    }


    // ========================================================
    // Last-resort runtime deployment
    // ========================================================

    try {

        console.log();
        console.log(
            "Trying runtime-bytecode fallback..."
        );


        const fallback =
            await deployRuntimeFallback(
                normalized,
                signer
            );


        mapping[
            normalized
        ] =
            fallback.address;


        finalResults.push({

            originalAddress:
                normalized,

            contractName:
                info.contractName
                ||
                "UNKNOWN",

            localAddress:
                fallback.address,

            implementationOriginal:
                info.implementation,

            implementationLocal:
                implementationLocal,

            status:
                "RUNTIME_FALLBACK",

            txHash:
                fallback.txHash,
        });


        console.log(
            `[RUNTIME FALLBACK SUCCESS] ${info.contractName}`
        );

        console.log(
            `Ethereum: ${normalized}`
        );

        console.log(
            `Local:    ${fallback.address}`
        );


        saveProgress();
    }

    catch (
        fallbackError: any
    ) {

        finalResults.push({

            originalAddress:
                normalized,

            contractName:
                info.contractName
                ||
                "UNKNOWN",

            status:
                "FAILED",

            error:
                fallbackError?.message
                ||
                String(
                    fallbackError
                ),
        });


        console.error(
            `[FINAL FAILURE] ${normalized}`
        );

        console.error(
            fallbackError
        );


        saveProgress();
    }
}


// ============================================================
// Verify contract code on local chain
// ============================================================

async function verifyMappings() {

    console.log();
    console.log(
        "============================================================"
    );

    console.log(
        "VERIFYING ALL TOP-LEVEL CONTRACTS"
    );

    console.log(
        "============================================================"
    );


    let count =
        0;


    for (
        const original
        of manifest.top20
    ) {

        const normalized =
            normalizeAddress(
                original
            );


        const local =
            mapping[
                normalized
            ];


        if (
            !local
        ) {

            console.log(
                `NO MAPPING | ${normalized}`
            );

            continue;
        }


        const code =
            await ethers.provider.getCode(
                local
            );


        const size =
            code === "0x"
                ?
                0
                :
                (code.length - 2) / 2;


        if (
            size > 0
        ) {

            count++;
        }


        console.log(
            `${
                size > 0
                    ?
                    "OK"
                    :
                    "NO CODE"
            } | `
            +
            `${normalized} -> ${local} | `
            +
            `${size} bytes`
        );
    }


    console.log();
    console.log(
        `Contracts with local bytecode: ${count}/20`
    );
}


// ============================================================
// Main
// ============================================================

async function main() {

    if (
        !ETHERSCAN_API_KEY
    ) {

        throw new Error(
            "ETHERSCAN_API_KEY is not exported"
        );
    }


    const [
        signer
    ] =
        await ethers.getSigners();


    const network =
        await ethers.provider.getNetwork();


    const balance =
        await ethers.provider.getBalance(
            signer.address
        );


    console.log(
        "============================================================"
    );

    console.log(
        "DEPLOY ALL TOP 20"
    );

    console.log(
        "============================================================"
    );

    console.log(
        `Deployer: ${signer.address}`
    );

    console.log(
        `Balance:  ${ethers.formatEther(balance)} ETH`
    );

    console.log(
        `Chain ID: ${network.chainId}`
    );


    // ========================================================
    // Reuse your 10 already-successful deployments
    // ========================================================

    loadExistingDeployments();


    console.log(
        `Existing mappings: ${Object.keys(mapping).length}`
    );


    // ========================================================
    // Process all original top 20
    // ========================================================

    for (
        let i = 0;
        i < manifest.top20.length;
        i++
    ) {

        const address =
            manifest.top20[
                i
            ];


        console.log();
        console.log(
            `[${i + 1}/20]`
        );


        await deployTopLevel(
            address,
            signer
        );
    }


    // ========================================================
    // Verify
    // ========================================================

    await verifyMappings();


    saveProgress();


    console.log();
    console.log(
        "============================================================"
    );

    console.log(
        "FINAL ADDRESS MAPPING"
    );

    console.log(
        "============================================================"
    );


    for (
        const original
        of manifest.top20
    ) {

        const normalized =
            normalizeAddress(
                original
            );


        console.log(
            `${normalized} -> ${
                mapping[normalized]
                ||
                "FAILED"
            }`
        );
    }


    console.log();
    console.log(
        `Results: ${FINAL_RESULTS_FILE}`
    );

    console.log(
        `Mapping: ${ADDRESS_MAPPING_FILE}`
    );
}


// ============================================================
// Run
// ============================================================

main()
    .then(
        () =>
            process.exit(0)
    )
    .catch(
        error => {

            console.error(
                error
            );

            process.exit(1);
        }
    );