"""
RazP Security & RBAC Module.
Provides Role-Based Access Control, API Key/Bearer Token validation, Fail-Closed Production Auth,
Bank Webhook HMAC Signature Verification, and Bounded Rate Limiting.
"""

import os
import time
import json
import hmac
import hashlib
from typing import Dict, List, Optional, Set, Tuple
from fastapi import Request, HTTPException, status, Security, Depends
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from core.schemas import UserRole, ActorContext

# Security Schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

# Known insecure/default keys that must be strictly rejected in production
KNOWN_WEAK_KEYS: Set[str] = {
    "razp_op_key_demo",
    "razp_admin_key_demo",
    "razp_audit_key_demo",
    "razp_master_admin_demo"
}

# Default Demo Keys (Allowed ONLY in non-production environments when explicitly enabled)
DEFAULT_DEMO_KEYS: Dict[str, UserRole] = {
    os.getenv("RAZP_KEY_OPERATOR", "razp_op_key_demo"): UserRole.OPERATOR,
    os.getenv("RAZP_KEY_POLICY_ADMIN", "razp_admin_key_demo"): UserRole.POLICY_ADMIN,
    os.getenv("RAZP_KEY_AUDITOR", "razp_audit_key_demo"): UserRole.AUDITOR,
    os.getenv("RAZP_KEY_ADMIN", "razp_master_admin_demo"): UserRole.ADMIN,
}

# Role Hierarchies / Permissions Matrix
ROLE_PERMISSIONS: Dict[UserRole, Set[str]] = {
    UserRole.OPERATOR: {"view_cases", "evaluate_case", "execute_demo"},
    UserRole.POLICY_ADMIN: {"view_cases", "evaluate_case", "view_policy", "update_policy"},
    UserRole.AUDITOR: {"view_cases", "view_ledger", "verify_integrity", "view_policy"},
    UserRole.ADMIN: {
        "view_cases", "evaluate_case", "view_policy", "update_policy",
        "view_ledger", "verify_integrity", "execute_demo", "tamper_test", "restore_ledger", "benchmark_run"
    },
}


def is_production() -> bool:
    env = os.getenv("ENVIRONMENT", "development").lower().strip()
    return env in ("production", "prod")


def allow_demo_keys() -> bool:
    if is_production():
        return False
    return os.getenv("ALLOW_DEMO_KEYS", "true").lower().strip() in ("true", "1", "yes")


def get_configured_keys() -> Dict[str, UserRole]:
    """
    Returns configured API keys and roles.
    FAILS CLOSED: In production or when demo keys are disabled, raises RuntimeError
    if keys are missing, empty, or contain known default demo keys.
    """
    custom_keys_json = os.getenv("RAZP_API_KEYS")
    if custom_keys_json:
        try:
            parsed = json.loads(custom_keys_json)
            if not parsed or not isinstance(parsed, dict):
                if is_production() or not allow_demo_keys():
                    raise RuntimeError("FATAL: RAZP_API_KEYS is empty in production. Failing closed.")
                return DEFAULT_DEMO_KEYS

            # Reject known weak/demo keys in production
            if is_production() or not allow_demo_keys():
                for k in parsed.keys():
                    if k in KNOWN_WEAK_KEYS:
                        raise RuntimeError(
                            f"FATAL: Known demo key '{k}' found in production RAZP_API_KEYS. Refusing startup."
                        )
                    if len(k) < 16:
                        raise RuntimeError(
                            f"FATAL: Insecure key '{k[:4]}...' (length < 16) in production RAZP_API_KEYS."
                        )

            return {k: UserRole(v) for k, v in parsed.items()}
        except json.JSONDecodeError as exc:
            if is_production() or not allow_demo_keys():
                raise RuntimeError(f"FATAL: Invalid JSON in RAZP_API_KEYS: {exc}. Failing closed.")
            pass

    # No custom keys supplied
    if is_production() or not allow_demo_keys():
        raise RuntimeError(
            "FATAL: Production mode active (ENVIRONMENT=production or ALLOW_DEMO_KEYS=false) "
            "but RAZP_API_KEYS is not configured. Startup aborted to fail closed."
        )

    return DEFAULT_DEMO_KEYS


async def get_current_actor(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth)
) -> ActorContext:
    """
    Validates token from X-API-Key or Authorization: Bearer.
    Extracts actor role and request correlation ID.
    Fails closed if authentication is missing, invalid, or using demo keys in production.
    """
    token = None
    if api_key:
        token = api_key.strip()
    elif bearer and bearer.credentials:
        token = bearer.credentials.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials. Provide a valid 'X-API-Key' or 'Authorization: Bearer <key>'.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # In production, immediately reject any known demo key
    if (is_production() or not allow_demo_keys()) and token in KNOWN_WEAK_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Demo credentials are strictly prohibited in production.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    keys = get_configured_keys()
    if token not in keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token or unrecognized API key.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    role = keys[token]
    actor_id = f"actor_{role.value}_{token[:8]}"
    correlation_id = getattr(request.state, "correlation_id", "corr_unknown")

    return ActorContext(
        actor_id=actor_id,
        role=role,
        correlation_id=correlation_id
    )


def require_roles(*allowed_roles: UserRole):
    """
    FastAPI dependency factory enforcing RBAC on endpoints.
    """
    async def role_checker(
        actor: ActorContext = Depends(get_current_actor)
    ) -> ActorContext:
        # Admin has root access to all endpoints
        if actor.role == UserRole.ADMIN or actor.role in allowed_roles:
            return actor

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access forbidden: Actor role '{actor.role.value}' is not authorized. "
                f"Required role(s): {[r.value for r in allowed_roles]}."
            )
        )

    return role_checker


# =============================================================================
# Bank Webhook Authentication (Raw HMAC-SHA256 Verification)
# =============================================================================

def get_bank_webhook_secret() -> str:
    secret = os.getenv("BANK_WEBHOOK_SECRET")
    if not secret:
        if is_production():
            raise RuntimeError("FATAL: BANK_WEBHOOK_SECRET is not configured in production.")
        return "demo_bank_webhook_secret_for_local_testing"
    return secret


async def verify_bank_webhook_signature(request: Request) -> bytes:
    """
    Verifies bank settlement webhook using raw request body HMAC-SHA256 signature.
    Requirements:
      - Raw request body HMAC comparison via hmac.compare_digest.
      - Enforce timestamp freshness (reject stale payloads > 300s clock skew/replay).
      - Signed payload: '{timestamp}.{raw_body_utf8}'.
      - Normal API key callers CANNOT authenticate this route.
    Returns:
      raw_body bytes if valid.
    """
    # 1. Block normal API key or Bearer tokens to prevent caller impersonation
    if request.headers.get("X-API-Key") or request.headers.get("Authorization"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bank webhooks only accept bank HMAC signatures, not API key tokens."
        )

    # 2. Extract signature and timestamp headers
    sig_header = request.headers.get("X-Bank-Signature") or request.headers.get("X-Razorpay-Signature")
    ts_header = request.headers.get("X-Bank-Timestamp")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required 'X-Bank-Signature' header."
        )

    provided_sig = ""
    timestamp_str = ""

    # Support structured 't={timestamp},v1={signature}' or separate header
    if "t=" in sig_header and "v1=" in sig_header:
        parts = {}
        for part in sig_header.split(","):
            kv = part.strip().split("=", 1)
            if len(kv) == 2:
                parts[kv[0]] = kv[1]
        timestamp_str = parts.get("t", "")
        provided_sig = parts.get("v1", "")
    else:
        provided_sig = sig_header.strip()
        timestamp_str = (ts_header or "").strip()

    if not timestamp_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing bank webhook signature timestamp (provide 'X-Bank-Timestamp' or 't=' in signature)."
        )

    # 3. Reject stale timestamps (replay protection window: 300 seconds)
    try:
        ts_val = float(timestamp_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed timestamp in bank webhook signature."
        )

    now = time.time()
    if abs(now - ts_val) > 300.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank webhook signature timestamp expired or outside replay tolerance window (300s)."
        )

    # 4. Read raw body and verify HMAC
    raw_body = await request.body()
    secret = get_bank_webhook_secret()
    payload_to_sign = f"{timestamp_str}.".encode("utf-8") + raw_body
    computed_sig = hmac.new(secret.encode("utf-8"), payload_to_sign, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_sig, provided_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bank webhook HMAC signature."
        )

    return raw_body


# =============================================================================
# In-Memory Sliding Window Rate Limiter with Bounded Eviction
# =============================================================================

class RateLimiter:
    """
    In-memory rate limiter per IP / token with sliding window and bounded eviction
    to prevent memory exhaustion from tracking unbounded IPs over time.
    """
    def __init__(self, requests_per_minute: int = 60, max_tracked_buckets: int = 5000):
        self.limit = requests_per_minute
        self.window = 60.0  # seconds
        self.max_buckets = max_tracked_buckets
        self._history: Dict[str, List[float]] = {}

    def check_rate_limit(self, request: Request, key_prefix: str = "default") -> None:
        client_ip = request.client.host if request.client else "unknown"
        token = request.headers.get("X-API-Key") or request.headers.get("Authorization") or client_ip
        bucket_key = f"{key_prefix}:{token}"

        now = time.time()

        # Bounded cleanup if tracking exceeds maximum threshold
        if len(self._history) > self.max_buckets:
            expired_keys = [k for k, ts in self._history.items() if not ts or (now - ts[-1] > self.window)]
            for k in expired_keys:
                self._history.pop(k, None)
            # If still over threshold, prune oldest 20%
            if len(self._history) > self.max_buckets:
                sorted_keys = sorted(self._history.keys(), key=lambda k: self._history[k][-1] if self._history[k] else 0)
                for k in sorted_keys[:len(sorted_keys) // 5]:
                    self._history.pop(k, None)

        timestamps = self._history.get(bucket_key, [])
        # Prune older than window
        timestamps = [t for t in timestamps if now - t < self.window]

        if len(timestamps) >= self.limit:
            retry_after = int(self.window - (now - timestamps[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for endpoint. Max {self.limit} requests per minute. Retry after {retry_after}s.",
                headers={"Retry-After": str(retry_after)}
            )

        timestamps.append(now)
        self._history[bucket_key] = timestamps


# Rate limiter instances for different sensitivity tiers
eval_rate_limiter = RateLimiter(requests_per_minute=60)
mutation_rate_limiter = RateLimiter(requests_per_minute=20)
benchmark_rate_limiter = RateLimiter(requests_per_minute=10)
