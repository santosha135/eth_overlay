import Web3 from 'web3';

// Set up Web3 instance, connect to Kurtosis-local Ethereum node (replace with your actual node URL)
const infuraUrl = "http://127.0.0.1:32769"; // Replace with the actual RPC URL from Kurtosis Ethereum testnet
const web3 = new Web3(new Web3.providers.HttpProvider(infuraUrl));

// Sender and recipient details
const fromAddress = "0x2c57d1CFC6d5f8E4182a56b4cf75421472eBAEa4";  // Replace with the sender's Ethereum address
const toAddress = "0xf93Ee4Cf8c6c40b329b0c0626F28333c132CF241";     // Replace with the recipient's Ethereum address
const privateKey = "7ff1a4c1d57e5e784d327c4c7651e952350bc271f156afb3d00d20f5ef924856";        // Replace with your private key (NEVER hardcode in production)

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
    //const nonceString = "5";
    console.log("Nonce as string: ", nonceString);  // Debugging

    // Loop to send multiple transactions
    const numberOfTransactions =5;  // Set how many transactions you want to send
    for (let i = 1; i < numberOfTransactions; i++) {
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

      console.log(signedTx)
      // Send the signed transaction
       web3.eth.sendSignedTransaction(signedTx.rawTransaction);

      // Log the transaction hash


  
     
    }

  } catch (error) {
    console.error("Error sending transaction:", error);
  }
}

// Call the function to send the transaction
sendTransaction();
