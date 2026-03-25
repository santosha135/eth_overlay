const {Web3} = require ('web3');
const  fs = require ('fs');

const ABI = require('/home/narwhal/attack_testbed/artifacts/contracts/ConditionalExhaustCoinbaseVariant.sol/ConditionalExhaustCoinbaseVariant.json');
//import ABI from '/home/santoshadhikari/awesome-kurtosis/smart-contract-example/artifacts/contracts/ConditionalExhaustCoinbaseVariant.sol/ConditionalExhaustCoinbaseVariant.json';
// const ABI = require('/home/santoshadhikari/awesome-kurtosis/smart-contract-example/artifacts/contracts/ConditionalExhaustCoinbaseVariant.sol/ConditionalExhaustCoinbaseVariant.json');
const ContractABI =  ABI.abi; // add ".abi" to RightsTokenABI
// Load Web3 and setup the provider
const infuraUrl = "http://127.0.0.1:32861"; // RPC URL  
const web3 = new Web3(infuraUrl);

// Load contract ABI and address
//const contractJSON = JSON.parse(fs.readFileSync('/home/santoshadhikari/awesome-kurtosis/smart-contract-example/artifacts/contracts/ConditionalExhaustCoinbaseVariant.sol/ConditionalExhaustCoinbaseVariant.json', 'utf-8'));
//const contractABI = contractJSON.abi;
const contractAddress = '0xb4B46bdAA835F8E4b4d8e208B6559cD267851051'; // Replace with actual address

// Create contract instance
const myContract = new web3.eth.Contract(ContractABI, contractAddress);

// Call DoS function
myContract.methods.DoS(10).send({ from: '0x8943545177806ED17B9F23F0a21ee5948eCaa776' })
  .then(result => {
    console.log('Contract value:', result);
  })
  .catch(error => {
    console.error('Error calling DoS:', error);
  });


