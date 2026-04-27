"""Verify Slack request signatures."""

import hashlib
import hmac
import time


def verify_slack_signature(
    *,
    signing_secret: str,
    request_body: bytes,
    timestamp: str,
    signature: str,
    tolerance_seconds: int = 60 * 5,
) -> bool:
    """Returns True iff the signature is valid and the request is fresh."""
    try:
        ts_int = int(timestamp)
    except (TypeError, ValueError):
        return False

    # Reject replays older than 5 minutes
    if abs(time.time() - ts_int) > tolerance_seconds:
        return False

    basestring = f"v0:{timestamp}:".encode() + request_body
    expected = (
        "v0="
        + hmac.new(
            signing_secret.encode(), basestring, hashlib.sha256
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature)