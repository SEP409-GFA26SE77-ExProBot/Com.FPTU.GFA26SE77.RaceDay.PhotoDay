"""Exact + near-duplicate helpers. See rule_design/03_duplicate_handling.md."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from PIL import Image

try:
    import imagehash
except ImportError:  # pragma: no cover
    imagehash = None  # type: ignore


@dataclass
class DedupeDecision:
    is_duplicate: bool
    kind: str | None  # exact | near | None
    duplicate_of: str | None
    content_sha256: str
    dhash_hex: str | None
    hamming: int | None


# In-memory index for local/dev. Production: Redis/Postgres keyed by event_id.
_EVENT_SHA: dict[str, dict[str, str]] = {}
_EVENT_DHASH: dict[str, dict[str, str]] = {}


def clear_dedupe(event_id: str | None = None) -> dict[str, int]:
    """Xóa index trùng (dev retest). event_id=None → clear all events."""
    if event_id:
        n_sha = len(_EVENT_SHA.pop(event_id, {}) or {})
        n_dh = len(_EVENT_DHASH.pop(event_id, {}) or {})
        return {"events": 1 if (n_sha or n_dh) else 0, "sha": n_sha, "dhash": n_dh}
    n_events = len(set(_EVENT_SHA) | set(_EVENT_DHASH))
    n_sha = sum(len(v) for v in _EVENT_SHA.values())
    n_dh = sum(len(v) for v in _EVENT_DHASH.values())
    _EVENT_SHA.clear()
    _EVENT_DHASH.clear()
    return {"events": n_events, "sha": n_sha, "dhash": n_dh}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dhash_hex(image: Image.Image) -> str | None:
    if imagehash is None:
        return None
    return str(imagehash.dhash(image))


def hamming_hex(a: str, b: str) -> int:
    return sum(c1 != c2 for c1, c2 in zip(a, b, strict=False)) + abs(len(a) - len(b))


def check_and_register(
    event_id: str,
    photo_id: str,
    data: bytes,
    image: Image.Image,
    *,
    near_dup_hamming_max: int,
    force: bool,
) -> DedupeDecision:
    digest = sha256_bytes(data)
    sha_index = _EVENT_SHA.setdefault(event_id, {})
    if not force and digest in sha_index and sha_index[digest] != photo_id:
        return DedupeDecision(True, "exact", sha_index[digest], digest, None, 0)

    dh = dhash_hex(image)
    if not force and dh is not None:
        dhash_index = _EVENT_DHASH.setdefault(event_id, {})
        for other_photo, other_hash in dhash_index.items():
            if other_photo == photo_id:
                continue
            dist = hamming_hex(dh, other_hash)
            if dist <= near_dup_hamming_max:
                return DedupeDecision(True, "near", other_photo, digest, dh, dist)

    sha_index[digest] = photo_id
    if dh is not None:
        _EVENT_DHASH.setdefault(event_id, {})[photo_id] = dh

    return DedupeDecision(False, None, None, digest, dh, None)
