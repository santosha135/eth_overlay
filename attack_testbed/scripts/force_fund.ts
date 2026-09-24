import { ethers } from "hardhat";

async function main(): Promise<void> {
    // Existing smart contract that needs ETH
    const targetAddress =
        "0xb4B46bdAA835F8E4b4d8e208B6559cD267851051";

    // Amount to transfer into the smart contract
    const amountToFund = ethers.parseEther("1000");

    const [sender] = await ethers.getSigners();

    console.log("Sender address:", sender.address);
    console.log("Target contract:", targetAddress);
    console.log(
        "Funding amount:",
        ethers.formatEther(amountToFund),
        "ETH"
    );

    const senderBalanceBefore = await ethers.provider.getBalance(
        sender.address
    );

    const targetBalanceBefore = await ethers.provider.getBalance(
        targetAddress
    );

    const targetCode = await ethers.provider.getCode(targetAddress);

    console.log(
        "Sender balance before:",
        ethers.formatEther(senderBalanceBefore),
        "ETH"
    );

    console.log(
        "Target balance before:",
        ethers.formatEther(targetBalanceBefore),
        "ETH"
    );

    if (targetCode === "0x") {
        throw new Error(
            `No smart contract exists at ${targetAddress}`
        );
    }

    if (senderBalanceBefore < amountToFund) {
        throw new Error(
            `Sender does not have enough ETH. Sender balance: ` +
            `${ethers.formatEther(senderBalanceBefore)} ETH`
        );
    }

    console.log("Deploying ForceFund helper...");

    const ForceFund = await ethers.getContractFactory("ForceFund");

    const forceFund = await ForceFund.deploy(targetAddress, {
        value: amountToFund
    });

    const deploymentTransaction =
        forceFund.deploymentTransaction();

    if (deploymentTransaction === null) {
        throw new Error(
            "Could not obtain deployment transaction"
        );
    }

    console.log(
        "Transaction hash:",
        deploymentTransaction.hash
    );

    const receipt = await deploymentTransaction.wait();

    if (receipt === null) {
        throw new Error(
            "Transaction receipt was not returned"
        );
    }

    if (receipt.status !== 1) {
        throw new Error(
            "Force-funding transaction failed"
        );
    }

    const targetBalanceAfter = await ethers.provider.getBalance(
        targetAddress
    );

    const senderBalanceAfter = await ethers.provider.getBalance(
        sender.address
    );

    console.log("---------------------------------------");
    console.log("Force funding completed successfully");
    console.log("Block number:", receipt.blockNumber);
    console.log("Gas used:", receipt.gasUsed.toString());

    console.log(
        "Target balance after:",
        ethers.formatEther(targetBalanceAfter),
        "ETH"
    );

    console.log(
        "Sender balance after:",
        ethers.formatEther(senderBalanceAfter),
        "ETH"
    );

    const receivedAmount =
        targetBalanceAfter - targetBalanceBefore;

    console.log(
        "Target received:",
        ethers.formatEther(receivedAmount),
        "ETH"
    );

    if (receivedAmount !== amountToFund) {
        console.warn(
            "Warning: the target balance increase does not " +
            "equal the requested funding amount."
        );
    }
}

main()
    .then(() => {
        process.exitCode = 0;
    })
    .catch((error: unknown) => {
        console.error("Force funding failed:");

        if (error instanceof Error) {
            console.error(error.message);
        } else {
            console.error(error);
        }

        process.exitCode = 1;
    });
