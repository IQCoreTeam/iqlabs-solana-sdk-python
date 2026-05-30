from typing import Union

DEFAULT_SESSION_SPEED = "light"

SESSION_SPEED_PROFILES = {
    "light": {"max_rps": 2, "max_concurrency": 5, "max_concurrency_upload": 1},
    "medium": {"max_rps": 50, "max_concurrency": 50, "max_concurrency_upload": 5},
    "heavy": {"max_rps": 100, "max_concurrency": 100, "max_concurrency_upload": 50},
    "extreme": {"max_rps": 250, "max_concurrency": 250, "max_concurrency_upload": 100},
}

# What writer/reader functions accept for the `speed` parameter.
# Either a preset name (str) or a raw override dict of any subset of the
# three dials — missing keys fall back to the DEFAULT_SESSION_SPEED preset.
SessionSpeedOption = Union[str, dict]


def resolve_session_speed(speed: str | None = None) -> str:
    if speed and speed in SESSION_SPEED_PROFILES:
        return speed
    return DEFAULT_SESSION_SPEED


def resolve_session_config(speed: SessionSpeedOption | None = None) -> dict:
    """Resolve any caller `speed` value into a concrete config dict.

    - None / unknown string -> DEFAULT_SESSION_SPEED preset.
    - Known preset string   -> that preset.
    - dict                  -> DEFAULT_SESSION_SPEED preset overlaid with
                               the provided dials.
    Returns a fresh dict (caller may mutate without touching the preset).
    """
    if isinstance(speed, dict):
        return {**SESSION_SPEED_PROFILES[DEFAULT_SESSION_SPEED], **speed}
    return dict(SESSION_SPEED_PROFILES[resolve_session_speed(speed)])
