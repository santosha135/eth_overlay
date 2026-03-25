import Web3 from 'web3';

// Set up Web3 instance, connect to Kurtosis-local Ethereum node (replace with your actual node URL)
const infuraUrl = "http://127.0.0.1:32773"; // Replace with the actual RPC URL from Kurtosis Ethereum testnet
const web3 = new Web3(new Web3.providers.HttpProvider(infuraUrl));

// Sender and recipient details
const fromAddress = "0x8943545177806ED17B9F23F0a21ee5948eCaa776";  // Replace with the sender's Ethereum address
const toAddress = "0x614561D2d143621E126e87831AEF287678B442b8";     // Replace with the recipient's Ethereum address
const privateKey = "bcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31";        // Replace with your private key (NEVER hardcode in production)

// Transaction details
const valueInEther = "0.1";  // Amount to send in Ether (e.g., 0.1 ETH)
const gasLimit = 21000;      // Gas limit for a simple transfer (standard ETH transfer)
const gasPriceInGwei = 90;   // Gas price in Gwei

// Function to send a single transaction
async function sendTransaction(i, nonce) {
  try {
    // Convert value from Ether to Wei (since Ethereum uses Wei as the smallest unit)
    const valueInWei = web3.utils.toWei(valueInEther, 'ether');

    // Ensure that gas price is a string and convert it to Wei
    const gasPrice = web3.utils.toWei(gasPriceInGwei.toString(), 'gwei');

    // Create the transaction object
    const tx = {
      from: fromAddress,
      to: toAddress,
      value: valueInWei.toString(),  // Ensure value is passed as string
      gas: gasLimit.toString(),      // Ensure gas is passed as string
      gasPrice: gasPrice,            // Ensure gasPrice is passed as string
      nonce: (parseInt(nonce) + i).toString(), // Explicitly convert to string
    };

    // Sign the transaction with the sender's private key
    const signedTx = await web3.eth.accounts.signTransaction(tx, privateKey);

    // Send the signed transaction
    const receipt = await web3.eth.sendSignedTransaction(signedTx.rawTransaction);

    // Log the transaction hash
    console.log(`Transaction ${i + 1} successful with hash:`, receipt.transactionHash);

  } catch (error) {
    console.error(`Error sending transaction ${i + 1}:`, error);
  }
}

// Function to send multiple transactions in parallel
async function sendTransactions() {
  try {
    // Get the nonce (transaction count for the sender)
    const nonce = await web3.eth.getTransactionCount(fromAddress);

    // Set how many transactions you want to send
    const numberOfTransactions = 1000;

    // Create an array of promises for sending multiple transactions in parallel
    const transactionPromises = [];
    for (let i = 0; i < numberOfTransactions; i++) {
      transactionPromises.push(sendTransaction(i, nonce));
    }

    // Wait for all transactions to complete
    await Promise.all(transactionPromises);
    console.log('All transactions have been sent successfully!');
  } catch (error) {
    console.error('Error sending transactions:', error);
  }
}

// Call the function to send multiple transactions
sendTransactions();
