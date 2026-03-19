from typing import Callable, Awaitable, TypedDict

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

from .encoding import bytes_to_hex, validate_pub_key
from .primitives import hkdf_derive, aes_encrypt, aes_decrypt, get_random_bytes


class DhEncryptResult(TypedDict):
    sender_pub: str
    iv: str
    ciphertext: str


DH_HKDF_SALT = "iq-sdk-dh-aes-v1"
DH_HKDF_INFO = "aes-256-gcm-key"
KEY_DERIVE_SALT = "iq-sdk-x25519-v1"
KEY_DERIVE_INFO = "x25519-private-key"
KEY_DERIVE_MSG = "iq-sdk-derive-encryption-key-v1"


async def derive_x25519_keypair(
    sign_message: Callable[[bytes], Awaitable[bytes]],
) -> dict:
    sig_bytes = await sign_message(KEY_DERIVE_MSG.encode("utf-8"))
    priv_key = hkdf_derive(sig_bytes, KEY_DERIVE_SALT, KEY_DERIVE_INFO)
    private = X25519PrivateKey.from_private_bytes(priv_key)
    pub_key = private.public_key().public_bytes_raw()
    return {"priv_key": priv_key, "pub_key": pub_key}


def dh_encrypt(recipient_pub_hex: str, plaintext: bytes) -> DhEncryptResult:
    recipient_pub = validate_pub_key(recipient_pub_hex, "recipientPubHex")
    sender_priv = get_random_bytes(32)
    sender_private = X25519PrivateKey.from_private_bytes(sender_priv)
    sender_pub = sender_private.public_key().public_bytes_raw()
    recipient_public = X25519PublicKey.from_public_bytes(recipient_pub)
    shared = sender_private.exchange(recipient_public)
    aes_key = hkdf_derive(shared, DH_HKDF_SALT, DH_HKDF_INFO)
    result = aes_encrypt(aes_key, plaintext)
    return DhEncryptResult(
        sender_pub=bytes_to_hex(sender_pub),
        iv=result["iv"],
        ciphertext=result["ciphertext"],
    )


def dh_decrypt(priv_key: bytes, sender_pub_hex: str, iv_hex: str, ciphertext_hex: str) -> bytes:
    sender_pub = validate_pub_key(sender_pub_hex, "senderPubHex")
    private = X25519PrivateKey.from_private_bytes(priv_key)
    sender_public = X25519PublicKey.from_public_bytes(sender_pub)
    shared = private.exchange(sender_public)
    aes_key = hkdf_derive(shared, DH_HKDF_SALT, DH_HKDF_INFO)
    return aes_decrypt(aes_key, iv_hex, ciphertext_hex)
