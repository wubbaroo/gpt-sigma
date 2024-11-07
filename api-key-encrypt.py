from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
import os
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

# Encrypt the API key
def encrypt_api_key(api_key: str, password: str) -> tuple:
    salt = os.urandom(16)  # Generate a random salt
    key = derive_key(password, salt)
    fernet = Fernet(key)
    encrypted_key = fernet.encrypt(api_key.encode())
    return encrypted_key, salt

# Main logic
if __name__ == '__main__':
    # Prompt the user for their API key
    api_key = input("Please enter your API key: ")
    
    # Prompt for a password
    password = getpass.getpass("Please enter a password to encrypt your API key: ")
    
    # Encrypt and save the API key and salt to a file
    encrypted_api_key, salt = encrypt_api_key(api_key, password)
    with open('encrypted_api_key.txt', 'wb') as file:
        file.write(salt + b'\n' + encrypted_api_key)  # Store salt and encrypted key in the file

    print("API Key encrypted and saved.")

