import { ethers } from "hardhat";
import { Contract, ContractFactory } from "ethers";

async function deployContract(
  name: string,
  args: any[] = []
): Promise<string> {
  console.log(`\n========================================`);
  console.log(`Deploying ${name}...`);
  console.log(`========================================`);

  const Factory: ContractFactory =
    await ethers.getContractFactory(name);

  const contract: Contract =
    (await Factory.deploy(...args)) as Contract;

  await contract.waitForDeployment();

  const address = await contract.getAddress();

  console.log(`${name} deployed to: ${address}`);

  return address;
}

async function main() {
  const [deployer] = await ethers.getSigners();

  console.log("========================================");
  console.log("Deployer");
  console.log("========================================");
  console.log("Address:", deployer.address);
  console.log(
    "Balance:",
    ethers.formatEther(
      await ethers.provider.getBalance(deployer.address)
    ),
    "ETH"
  );

  const addresses: Record<string, string> = {};

  // ============================================================
  // 1. WETH9
  // No constructor arguments
  // ============================================================

  addresses.WETH9 =
    await deployContract("WETH9");


  // ============================================================
  // 2. DegenerateDachshunds
  //
  // constructor(string memory baseURI)
  // ============================================================

  addresses.DegenerateDachshunds =
    await deployContract(
      "DegenerateDachshunds",
      [
        "https://example.com/metadata/"
      ]
    );


  // ============================================================
  // 3. TetherToken
  //
  // constructor:
  // TetherToken(
  //     uint _initialSupply,
  //     string _name,
  //     string _symbol,
  //     uint _decimals
  // )
  //
  // This old Tether contract uses Solidity 0.4.x.
  // USDT uses 6 decimals.
  // Example = 1,000,000 USDT
  // ============================================================

  const tetherInitialSupply =
    1_000_000n * 10n ** 6n;

  addresses.TetherToken =
    await deployContract(
      "TetherToken",
      [
        tetherInitialSupply,
        "Tether USD",
        "USDT",
        6
      ]
    );


  // ============================================================
  // 4. ZeroEx
  // No constructor arguments
  //
  // NOTE:
  // This will work ONLY if all required 0x dependencies are
  // present in your Hardhat project.
  // ============================================================

  addresses.ZeroEx =
    await deployContract("ZeroEx");


  // ============================================================
  // 5. CommonAdapter
  // No constructor arguments
  //
  // NOTE:
  // Requires:
  //   @openzeppelin/contracts
  //   ../Constants.sol
  // ============================================================

  addresses.CommonAdapter =
    await deployContract("CommonAdapter");


  // ============================================================
  // The remaining contracts need special handling.
  // ============================================================

  console.log("\n\n========================================");
  console.log("DEPLOYED CONTRACT ADDRESSES");
  console.log("========================================");

  for (const [name, address] of Object.entries(addresses)) {
    console.log(`${name}: ${address}`);
  }

  console.log("\n========================================");
  console.log("Deployment finished");
  console.log("========================================");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });