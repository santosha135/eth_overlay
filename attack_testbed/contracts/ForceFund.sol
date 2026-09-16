// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title ForceFund
 * @notice Forces ETH into another address during deployment.
 *
 * The constructor receives ETH and immediately transfers the entire
 * contract balance to the target address using SELFDESTRUCT.
 */
contract ForceFund {
    constructor(address payable target) payable {
        require(target != address(0), "Invalid target address");
        require(msg.value > 0, "No ETH supplied");

        selfdestruct(target);
    }
}