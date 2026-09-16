#!/usr/bin/env python3

import os
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional


# ============================================================
# Configuration
# ============================================================

# ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY")
ETHERSCAN_API_KEY = "96T7J8YK2715HRUUB2XMCRXEJ14H1Z8WVD"

ETHERSCAN_API = "https://api.etherscan.io/v2/api"

CHAIN_ID = "1"

OUTPUT_DIR = Path("etherscan_contracts")


TOP_20 = [
    "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad",
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "0xd5ceb3e748ef3296a68b930c1810c5884278410e",
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    "0x253553366da8546fc250f225fe3d25d0c782303b",
    "0x32400084c286cf3e17e7b677ea9583e60a000324",
    "0x881d40237659c251811cec9c364ef91dc08d300c",
    "0x29469395eaf6f95920e59f858042f0e28d98a20b",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff",
    "0x00000000000000adc04c56bf30ac9d3c0aaf14dc",
    "0xf951e335afb289353dc249e82926178eac7ded78",
    "0x1111111254eeb25477b68fb85ed929f73a960582",
    "0xdaf1695c41327b61b9b9965ac6a5843a3198cf07",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
    "0x06450dee7fd2fb8e39061434babcfc05599a6fb8",
    "0xc321bf502c03d9e26eabf3afa6574efc4d6fecf0",
    "0xa0425d71cb1d6fb80e65a5361a04096e0672de03",
    "0xb2ecfe4e4d61f8790bbb9de2d1259b9e2410cea5",
    "0x0000000000a39bb272e79075ade125fd351887ac",
]


# ============================================================
# Utility
# ============================================================

def safe_path(name: str) -> Path:
    """
    Convert Solidity source path to a safe local path.
    """
    name = name.replace("\\", "/")

    while name.startswith("../"):
        name = name[3:]

    while name.startswith("./"):
        name = name[2:]

    name = name.lstrip("/")

    return Path(name)


def etherscan_request(address: str) -> Dict[str, Any]:

    params = {
        "chainid": CHAIN_ID,
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "apikey": ETHERSCAN_API_KEY,
    }

    response = requests.get(
        ETHERSCAN_API,
        params=params,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("status") != "1":
        raise RuntimeError(
            f"Etherscan error for {address}: "
            f"{data.get('message')} - {data.get('result')}"
        )

    result = data.get("result")

    if not isinstance(result, list) or len(result) == 0:
        raise RuntimeError(
            f"No contract information returned for {address}"
        )

    return result[0]


# ============================================================
# Parse Etherscan source
# ============================================================

def parse_source_code(
    raw_source: str,
    contract_name: str,
) -> Dict[str, Any]:

    raw_source = raw_source.strip()

    if not raw_source:
        return {
            "type": "unverified",
            "sources": {},
            "settings": {},
        }

    # --------------------------------------------------------
    # Etherscan sometimes wraps Standard JSON with:
    #
    # {{
    #   ...
    # }}
    #
    # instead of:
    #
    # {
    #   ...
    # }
    # --------------------------------------------------------

    candidate = raw_source

    if candidate.startswith("{{") and candidate.endswith("}}"):
        candidate = candidate[1:-1]

    # --------------------------------------------------------
    # Try JSON format
    # --------------------------------------------------------

    try:
        obj = json.loads(candidate)

        # Solidity Standard JSON
        if isinstance(obj, dict) and "sources" in obj:

            sources = obj["sources"]

            settings = obj.get("settings", {})

            language = obj.get("language", "Solidity")

            return {
                "type": "standard-json",
                "language": language,
                "sources": sources,
                "settings": settings,
            }

        # Sometimes SourceCode is only:
        #
        # {
        #   "contracts/A.sol": {
        #       "content": "..."
        #   }
        # }
        #
        if isinstance(obj, dict):

            looks_like_sources = True

            for _, value in obj.items():
                if not isinstance(value, dict):
                    looks_like_sources = False
                    break

                if "content" not in value:
                    looks_like_sources = False
                    break

            if looks_like_sources:

                return {
                    "type": "multi-file",
                    "language": "Solidity",
                    "sources": obj,
                    "settings": {},
                }

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Single flattened Solidity source file
    # --------------------------------------------------------

    filename = f"{contract_name}.sol"

    return {
        "type": "single-file",
        "language": "Solidity",
        "sources": {
            filename: {
                "content": raw_source
            }
        },
        "settings": {},
    }


# ============================================================
# Save source files
# ============================================================

def save_sources(
    contract_dir: Path,
    parsed: Dict[str, Any],
):

    sources = parsed.get("sources", {})

    source_root = contract_dir / "sources"

    source_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    for source_name, source_info in sources.items():

        content = ""

        if isinstance(source_info, dict):
            content = source_info.get("content", "")
        elif isinstance(source_info, str):
            content = source_info

        local_path = source_root / safe_path(source_name)

        local_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            local_path,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(content)


# ============================================================
# Build compiler input
# ============================================================

def build_compiler_input(
    parsed: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:

    settings = parsed.get("settings") or {}

    # Make a deep copy
    settings = json.loads(json.dumps(settings))

    # --------------------------------------------------------
    # If standard JSON did not contain optimizer information,
    # reconstruct it from Etherscan metadata.
    # --------------------------------------------------------

    if "optimizer" not in settings:

        optimizer_enabled = (
            str(metadata.get("OptimizationUsed", "0")) == "1"
        )

        runs_string = str(
            metadata.get("Runs", "200")
        )

        try:
            runs = int(runs_string)
        except Exception:
            runs = 200

        settings["optimizer"] = {
            "enabled": optimizer_enabled,
            "runs": runs,
        }

    # --------------------------------------------------------
    # EVM version
    # --------------------------------------------------------

    evm_version = str(
        metadata.get("EVMVersion", "")
    ).strip()

    if (
        evm_version
        and evm_version.lower() != "default"
    ):
        settings["evmVersion"] = evm_version

    # --------------------------------------------------------
    # We need creation bytecode for deployment.
    # --------------------------------------------------------

    settings["outputSelection"] = {
        "*": {
            "*": [
                "abi",
                "evm.bytecode",
                "evm.deployedBytecode",
                "metadata",
            ]
        }
    }

    return {
        "language": parsed.get(
            "language",
            "Solidity"
        ),
        "sources": parsed.get(
            "sources",
            {}
        ),
        "settings": settings,
    }


# ============================================================
# Download one contract
# ============================================================

downloaded = {}


def download_contract(
    address: str,
    relation: str = "top20",
) -> Optional[Dict[str, Any]]:

    address = address.lower()

    if address in downloaded:
        return downloaded[address]

    print()
    print("=" * 80)
    print(f"Downloading: {address}")
    print(f"Relation:    {relation}")
    print("=" * 80)

    contract_dir = OUTPUT_DIR / address

    contract_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        metadata = etherscan_request(address)

    except Exception as exc:

        print(f"[ERROR] {exc}")

        error_info = {
            "address": address,
            "status": "API_ERROR",
            "error": str(exc),
        }

        with open(
            contract_dir / "error.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                error_info,
                f,
                indent=2,
            )

        downloaded[address] = error_info

        return error_info

    source_code = metadata.get(
        "SourceCode",
        ""
    )

    contract_name = metadata.get(
        "ContractName",
        ""
    )

    compiler_version = metadata.get(
        "CompilerVersion",
        ""
    )

    proxy = str(
        metadata.get("Proxy", "0")
    )

    implementation = str(
        metadata.get("Implementation", "")
    ).strip()

    print(
        f"Contract name:    {contract_name}"
    )

    print(
        f"Compiler:         {compiler_version}"
    )

    print(
        f"Proxy:            {proxy}"
    )

    if implementation:
        print(
            f"Implementation:   {implementation}"
        )

    # --------------------------------------------------------
    # Save complete original Etherscan response
    # --------------------------------------------------------

    with open(
        contract_dir / "etherscan_metadata.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            metadata,
            f,
            indent=2,
        )

    # --------------------------------------------------------
    # Save ABI
    # --------------------------------------------------------

    abi_raw = metadata.get(
        "ABI",
        ""
    )

    if abi_raw:

        try:

            abi = json.loads(abi_raw)

            with open(
                contract_dir / "abi.json",
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    abi,
                    f,
                    indent=2,
                )

        except Exception:

            with open(
                contract_dir / "abi.txt",
                "w",
                encoding="utf-8",
            ) as f:
                f.write(abi_raw)

    # --------------------------------------------------------
    # Unverified
    # --------------------------------------------------------

    if not source_code.strip():

        print("[SKIP] Source code is not verified.")

        info = {
            "address": address,
            "contractName": contract_name,
            "compilerVersion": compiler_version,
            "verified": False,
            "proxy": proxy == "1",
            "implementation": implementation,
            "relation": relation,
        }

        with open(
            contract_dir / "contract.json",
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                info,
                f,
                indent=2,
            )

        downloaded[address] = info

        return info

    # --------------------------------------------------------
    # Parse complete source tree
    # --------------------------------------------------------

    parsed = parse_source_code(
        source_code,
        contract_name or "Contract",
    )

    save_sources(
        contract_dir,
        parsed,
    )

    # --------------------------------------------------------
    # Compiler input
    # --------------------------------------------------------

    compiler_input = build_compiler_input(
        parsed,
        metadata,
    )

    with open(
        contract_dir / "compiler_input.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            compiler_input,
            f,
            indent=2,
        )

    # --------------------------------------------------------
    # Our normalized metadata
    # --------------------------------------------------------

    info = {
        "address": address,
        "contractName": contract_name,
        "contractFileName": metadata.get(
            "ContractFileName",
            ""
        ),
        "compilerVersion": compiler_version,
        "compilerType": metadata.get(
            "CompilerType",
            ""
        ),
        "optimizationUsed": metadata.get(
            "OptimizationUsed",
            ""
        ),
        "runs": metadata.get(
            "Runs",
            ""
        ),
        "constructorArguments": metadata.get(
            "ConstructorArguments",
            ""
        ),
        "evmVersion": metadata.get(
            "EVMVersion",
            ""
        ),
        "library": metadata.get(
            "Library",
            ""
        ),
        "proxy": proxy == "1",
        "implementation": implementation,
        "licenseType": metadata.get(
            "LicenseType",
            ""
        ),
        "verified": True,
        "sourceFormat": parsed.get(
            "type"
        ),
        "relation": relation,
    }

    with open(
        contract_dir / "contract.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            info,
            f,
            indent=2,
        )

    downloaded[address] = info

    print(
        f"[OK] Saved to: {contract_dir}"
    )

    # --------------------------------------------------------
    # If this is a proxy, also download implementation source
    # --------------------------------------------------------

    if (
        proxy == "1"
        and implementation
        and implementation.startswith("0x")
        and len(implementation) == 42
    ):

        print()
        print(
            f"[PROXY] Downloading implementation "
            f"{implementation}"
        )

        time.sleep(0.45)

        download_contract(
            implementation,
            relation=f"implementation-of:{address}",
        )

    return info


# ============================================================
# Main
# ============================================================

def main():

    if not ETHERSCAN_API_KEY:

        raise SystemExit(
            "\nERROR: ETHERSCAN_API_KEY is not set.\n\n"
            "Run:\n"
            'export ETHERSCAN_API_KEY="YOUR_API_KEY"\n'
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    for index, address in enumerate(
        TOP_20,
        start=1,
    ):

        print()
        print(
            f"[{index}/{len(TOP_20)}]"
        )

        result = download_contract(
            address,
            relation="top20",
        )

        results.append(result)

        # Be friendly to Etherscan rate limits
        time.sleep(0.45)

    # --------------------------------------------------------
    # Save complete manifest
    # --------------------------------------------------------

    manifest = {
        "chainId": CHAIN_ID,
        "top20": TOP_20,
        "contracts": downloaded,
    }

    with open(
        OUTPUT_DIR / "manifest.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2,
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    verified = 0
    unverified = 0
    proxies = 0

    for _, info in downloaded.items():

        if info.get("verified"):
            verified += 1
        else:
            unverified += 1

        if info.get("proxy"):
            proxies += 1

    print()
    print("=" * 80)
    print("DOWNLOAD COMPLETE")
    print("=" * 80)

    print(
        f"Top-level addresses: {len(TOP_20)}"
    )

    print(
        f"Total addresses downloaded "
        f"(including implementations): "
        f"{len(downloaded)}"
    )

    print(
        f"Verified:   {verified}"
    )

    print(
        f"Unverified: {unverified}"
    )

    print(
        f"Proxies:    {proxies}"
    )

    print()
    print(
        f"Output directory: {OUTPUT_DIR.resolve()}"
    )


if __name__ == "__main__":
    main()