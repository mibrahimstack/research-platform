"""Best-effort Redis cache utilities for read-heavy API responses."""

import hashlib
import json


CORPUS_VERSION_KEY = "research:corpus_version"


def cache_key(namespace: str, payload: dict, version: str = "1") -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"research:{namespace}:v{version}:{digest}"


def get_corpus_version(client) -> str:
    if client is None:
        return "1"
    try:
        return client.get(CORPUS_VERSION_KEY) or "1"
    except Exception:
        return "1"


def get_json(client, key: str):
    if client is None:
        return None
    try:
        cached = client.get(key)
        return json.loads(cached) if cached else None
    except Exception:
        return None


def set_json(client, key: str, value, ttl_seconds: int) -> None:
    if client is None:
        return
    try:
        client.set(key, json.dumps(value), ex=ttl_seconds)
    except Exception:
        # Redis must never turn a cache miss/failure into an API outage.
        pass


def bump_corpus_version(client) -> None:
    if client is None:
        return
    try:
        client.incr(CORPUS_VERSION_KEY)
    except Exception:
        pass
