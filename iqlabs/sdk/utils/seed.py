import re
from Crypto.Hash import keccak

HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")


def derive_seed_bytes(value: str) -> bytes:
    if HEX_64.match(value):
        return bytes.fromhex(value)
    k = keccak.new(digest_bits=256)
    k.update(value.encode("utf-8"))
    return k.digest()


def derive_dm_seed(user_a: str, user_b: str) -> bytes:
    a, b = (user_a, user_b) if user_a < user_b else (user_b, user_a)
    return derive_seed_bytes(f"{a}:{b}")


def to_seed_bytes(value: bytes | str) -> bytes:
    return derive_seed_bytes(value) if isinstance(value, str) else value
