import re

_HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")


def hex_to_bytes(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str)


def bytes_to_hex(data: bytes) -> str:
    return data.hex()


def validate_pub_key(hex_str: str, label: str) -> bytes:
    if not _HEX_64.match(hex_str):
        raise ValueError(f"{label}: must be 64 hex chars (32 bytes), got {len(hex_str)}")
    raw = bytes.fromhex(hex_str)
    if all(b == 0 for b in raw):
        raise ValueError(f"{label}: zero key is not valid")
    return raw
