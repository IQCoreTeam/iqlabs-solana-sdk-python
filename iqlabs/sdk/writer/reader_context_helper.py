from ...coder import decode_account


def decode_user_state(data: bytes) -> dict | None:
    return decode_account("UserState", data)
