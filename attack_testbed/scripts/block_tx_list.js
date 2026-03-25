const {Web3} = require ('web3');
const web3 = new Web3("http://127.0.0.1:32770"); // Change this to your node URL


// Function to list block details in a tabular format
async function listBlocks() {
  try {
    // Get the latest block number (BigInt)
    const latestBlockNumber = await web3.eth.getBlockNumber();
    console.log('Latest Block Number:', latestBlockNumber);

    // Convert 100 to BigInt to ensure proper arithmetic with latestBlockNumber
    const startBlock = BigInt(latestBlockNumber) - BigInt(20);
    const endBlock = BigInt(latestBlockNumber);

    // Create an array to store block details for tabular output
    const blocks = [];

    
    // Loop through the blocks in the defined range and get block details
    for (let blockNumber = startBlock; blockNumber <= endBlock; blockNumber++) {

      console.log(blockNumber.toString());
      const block = await web3.eth.getBlock(Number(blockNumber)); // Convert BigInt to number for web3 call
      const blockData = {
        BlockNumber: blockNumber.toString(),  // Ensure it's a string for consistent table format
        BlockHash: block.hash,
        Miner: block.miner,
        //Status: blockStatus,
        Transactions: block.transactions.length,
        GasUsed: block.gasUsed.toString(), // Explicitly convert to string
        GasLimit: block.gasLimit.toString(), // Explicitly convert to string
        // Convert Unix timestamp to readable format
        Timestamp: new Date(Number(block.timestamp) * 1000).toLocaleString(),
      };
      blocks.push(blockData);
    }

    // Display the blocks in a tabular format
    console.table(blocks);

  } catch (error) {
    console.error('Error fetching block data:', error);
  }
}

// Call the function to list blocks and transactions
listBlocks();
