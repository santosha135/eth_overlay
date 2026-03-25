const { Web3 } = require('web3');
const web3 = new Web3("http://127.0.0.1:32770"); // Change this to your node URL

// Function to list mined transactions and check their status
async function listBlocks() {
    try {
        // Get the latest block number
        const latestBlockNumber = await web3.eth.getBlockNumber();
        console.log('Latest Block Number:', latestBlockNumber);

        const startBlock = BigInt(latestBlockNumber) - BigInt(10000);
        const endBlock = BigInt(latestBlockNumber);

        // Store block summary
        const blocks = [];

        // Store transaction statuses
        const minedTransactions = [];

        // Loop through the last 20 blocks
        for (let blockNumber = startBlock; blockNumber <= endBlock; blockNumber++) {
            console.log(`Fetching block ${blockNumber.toString()}...`);
            
            // Get block details
            const block = await web3.eth.getBlock(Number(blockNumber), true); // Fetch transactions included

            if (!block) continue;

            for (let tx of block.transactions) {
                try {
                    // Fetch transaction receipt to check status
                    const receipt = await web3.eth.getTransactionReceipt(tx.hash);
                    
                    if (receipt) {
                        const status = receipt.status ? '0x1' : '0x0'; // Convert to hex string
                        const txDetails = {
                            Block: blockNumber.toString(),
                            TxHash: tx.hash,
                            From: tx.from,
                            To: tx.to ? tx.to : "Contract Creation",
                            GasUsed: receipt.gasUsed.toString(),
                            Status: status === '0x1' ? "✅ Success" : "❌ Failed",
                        };

                        minedTransactions.push(txDetails);
                    }
                } catch (txError) {
                    console.error(`Error fetching receipt for transaction ${tx.hash}:`, txError.message);
                }
            }

            // Store block data
            blocks.push({
                BlockNumber: blockNumber.toString(),
                BlockHash: block.hash,
                Miner: block.miner,
                Transactions: block.transactions.length,
                GasUsed: block.gasUsed.toString(),
                GasLimit: block.gasLimit.toString(),
                Timestamp: new Date(Number(block.timestamp) * 1000).toLocaleString(),
            });
        }

        // Display block summary
        console.log("\n📌 BLOCK SUMMARY:");
        console.table(blocks);

        // Display mined transactions with status
        console.log("\n📌 MINED TRANSACTIONS (Success & Failed):");
        if (minedTransactions.length > 0) {
            console.table(minedTransactions);
        } else {
            console.log("No transactions found in the last 20 blocks.");
        }

    } catch (error) {
        console.error('Error fetching block or transaction data:', error);
    }
}

// Call the function to list blocks and transactions
listBlocks();
