"""Password hashing with salted PBKDF2-HMAC-SHA256 (Python standard library).

New hashes are stored as   pbkdf2_sha256$<iterations>$<salt>$<hex digest>
The seeded accounts use    pbkdf2_sha256$<salt>$<hex digest>   (no iteration count), which is
checked with LEGACY_ITERATIONS (120,000, confirmed against the Test User account).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000  # OWASP's 2023+ recommendation for PBKDF2-HMAC-SHA256
LEGACY_ITERATIONS = int(os.getenv("LEGACY_PBKDF2_ITERATIONS", "120000"))


def _digest(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    return f"{ALGORITHM}${ITERATIONS}${salt}${_digest(password, salt, ITERATIONS)}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if parts[0] != ALGORITHM:
        return False
    if len(parts) == 4:
        _, iterations, salt, expected = parts
        iterations = int(iterations)
    elif len(parts) == 3:
        _, salt, expected = parts
        iterations = LEGACY_ITERATIONS
    else:
        return False
    return hmac.compare_digest(_digest(password, salt, iterations), expected)


# Checked against when the email doesn't exist, so a wrong email takes as long as a wrong password.
DUMMY_HASH = hash_password(secrets.token_hex(16))
