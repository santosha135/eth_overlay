import Web3 from "web3";

const infuraUrl = "http://127.0.0.1:32003";
const web3 = new Web3(infuraUrl);

const MASTER_PK =
  "0xbcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31";

const TO_ADDR = Web3.utils.toChecksumAddress(
  "0x8e76be392dd23911f3f403e82b24d3a660761fb1"
);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForReceipt(txHash, timeoutMs = 120000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const receipt = await web3.eth.getTransactionReceipt(txHash);
      if (receipt && receipt.blockNumber != null) return receipt;
    } catch (e) {
      // Web3 often throws TransactionNotFound (code 430) right after broadcast.
      // Ignore and keep polling.
      if (!(e && (e.code === 430 || String(e.message || "").includes("not found")))) {
        throw e;
      }
    }
    await sleep(1000);
  }
  throw new Error(`Timeout waiting for receipt: ${txHash}`);
}

async function main() {
  const master = web3.eth.accounts.privateKeyToAccount(MASTER_PK);

  console.log("[RPC]", infuraUrl);
  console.log("[MASTER]", master.address);
  console.log("[TO]", TO_ADDR);

  const chainId = Number(await web3.eth.getChainId()); // convert BigInt
  const block = await web3.eth.getBlockNumber();
  console.log("[chainId]", chainId, "[block]", block);

  const nonce = await web3.eth.getTransactionCount(master.address, "pending");
  console.log("[nonce]", nonce);

  // bump gasPrice to avoid "underpriced"
  const gasPrice = web3.utils.toWei("50", "gwei");

  const tx = {
    from: master.address,
    to: TO_ADDR,
    value: web3.utils.toWei("1", "ether"),
    gas: 21000,
    gasPrice,
    nonce,
    chainId,
  };

  const signed = await web3.eth.accounts.signTransaction(tx, MASTER_PK);

  console.log("[SEND] broadcasting...");
  const sendProm = web3.eth.sendSignedTransaction(signed.rawTransaction);

  const txHash = await new Promise((resolve, reject) => {
    sendProm.once("transactionHash", resolve);
    sendProm.once("error", reject);
  });

  console.log("[txHash]", txHash);

  const receipt = await waitForReceipt(txHash, 120000);
  console.log("[MINED] block", receipt.blockNumber);

  const bal = await web3.eth.getBalance(TO_ADDR);
  console.log("[TO BALANCE]", bal.toString(), "wei");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
