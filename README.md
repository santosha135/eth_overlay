Geth Attack Testbed

This repository contains scripts for setting up, cleaning up, deploying, testing, replaying transactions, and generating plots for the Geth attack testbed.

Prerequisites

Before starting any Geth or Kurtosis environment, make sure the required Docker images are imported and the environment is cleaned up.

Setup and Cleanup

Use the following script to initialize and clean up the environment:

./cleanup_start.sh


Run this script before starting any Geth or Kurtosis instance.

Docker Images

Before starting the testbed, import the required Docker images/packages using the following scripts:

./deploy_geth_overlay_new_normal.sh
./clean_image.sh
./deploy_geth_overlay.sh


Make sure the required Docker images are available before proceeding with the Geth/Kurtosis setup.

Starting Geth / Kurtosis

The recommended workflow is:

1. Run cleanup_start.sh
2. Import/deploy the required Docker images
3. Start the Geth or Kurtosis environment
4. Run the required attack or replay scripts
5. Collect the results
6. Generate plots using the scripts in the plot result folder
7. Run cleanup_start.sh when finished

Attack and Replay Scripts

All attack and transaction replay scripts are available under:

attack_testbed/


Replay scripts follow the naming convention:

replay_tx_v*.py


For example:

python attack_testbed/replay_tx_v1.py


Check the individual script for its required arguments and configuration before running it.

Plotting Results

All plotting scripts are available under:

plot result/


Use the appropriate plotting script after the test/replay has completed and the results have been generated.

Recommended Workflow

A typical test run should follow this order:

# 1. Clean and initialize the environment
./cleanup_start.sh

# 2. Import/deploy Docker images
./deploy_geth_overlay_new_normal.sh
./clean_image.sh
./deploy_geth_overlay.sh

# 3. Start Geth/Kurtosis
# ... start your required environment here ...

# 4. Run an attack or replay test
python attack_testbed/replay_tx_v*.py

# 5. Generate plots
# Run the appropriate script from:
# plot result/

# 6. Clean up after the experiment
./cleanup_start.sh

Important Notes

Always run cleanup_start.sh before starting Geth or Kurtosis.

Make sure the required Docker images have been imported/deployed before starting the testbed.

Attack and replay scripts are located in attack_testbed/.

Replay scripts use the replay_tx_v*.py naming convention.

Plotting scripts are located in plot result/.

Check each script's arguments and configuration before execution.
