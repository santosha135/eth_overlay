import Web3 from 'web3';

import fs from 'fs';

// Set up Web3 instance, connect to Kurtosis-local Ethereum node (replace with your actual node URL)
const infuraUrl = "http://127.0.0.1:32901"; // Replace with the actual RPC URL from Kurtosis Ethereum testnet
const web3 = new Web3(new Web3.providers.HttpProvider(infuraUrl));

// Sender and recipient details
const fromAddress = "0x8943545177806ED17B9F23F0a21ee5948eCaa776";  // Replace with the sender's Ethereum address
const toAddress = "0x614561D2d143621E126e87831AEF287678B442b8";     // Replace with the recipient's Ethereum address
const privateKey = "bcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31";        // Replace with your private key (NEVER hardcode in production)

//to check balance

// web3.eth.getBalance('0x2625b63abe7b144dc22f74e02019a1fad9b9a7bc')

//send eth

// web3.eth.sendTransaction({
//   from: '0x479e5fF0991386DBfd15961C6E6f64cc6E1d2Ec6',
//   to: '0x7462e771ea01a51a960240cf4f4391353453339d',
//   value: web3.utils.toWei('1000', 'ether')
// }
//
const accounts = await web3.eth.getAccounts();
console.log("Available accounts: ", accounts);


// Transaction details
const valueInEther = "0.1";  // Amount to send in Ether (e.g., 0.1 ETH)
const gasLimit = 21000;      // Gas limit for a simple transfer (standard ETH transfer)
const gasPriceInGwei = 20;   // Gas price in Gwei

// Function to send the transaction
async function sendTransaction() {
  try {
    // Convert value from Ether to Wei (since Ethereum uses Wei as the smallest unit)
    const valueInWei = web3.utils.toWei(valueInEther, 'ether');
    console.log("Converted valueInWei: ", valueInWei);  // Debugging

    // Ensure that gas price is a string and convert it to Wei
    const gasPrice = web3.utils.toWei(gasPriceInGwei.toString(), 'gwei');
    console.log("Converted gasPrice: ", gasPrice);  // Debugging

    // Get the nonce (transaction count for the sender)
    const nonce = await web3.eth.getTransactionCount(fromAddress);
    console.log("Nonce (BigInt): ", nonce);  // Debugging

    // Explicitly convert nonce to string
    const nonceString = nonce.toString();
    console.log("Nonce as string: ", nonceString);  // Debugging

    // Loop to send multiple transactions
    const numberOfTransactions = 5;  // Set how many transactions you want to send
    for (let i = 0; i < numberOfTransactions; i++) {
      // Explicitly convert everything to string
      const tx = {
        from: fromAddress,
        to: toAddress,
        value: valueInWei.toString(),  // Ensure value is passed as string
        gas: gasLimit.toString(),      // Ensure gas is passed as string
        gasPrice: gasPrice,            // Ensure gasPrice is passed as string
        //nonce : 0,
         nonce: (parseInt(nonceString) +i).toString(), // Explicitly convert to string
      };

      console.log("Transaction object: ", tx);  // Debugging

      // Get the current time (when the transaction is sent)
      const startTime = Date.now();  // This is your "start time"
      console.log(startTime/1000);

      // Sign the transaction with the sender's private key
      const signedTx = await web3.eth.accounts.signTransaction(tx, privateKey);

      // Convert rawTransaction hex string to bytes
      const txBytes = Buffer.from(signedTx.rawTransaction.slice(2), "hex");

      // const txBytes = Buffer.from(rawTransaction.slice(2), "hex");

      // Convert to hex array format: 0xf8, 0x6f, ...
      const hexArray = Array.from(txBytes).map(b =>
        "0x" + b.toString(16).padStart(2, "0")
      );

      // Format as multi-line block
      const formatted =
        "[\n    " +
        hexArray.map((v, i) => (i % 8 === 0 && i !== 0 ? "\n    " : "") + v).join(", ") +
        "\n],\n";

      // Append to file (for multiple transactions)
      fs.appendFileSync("/home/narwhal/narwhal/node/src/transactions.txt", formatted);
          
      
      // Write to binary file
      // fs.writeFileSync("/home/narwhal/narwhal/node/src/transaction.bin", txBytes);

      console.log(signedTx)
      // Send the signed transaction
      const receipt = await web3.eth.sendSignedTransaction(signedTx.rawTransaction);

      // Log the transaction hash
      console.log(`Transaction ${i + 1} successful with hash:`, receipt.transactionHash);

      // Monitor the transaction and check if it is mined
      let receipt1;
      let mined = false;
      while (!mined) {
        receipt1 = await web3.eth.getTransactionReceipt(receipt.transactionHash);

        if (receipt1) {
          // If the receipt is found, the transaction is mined
          mined = true;
        } else {
          console.log('Waiting for transaction to be mined...');
          await new Promise(resolve => setTimeout(resolve, 5000));  // Wait 5 seconds before retrying
        }
      }

      // Get the block mined time (timestamp)
      const block = await web3.eth.getBlock(receipt1.blockNumber);
      const blockMinedTime = Number(block.timestamp);

      console.log(Number(blockMinedTime) );

      // Calculate the elapsed time in seconds
      const elapsedTimeInSeconds = (blockMinedTime - startTime / 1000);
      console.log(`Transaction mined in ${elapsedTimeInSeconds} seconds`);
      console.log('Transaction Receipt:', receipt1);
    }

  } catch (error) {
    console.error("Error sending transaction:", error);
  }
}

// Call the function to send the transaction
sendTransaction();
