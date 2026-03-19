from typing import TypedDict

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

from .encoding import bytes_to_hex, validate_pub_key
from .primitives import hkdf_derive, aes_encrypt, aes_decrypt, get_random_bytes


class RecipientEntry(TypedDict):
    recipient_pub: str
    ephemeral_pub: str
    wrapped_key: str
    wrap_iv: str


class MultiEncryptResult(TypedDict):
    recipients: list[RecipientEntry]
    iv: str
    ciphertext: str


MULTI_HKDF_SALT = "iq-sdk-multi-dh-v1"
MULTI_HKDF_INFO = "aes-256-gcm-wrap-key"


def multi_encrypt(recipient_pub_hexes: list[str], plaintext: bytes) -> MultiEncryptResult:
    if not recipient_pub_hexes:
        raise ValueError("At least one recipient required")

    unique = list(dict.fromkeys(recipient_pub_hexes))

    cek = get_random_bytes(32)
    encrypted = aes_encrypt(cek, plaintext)

    recipients: list[RecipientEntry] = []
    for recipient_pub_hex in unique:
        recipient_pub = validate_pub_key(recipient_pub_hex, "recipientPubHex")
        eph_priv = get_random_bytes(32)
        eph_private = X25519PrivateKey.from_private_bytes(eph_priv)
        eph_pub = eph_private.public_key().public_bytes_raw()
        recipient_public = X25519PublicKey.from_public_bytes(recipient_pub)
        shared = eph_private.exchange(recipient_public)
        wrap_key = hkdf_derive(shared, MULTI_HKDF_SALT, MULTI_HKDF_INFO)
        wrapped = aes_encrypt(wrap_key, cek)
        recipients.append(RecipientEntry(
            recipient_pub=recipient_pub_hex,
            ephemeral_pub=bytes_to_hex(eph_pub),
            wrapped_key=wrapped["ciphertext"],
            wrap_iv=wrapped["iv"],
        ))

    return MultiEncryptResult(
        recipients=recipients,
        iv=encrypted["iv"],
        ciphertext=encrypted["ciphertext"],
    )


def multi_decrypt(priv_key: bytes, pub_key_hex: str, encrypted: MultiEncryptResult) -> bytes:
    entry = next((r for r in encrypted["recipients"] if r["recipient_pub"] == pub_key_hex), None)
    if not entry:
        raise ValueError("No matching recipient entry found for this key")

    eph_pub = validate_pub_key(entry["ephemeral_pub"], "ephemeralPub")
    private = X25519PrivateKey.from_private_bytes(priv_key)
    eph_public = X25519PublicKey.from_public_bytes(eph_pub)
    shared = private.exchange(eph_public)
    wrap_key = hkdf_derive(shared, MULTI_HKDF_SALT, MULTI_HKDF_INFO)

    cek = aes_decrypt(wrap_key, entry["wrap_iv"], entry["wrapped_key"])

    return aes_decrypt(cek, encrypted["iv"], encrypted["ciphertext"])
