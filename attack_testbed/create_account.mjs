import Web3 from 'web3';

import fs from 'fs';

// Set up Web3 instance, connect to Kurtosis-local Ethereum node (replace with your actual node URL)
const infuraUrl = "http://127.0.0.1:32003"; // Replace with the actual RPC URL from Kurtosis Ethereum testnet
const web3 = new Web3(new Web3.providers.HttpProvider(infuraUrl));

const acct = web3.eth.accounts.create();
console.log("Address:", acct.address);
console.log("Private Key:", acct.privateKey);
