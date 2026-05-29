DEFAULT_SESSION_SPEED = "light"

SESSION_SPEED_PROFILES = {
    "light": {"max_rps": 2, "max_concurrency": 5, "max_concurrency_upload": 1},
    "medium": {"max_rps": 50, "max_concurrency": 50, "max_concurrency_upload": 5},
    "heavy": {"max_rps": 100, "max_concurrency": 100, "max_concurrency_upload": 50},
    "extreme": {"max_rps": 250, "max_concurrency": 250, "max_concurrency_upload": 100},
}


def resolve_session_speed(speed: str | None = None) -> str:
    if speed and speed in SESSION_SPEED_PROFILES:
        return speed
    return DEFAULT_SESSION_SPEED
