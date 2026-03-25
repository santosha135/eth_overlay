const {Web3} = require ('web3');
const  fs = require ('fs');

// Import ABI from your contract's JSON file
const ABI = require('/home/narwhal/attack_testbed/artifacts/contracts/ConditionalExhaustCoinbaseVariant.sol/ConditionalExhaustCoinbaseVariant.json');
// const ABI = require('/home/santoshadhikari/awesome-kurtosis/smart-contract-example/artifacts/contracts/ConditionalExhaustCoinbaseVariant.sol/ConditionalExhaustCoinbaseVariant.json');  // Replace with your ABI path
const ContractABI = ABI.abi; // Extract the ABI from the JSON

// Connect to the local Ethereum node (you can use Infura if you’re using a testnet or mainnet)
const infuraUrl = "http://127.0.0.1:32861"; 
const web3 = new Web3(infuraUrl);

// Your contract address after deployment
const contractAddress = '0x17435ccE3d1B4fA2e5f8A08eD921D57C6762A180'; // Replace with your deployed contract address

// Your account details
const fromAddress = '0x8943545177806ED17B9F23F0a21ee5948eCaa776'; // Replace with your Ethereum account address
const privateKey = 'bcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31'; // Replace with your private key for signing the transaction

// Create contract instance
const myContract = new web3.eth.Contract(ContractABI, contractAddress);

async function callDoS(i) {
  try {
    // Get the nonce (transaction count) for the sender address
    const nonce = await web3.eth.getTransactionCount(fromAddress, 'latest');
    console.log(nonce);
    // Create the transaction object
    const tx = {
      from: fromAddress,
      to: contractAddress,
      gas: 500000,  // Adjust the gas limit as needed
      gasPrice: web3.utils.toWei("50", 'gwei'),  // You can set your custom gas price
     
      //gasPrice: await web3.eth.getGasPrice(),  // You can set your custom gas price
      nonce: nonce,
      data: myContract.methods.DoS(i).encodeABI(), // Call the DoS method with input argument 'i'
      value: '0'  // If the function is payable, you can include Ether here. Set to '0' for no Ether
    };

    // Sign the transaction with your private key
    const signedTx = await web3.eth.accounts.signTransaction(tx, privateKey);

    // Send the signed transaction to the network
    const receipt = await web3.eth.sendSignedTransaction(signedTx.rawTransaction);

    // Log the receipt (this shows the result of the transaction)
    console.log('Transaction successful! Receipt:', receipt);
  } catch (error) {
    console.error('Error calling DoS:', error);
  }
}

// Call the DoS function with the argument 10 (you can change this to any value)
callDoS(10);
