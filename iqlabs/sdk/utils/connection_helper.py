import os
from solana.rpc.async_api import AsyncClient

_runtime_rpc_url: str | None = None
_runtime_rpc_provider: str | None = None


def set_rpc_url(url: str) -> None:
    global _runtime_rpc_url
    _runtime_rpc_url = url


def set_rpc_provider(provider: str) -> None:
    global _runtime_rpc_provider
    _runtime_rpc_provider = provider


def _env(key: str) -> str | None:
    value = os.environ.get(key)
    if not value:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def _normalize_provider(value: str | None) -> str | None:
    if not value:
        return None
    trimmed = value.strip().lower()
    if trimmed == "helius":
        return "helius"
    if trimmed in ("standard", "rpc"):
        return "standard"
    return None


def _infer_provider_from_url(url: str) -> str:
    return "helius" if "helius" in url.lower() else "standard"


def detect_connection_settings() -> dict:
    rpc_url = (
        _runtime_rpc_url
        or _env("IQLABS_RPC_ENDPOINT")
        or _env("SOLANA_RPC_ENDPOINT")
        or _env("HELIUS_RPC_URL")
        or _env("SOLANA_RPC")
        or _env("RPC_ENDPOINT")
        or _env("RPC_URL")
        or "https://api.devnet.solana.com"
    )
    return {
        "rpc_url": rpc_url,
        "helius_rpc_url": _env("HELIUS_RPC_URL"),
        "zeroblock_rpc_url": _env("ZEROBLOCK_RPC_URL"),
        "fresh_rpc_url": _env("FRESH_RPC_URL"),
        "recent_rpc_url": _env("RECENT_RPC_URL"),
    }


def get_rpc_url() -> str:
    return detect_connection_settings()["rpc_url"]


def get_rpc_provider() -> str:
    env_provider = (
        _normalize_provider(_env("IQLABS_RPC_PROVIDER"))
        or _normalize_provider(_env("RPC_PROVIDER"))
    )
    return _runtime_rpc_provider or env_provider or _infer_provider_from_url(get_rpc_url())


def choose_rpc_url_for_freshness(label: str) -> str:
    settings = detect_connection_settings()
    if label == "fresh":
        return settings["fresh_rpc_url"] or settings["zeroblock_rpc_url"] or settings["rpc_url"]
    if label == "recent":
        return settings["recent_rpc_url"] or settings["helius_rpc_url"] or settings["rpc_url"]
    return settings["rpc_url"]


def get_connection(commitment: str = "confirmed") -> AsyncClient:
    return AsyncClient(get_rpc_url(), commitment=commitment)


def get_reader_connection(label_or_url: str | None = None, commitment: str = "confirmed") -> AsyncClient:
    if not label_or_url:
        return get_connection(commitment)
    if label_or_url in ("fresh", "recent", "archive"):
        return AsyncClient(choose_rpc_url_for_freshness(label_or_url), commitment=commitment)
    return AsyncClient(label_or_url, commitment=commitment)
