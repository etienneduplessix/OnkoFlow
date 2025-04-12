import json
import base64
import brotli
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def generate_reverse_mapping(backbone):
    """Create a reverse mapping from short IDs to original names"""
    return {v: k for k, v in backbone.items()}

def restore_keys(data, reverse_mapping):
    """Recursively restore original keys from short IDs"""
    if isinstance(data, dict):
        return {
            reverse_mapping.get(key, key): restore_keys(value, reverse_mapping)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [restore_keys(item, reverse_mapping) for item in data]
    else:
        return data

def decrypt_and_decompress(encoded_data):
    """Decrypt and decompress the encoded QR data"""
    # Base64 decode
    encrypted_data = base64.b64decode(encoded_data)
    
    # Extract salt, nonce and encrypted data
    salt = encrypted_data[:16]
    nonce = encrypted_data[16:28]
    ciphertext = encrypted_data[28:]
    
    # Recreate the key using the same password and salt
    password = "secure-medical-data-password"  # Must match encrypt.py
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = kdf.derive(password.encode('utf-8'))
    
    # Decrypt the data
    aesgcm = AESGCM(key)
    compressed = aesgcm.decrypt(nonce, ciphertext, None)
    
    # Decompress using Brotli
    json_bytes = brotli.decompress(compressed)
    
    # Load JSON
    return json.loads(json_bytes.decode('utf-8'))
