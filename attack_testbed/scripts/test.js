const { Web3 } = require('web3');
const fs = require('fs');

// Import ABI from your contract's JSON file
const ABI = require('/home/santoshadhikari/awesome-kurtosis/smart-contract-example/artifacts/contracts/ConditionalExhaustCoinbaseVariant.sol/ConditionalExhaustCoinbaseVariant.json');  // Replace with your ABI path
const ContractABI = ABI.abi; // Extract the ABI from the JSON

// Connect to the local Ethereum node (you can use Infura if you’re using a testnet or mainnet)
const infuraUrl = "http://127.0.0.1:32769"; 
const web3 = new Web3(infuraUrl);

// Your contract address after deployment
const contractAddress = '0xb4B46bdAA835F8E4b4d8e208B6559cD267851051'; // Replace with your deployed contract address

// Your account details
const fromAddress = '0x614561D2d143621E126e87831AEF287678B442b8'; // Replace with your Ethereum account address
const privateKey = 'bcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31'; // Replace with your private key for signing the transaction

// Create contract instance
const myContract = new web3.eth.Contract(ContractABI, contractAddress);

// Keep track of the nonce manually
let nonce = 0;

async function sendTransactionWithRetry(tx) {
  let retries = 3;
  while (retries > 0) {
    try {
      const signedTx = await web3.eth.accounts.signTransaction(tx, privateKey);
      const receipt = await web3.eth.sendSignedTransaction(signedTx.rawTransaction);
      console.log('Transaction successful! Receipt:', receipt);
      return receipt;
    } catch (error) {
      if (error.message.includes('nonce too low')) {
        console.log('Nonce too low, retrying...');
        retries--;
        await delay(2000); // wait for 2 seconds before retrying
      } else {
        console.error('Transaction failed:', error);
        retries = 0; // If it's another error, stop retries
      }
    }
  }
  console.log('Retries exhausted.');
  return null;
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function callDoS() {
  try {
    const numberOfTransactions = 50;  // Set how many transactions you want to send

    // Get the initial nonce (transaction count) for the sender address, including pending transactions
    nonce = await web3.eth.getTransactionCount(fromAddress, 'pending');  // Use 'pending' to consider pending transactions

    console.log(`Starting with nonce: ${nonce}`);

    for (let i = 0; i < numberOfTransactions; i++) {
      console.log(`Sending transaction ${i + 1}...`);
      
      // Create the transaction object
      const tx = {
        from: fromAddress,
        to: contractAddress,
        gas: 500000,  // Adjust the gas limit as needed
        gasPrice: web3.utils.toWei("50", 'gwei'),  // You can set your custom gas price
        nonce: nonce,  // Use the manually tracked nonce
        data: myContract.methods.DoS(i).encodeABI(), // Call the DoS method with input argument 'i'
        value: '0'  // If the function is payable, you can include Ether here. Set to '0' for no Ether
      };

      const receipt = await sendTransactionWithRetry(tx);
      
      if (receipt) {
        console.log(`Transaction ${i + 1} successful! Nonce was: ${nonce}`);
        nonce++;  // Increment nonce after sending the transaction
      } else {
        console.log(`Transaction ${i + 1} failed after retries.`);
      }
    }
  } catch (error) {
    console.error('Error calling DoS:', error);
  }
}

// Call the DoS function
callDoS();
