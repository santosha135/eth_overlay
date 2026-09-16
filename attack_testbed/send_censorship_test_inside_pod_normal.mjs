import Web3 from 'web3';
import fs from 'fs';
import { execSync } from 'child_process';



 const rpcUrl = "http://el-01-geth-lighthouse:8545";
 const web3 = new Web3(new Web3.providers.HttpProvider(rpcUrl));

// Sender and recipient
const fromAddress = "0x2c57d1CFC6d5f8E4182a56b4cf75421472eBAEa4";
const toAddress = "0xf93Ee4Cf8c6c40b329b0c0626F28333c132CF241";
const privateKey = "7ff1a4c1d57e5e784d327c4c7651e952350bc271f156afb3d00d20f5ef924856";

// Transaction config
const valueInEther = "0.1";
const gasLimit = 21000;
const gasPriceInGwei = "20";
const numberOfTransactions = 5;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function normalizeReceiptStatus(status) {
  return (
    status === true ||
    status === 1 ||
    status === 1n ||
    status === "1" ||
    status === "0x1"
  );
}

async function sendTransactions() {
  try {
    const accounts = await web3.eth.getAccounts();
    console.log("Available accounts:", accounts);

    const valueInWei = web3.utils.toWei(valueInEther, 'ether');
    const gasPrice = web3.utils.toWei(gasPriceInGwei, 'gwei');

    const baseNonce = Number(await web3.eth.getTransactionCount(fromAddress, 'pending'));
    console.log("Base nonce:", baseNonce);

    const results = [];
    const batchStartMs = Date.now();

    const chainId = await web3.eth.getChainId();
    const fromBalance = await web3.eth.getBalance(fromAddress);
    const toBalance = await web3.eth.getBalance(toAddress);
    const toCode = await web3.eth.getCode(toAddress);

    console.log("Chain ID       :", chainId.toString());
    console.log("From address   :", fromAddress);
    console.log("To address     :", toAddress);
    console.log("From balance   :", web3.utils.fromWei(fromBalance.toString(), "ether"), "ETH");
    console.log("To balance     :", web3.utils.fromWei(toBalance.toString(), "ether"), "ETH");
    console.log("To code        :", toCode);
    console.log("To is contract :", toCode !== "0x");

    for (let i = 0; i < numberOfTransactions; i++) {
      const nonce = baseNonce + i;

      const tx = {
        from: fromAddress,
        to: toAddress,
        value: valueInWei.toString(),
        gas: gasLimit.toString(),
        gasPrice: gasPrice.toString(),
        nonce: nonce.toString(),
      };

      console.log(`\nSending transaction ${i + 1}/${numberOfTransactions}`);
      console.log("TX object:", tx);

      const signedTx = await web3.eth.accounts.signTransaction(tx, privateKey);

      if (!signedTx.rawTransaction) {
        throw new Error(`Failed to sign transaction ${i + 1}`);
      }

      const txBytes = Buffer.from(signedTx.rawTransaction.slice(2), "hex");
      const hexArray = Array.from(txBytes).map(b => "0x" + b.toString(16).padStart(2, "0"));
      const formatted =
        "[\n    " +
        hexArray.map((v, idx) => (idx % 8 === 0 && idx !== 0 ? "\n    " : "") + v).join(", ") +
        "\n],\n";
      fs.appendFileSync("/root/attack_testbed/transactions.txt", formatted);

      const sendStartMs = Date.now();

      try {
        const receipt = await web3.eth.sendSignedTransaction(signedTx.rawTransaction);
        const receiptTimeMs = Date.now();
        const latencyMs = receiptTimeMs - sendStartMs;

        const block = await web3.eth.getBlock(receipt.blockNumber);
        const blockTimestampSec = Number(block.timestamp);
        const isSuccess = normalizeReceiptStatus(receipt.status);

        const txResult = {
          index: i + 1,
          nonce,
          transactionHash: receipt.transactionHash,
          blockNumber: Number(receipt.blockNumber),
          blockTimestampSec,
          latencyMs,
          latencySec: latencyMs / 1000,
          status: isSuccess,
          rawStatus: receipt.status?.toString?.() ?? receipt.status,
          gasUsed: Number(receipt.gasUsed),
          cumulativeGasUsed: Number(receipt.cumulativeGasUsed),
          from: receipt.from,
          to: receipt.to,
        };

        results.push(txResult);

        console.log(`Transaction ${i + 1} mined`);
        console.log(`Hash          : ${txResult.transactionHash}`);
        console.log(`Block         : ${txResult.blockNumber}`);
        console.log(`Status raw    : ${txResult.rawStatus} (${typeof receipt.status})`);
        console.log(`Status        : ${txResult.status ? "SUCCESS" : "FAILED"}`);
        console.log(`Latency       : ${txResult.latencySec.toFixed(3)} sec`);
        console.log(`Gas Used      : ${txResult.gasUsed}`);
      } catch (txError) {
        const receiptTimeMs = Date.now();
        const latencyMs = receiptTimeMs - sendStartMs;

        const txResult = {
          index: i + 1,
          nonce,
          transactionHash: null,
          blockNumber: null,
          blockTimestampSec: null,
          latencyMs,
          latencySec: latencyMs / 1000,
          status: false,
          rawStatus: null,
          gasUsed: null,
          cumulativeGasUsed: null,
          from: fromAddress,
          to: toAddress,
          error: txError.message,
        };

        results.push(txResult);
        console.error(`Transaction ${i + 1} failed before mining:`, txError.message);
      }

      await sleep(200);
    }

    const batchEndMs = Date.now();
    const totalDurationSec = (batchEndMs - batchStartMs) / 1000;

    const minedTransactions = results.filter(r => r.blockNumber !== null).length;
    const successTransactions = results.filter(r => r.status === true).length;
    const failedTransactions = results.filter(r => r.blockNumber !== null && r.status === false).length;
    const droppedTransactions = results.filter(r => r.blockNumber === null).length;

    const minedLatencies = results
      .filter(r => r.blockNumber !== null)
      .map(r => r.latencyMs);

    const successLatencies = results
      .filter(r => r.status === true)
      .map(r => r.latencyMs);

    const avgMinedLatencyMs =
      minedLatencies.length > 0
        ? minedLatencies.reduce((a, b) => a + b, 0) / minedLatencies.length
        : 0;

    const minMinedLatencyMs =
      minedLatencies.length > 0 ? Math.min(...minedLatencies) : 0;

    const maxMinedLatencyMs =
      minedLatencies.length > 0 ? Math.max(...minedLatencies) : 0;

    const avgSuccessLatencyMs =
      successLatencies.length > 0
        ? successLatencies.reduce((a, b) => a + b, 0) / successLatencies.length
        : 0;

    const txRateOverall = numberOfTransactions / totalDurationSec;
    const txRateSuccessful = successTransactions / totalDurationSec;
    const txRateMined = minedTransactions / totalDurationSec;

    const summary = {
      totalTransactions: numberOfTransactions,
      minedTransactions,
      successTransactions,
      failedTransactions,
      droppedTransactions,
      totalDurationSec,
      txRateOverall,
      txRateMined,
      txRateSuccessful,
      avgMinedLatencyMs,
      minMinedLatencyMs,
      maxMinedLatencyMs,
      avgSuccessLatencyMs,
      results,
    };

    console.log("\n================ FINAL SUMMARY ================");
    console.log(`Total transactions     : ${summary.totalTransactions}`);
    console.log(`Mined transactions     : ${summary.minedTransactions}`);
    console.log(`Successful transactions: ${summary.successTransactions}`);
    console.log(`Failed transactions    : ${summary.failedTransactions}`);
    console.log(`Dropped transactions   : ${summary.droppedTransactions}`);
    console.log(`Total duration         : ${summary.totalDurationSec.toFixed(3)} sec`);
    console.log(`Overall tx rate        : ${summary.txRateOverall.toFixed(3)} tx/sec`);
    console.log(`Mined tx rate          : ${summary.txRateMined.toFixed(3)} tx/sec`);
    console.log(`Successful tx rate     : ${summary.txRateSuccessful.toFixed(3)} tx/sec`);
    console.log(`Average mined latency  : ${(summary.avgMinedLatencyMs / 1000).toFixed(3)} sec`);
    console.log(`Min mined latency      : ${(summary.minMinedLatencyMs / 1000).toFixed(3)} sec`);
    console.log(`Max mined latency      : ${(summary.maxMinedLatencyMs / 1000).toFixed(3)} sec`);
    console.log(`Average success latency: ${(summary.avgSuccessLatencyMs / 1000).toFixed(3)} sec`);

    fs.writeFileSync(
      "/root/attack_testbed/tx_summary.json",
      JSON.stringify(summary, null, 2)
    );

    console.log("\nSummary written to:");
    console.log("/root/attack_testbed/tx_summary.json");

  } catch (error) {
    console.error("Error sending transactions:", error);
  }
}

sendTransactions();

