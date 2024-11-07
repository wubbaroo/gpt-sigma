from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
import base64
import getpass

# Function to derive a key from a password
def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

# Function to decrypt the API key
def decrypt_api_key(password: str) -> str:
    # Read the encrypted API key and salt from the file
    with open('encrypted_api_key.txt', 'rb') as file:
        salt, encrypted_api_key = file.read().split(b'\n', 1)
    
    key = derive_key(password, salt)
    fernet = Fernet(key)
    
    try:
        decrypted_key = fernet.decrypt(encrypted_api_key).decode()
        return decrypted_key
    except Exception as e:
        print(f"Decryption failed: {e}")
        return None  # Return None if decryption fails

# Example usage (optional)
if __name__ == '__main__':
    password = getpass.getpass("Please enter the password to decrypt your API key: ")
    api_key = decrypt_api_key(password)
    if api_key:
        print(f"Decrypted API Key: {api_key}")
