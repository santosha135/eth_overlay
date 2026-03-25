

from web3 import Web3
import binascii

# Path to the keystore file
keystore_file_path = "/home/santoshadhikari/private_ethereum_setup/keystore/UTC--2025-02-25T18-41-24.423437999Z--7462e771ea01a51a960240cf4f4391353453339d"



# Passphrase used to encrypt the keystore file
passphrase = "santosh123"

# Initialize Web3 instance (without connecting to a node, just for decryption)
w3 = Web3()

# Read the keystore file content
with open(keystore_file_path, 'r') as keyfile:
    encrypted_key = keyfile.read()

# Decrypt the keystore with Web3.py
try:
    private_key = w3.eth.account.decrypt(encrypted_key, passphrase)
    print("Private Key: ", binascii.b2a_hex(private_key))
except Exception as e:
    print(f"Error: {e}")