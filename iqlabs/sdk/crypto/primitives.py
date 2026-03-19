import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from .encoding import hex_to_bytes, bytes_to_hex


def get_random_bytes(n: int) -> bytes:
    return os.urandom(n)


def hkdf_derive(ikm: bytes, salt: str, info: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode("utf-8"),
        info=info.encode("utf-8"),
    ).derive(ikm)


def aes_encrypt(key_bytes: bytes, plaintext: bytes) -> dict:
    iv = os.urandom(12)
    aesgcm = AESGCM(key_bytes)
    ct = aesgcm.encrypt(iv, plaintext, None)
    return {"iv": bytes_to_hex(iv), "ciphertext": bytes_to_hex(ct)}


def aes_decrypt(key_bytes: bytes, iv_hex: str, ciphertext_hex: str) -> bytes:
    aesgcm = AESGCM(key_bytes)
    return aesgcm.decrypt(hex_to_bytes(iv_hex), hex_to_bytes(ciphertext_hex), None)


def pbkdf2_derive(password: str, salt_hex: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=hex_to_bytes(salt_hex),
        iterations=250_000,
    )
    return kdf.derive(password.encode("utf-8"))
