const {Web3} = require ('web3');
const web3 = new Web3("http://127.0.0.1:32770"); // Change this to your node URL

// Function to list pending transactions
async function listPendingTransactions() {
  while (true){
    try {
      // Fetch all pending transactions from the node's mempool using the `eth_pendingTransactions` RPC
      const pendingTransactions = await web3.eth.getPendingTransactions();
  
      if (pendingTransactions.length === 0) {
        //console.log("No pending transactions.");
        continue;
      }
  

      // Map the pending transactions into a readable format
      const transactions = pendingTransactions.map(tx => {
        return {
          Hash: tx.hash,
          From: tx.from,
          To: tx.to || 'Contract Call',  // 'to' might be null for contract creation
          Gas: tx.gas,
          GasPrice: web3.utils.fromWei(tx.gasPrice, 'gwei') + ' Gwei',  // Gas price in Gwei
          Value: web3.utils.fromWei(tx.value, 'ether') + ' ETH',  // Transaction value in ETH
          Nonce: tx.nonce,
          Input: tx.input.length > 20 ? tx.input.slice(0, 20) + '...' : tx.input  // Show only first 20 characters of input
        };
      });
  
      // Display the pending transactions in a tabular format
      console.table(transactions);
  
    } catch (error) {
      console.error('Error fetching pending transactions:', error);
    }
  }
  }
  
  // Call the function to list pending transactions
  listPendingTransactions();
  