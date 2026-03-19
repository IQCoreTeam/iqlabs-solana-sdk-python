from typing import TypedDict

from .encoding import bytes_to_hex
from .primitives import pbkdf2_derive, aes_encrypt, aes_decrypt, get_random_bytes


class PasswordEncryptResult(TypedDict):
    salt: str
    iv: str
    ciphertext: str


def password_encrypt(password: str, plaintext: bytes) -> PasswordEncryptResult:
    salt = bytes_to_hex(get_random_bytes(16))
    aes_key = pbkdf2_derive(password, salt)
    result = aes_encrypt(aes_key, plaintext)
    return PasswordEncryptResult(salt=salt, iv=result["iv"], ciphertext=result["ciphertext"])


def password_decrypt(password: str, salt_hex: str, iv_hex: str, ciphertext_hex: str) -> bytes:
    aes_key = pbkdf2_derive(password, salt_hex)
    return aes_decrypt(aes_key, iv_hex, ciphertext_hex)
