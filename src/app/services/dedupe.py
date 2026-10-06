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
