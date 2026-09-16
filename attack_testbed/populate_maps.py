#!/usr/bin/env python3

from pathlib import Path
import re

# ============================================================
# PASTE YOUR FINAL ADDRESS MAPPING HERE EXACTLY AS RECEIVED
# ============================================================

FINAL_ADDRESS_MAPPING = """
0xdac17f958d2ee523a2206206994597c13d831ec7 -> 0xb4B46bdAA835F8E4b4d8e208B6559cD267851051
0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad -> 0x17435ccE3d1B4fA2e5f8A08eD921D57C6762A180
0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48 -> 0x0643D39D47CF0ea95Dbea69Bf11a7F8C4Bc34968
0xd5ceb3e748ef3296a68b930c1810c5884278410e -> 0x9f9F5Fd89ad648f2C000C954d8d9C87743243eC5
0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2 -> 0x8F0342A7060e76dfc7F6e9dEbfAD9b9eC919952c
0x253553366da8546fc250f225fe3d25d0c782303b -> 0x72ae2643518179cF01bcA3278a37ceAD408DE8b2
0x32400084c286cf3e17e7b677ea9583e60a000324 -> 0x9fCF7D13d10dEdF17d0f24C62f0cf4ED462f65b7
0x881d40237659c251811cec9c364ef91dc08d300c -> 0x63e6DDE6763C3466C7b45Be880f7eE5dC2ca3E25
0x29469395eaf6f95920e59f858042f0e28d98a20b -> 0x373E0B8B80A15cdf587C1263654c6B5edd195a43
0xdef1c0ded9bec7f1a1670819833240f027b25eff -> 0xEE0fCB8E5cCAD0b4197BAabd633333886f5C364d
0x00000000000000adc04c56bf30ac9d3c0aaf14dc -> 0x1ADB9959EB142bE128E6dfEcc8D571f07cd66DeE
0xf951e335afb289353dc249e82926178eac7ded78 -> 0xB965D10739e19a9158e7f713720B0145D996E370
0x1111111254eeb25477b68fb85ed929f73a960582 -> 0x3A8C1bd531b5C1aeFBB9ebc3e021C1251cF4Ccb1
0xdaf1695c41327b61b9b9965ac6a5843a3198cf07 -> 0x38435Ac0E0e9Bd8737c476F8F39a24b0735e00dc
0x7a250d5630b4cf539739df2c5dacb4c659f2488d -> 0x1430c9c2143F97aaE765197e744BaBa7e78acaf0
0x06450dee7fd2fb8e39061434babcfc05599a6fb8 -> 0xE19dddcaF5dCb2Ec0Fe52229e3133B99396f22e2
0xc321bf502c03d9e26eabf3afa6574efc4d6fecf0 -> 0x2A3365C575a5Fc8fD2842B82D29f8035E7f71CeC
0xa0425d71cb1d6fb80e65a5361a04096e0672de03 -> 0x9ECB6f04D47FA2599449AaA523bF84476f7aD80f
0xb2ecfe4e4d61f8790bbb9de2d1259b9e2410cea5 -> 0x2b45cD38B213Bbd3A1A848bf2467927c976877Cb
0x0000000000a39bb272e79075ade125fd351887ac -> 0xC5FC7cE1d859E6604f1e8E57BA0f4A92858850Bc
"""

# ============================================================
# SETTINGS
# ============================================================

# You said you want ONLY 10 successful mappings.
MAX_SUCCESSFUL_MAPPINGS = 5

# ============================================================
# ONLY CONTRACTS THAT HAD >= 1 SUCCESSFUL CALL
# ============================================================

SUCCESSFUL_CONTRACT_ADDRESSES = {
    # USDT
    "0xdac17f958d2ee523a2206206994597c13d831ec7",

    # UniversalRouter
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad",

    # USDC
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",

    # WETH
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",

    # Blend / ERC1967
    "0x29469395eaf6f95920e59f858042f0e28d98a20b",
}

# ============================================================
# PARSE THE PASTED TEXT
# ============================================================

def parse_mapping(text):
    results = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        if "->" not in line:
            continue

        source, destination = line.split("->", 1)

        source = source.strip().lower()
        destination = destination.strip()

        # Skip contracts that did not have any successful call
        if source not in SUCCESSFUL_CONTRACT_ADDRESSES:
            print(f"SKIP NO SUCCESS CALL: {source}")
            continue

        # Ignore FAILED
        if destination.upper() == "FAILED":
            print(f"SKIP FAILED: {source}")
            continue

        # Basic Ethereum address validation
        if not re.fullmatch(r"0x[a-fA-F0-9]{40}", source):
            print(f"WARNING: Invalid source address: {source}")
            continue

        if not re.fullmatch(r"0x[a-fA-F0-9]{40}", destination):
            print(f"WARNING: Invalid destination address: {destination}")
            continue

        results.append((source, destination))

        # if len(results) >= MAX_SUCCESSFUL_MAPPINGS:
        #     break

    return results


# ============================================================
# CREATE PYTHON CONTRACT_ADDRESS_MAP
# ============================================================

def create_map_block(mappings):

    lines = []

    lines.append("# ============================================================")
    lines.append("# FIVE CONTRACTS WITH >= 1 SUCCESSFUL CALL")
    lines.append("# ============================================================")
    lines.append("")
    lines.append("CONTRACT_ADDRESS_MAP = {")

    for i, (source, destination) in enumerate(mappings):

        comma = "," if i < len(mappings) - 1 else ""

        lines.append(f'    "{source}":')
        lines.append(f'        "{destination}"{comma}')
        lines.append("")

    lines.append("}")
    lines.append("")
    lines.append("CONTRACT_ADDRESS_MAP = {")
    lines.append("    k.lower(): Web3.to_checksum_address(v)")
    lines.append("    for k, v in CONTRACT_ADDRESS_MAP.items()")
    lines.append("}")

    return "\n".join(lines)


# ============================================================
# REPLACE EXISTING MAP
# ============================================================

def replace_map(text, new_block):

    # Find first CONTRACT_ADDRESS_MAP
    start_match = re.search(
        r"CONTRACT_ADDRESS_MAP\s*=\s*\{",
        text
    )

    if not start_match:
        raise RuntimeError(
            "CONTRACT_ADDRESS_MAP not found"
        )

    start = start_match.start()

    # Find the end of the first dictionary
    brace_start = text.find("{", start)

    depth = 0
    first_end = None

    for i in range(brace_start, len(text)):

        if text[i] == "{":
            depth += 1

        elif text[i] == "}":
            depth -= 1

            if depth == 0:
                first_end = i + 1
                break

    if first_end is None:
        raise RuntimeError(
            "Could not find end of CONTRACT_ADDRESS_MAP"
        )

    # Find checksum map after first map
    second_match = re.search(
        r"CONTRACT_ADDRESS_MAP\s*=\s*\{",
        text[first_end:]
    )

    if second_match:

        second_start = first_end + second_match.start()

        brace_start2 = text.find("{", second_start)

        depth = 0
        second_end = None

        for i in range(brace_start2, len(text)):

            if text[i] == "{":
                depth += 1

            elif text[i] == "}":
                depth -= 1

                if depth == 0:
                    second_end = i + 1
                    break

        if second_end is None:
            raise RuntimeError(
                "Could not find end of checksum map"
            )

        end = second_end

    else:
        end = first_end

    return (
        text[:start]
        + new_block
        + text[end:]
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("PARSING FINAL ADDRESS MAPPING")
    print("=" * 70)

    mappings = parse_mapping(FINAL_ADDRESS_MAPPING)

    print()
    print(f"Successful mappings found: {len(mappings)}")
    # print(f"Mappings requested:         {MAX_SUCCESSFUL_MAPPINGS}")
    print(
        f"Successful-call contracts requested: "
        f"{len(SUCCESSFUL_CONTRACT_ADDRESSES)}"
    )
    print()

    # if len(mappings) < MAX_SUCCESSFUL_MAPPINGS:
    #     raise RuntimeError(
    #         f"Only {len(mappings)} successful mappings found."
    #     )

    if len(mappings) != len(
    SUCCESSFUL_CONTRACT_ADDRESSES
    ):
        raise RuntimeError(
            f"Expected "
            f"{len(SUCCESSFUL_CONTRACT_ADDRESSES)} "
            f"successful contract mappings, "
            f"found {len(mappings)}"
        )

    # Show exactly what will be used
    print("Mappings that will be installed:")
    print()

    for i, (source, destination) in enumerate(mappings, 1):
        print(f"{i:2d}. {source} -> {destination}")

    print()

    new_block = create_map_block(mappings)

    # ========================================================
    # FIND ALL 10 REPLAY SCRIPTS
    # ========================================================

    files = sorted(
        Path(".").glob("replay_tx_v*_sm.py"),
        key=lambda p: int(
            re.search(r"v(\d+)_sm\.py$", p.name).group(1)
        )
    )

    print("=" * 70)
    print(f"REPLAY FILES FOUND: {len(files)}")
    print("=" * 70)

    if len(files) != 10:
        raise RuntimeError(
            f"Expected exactly 10 replay scripts, found {len(files)}"
        )

    # ========================================================
    # UPDATE EVERY FILE
    # ========================================================

    print()

    for path in files:

        print(f"Updating {path} ...")

        original = path.read_text()

        try:
            updated = replace_map(
                original,
                new_block
            )

        except Exception as e:
            print(f"ERROR: {e}")
            raise

        # Backup
        backup = Path(
            str(path) + ".bak"
        )

        backup.write_text(original)

        # Write new version
        path.write_text(updated)

        print(f"  OK")
        print(f"  Backup: {backup}")

    print()
    print("=" * 70)
    print("SUCCESS")
    print("=" * 70)

    print()
    print(
        f"Installed {len(mappings)} successful mappings "
        f"into {len(files)} replay scripts."
    )


if __name__ == "__main__":
    main()