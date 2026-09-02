"""
RazP Security & RBAC Module.
Provides Role-Based Access Control, API Key/Bearer Token validation, and Rate Limiting.
"""

import os
import time
import json
from typing import Dict, List, Optional, Set
from fastapi import Request, HTTPException, status, Security, Depends
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from core.schemas import UserRole, ActorContext

# Security Schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

# Default Demo Keys (Configurable via Environment)
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


def get_configured_keys() -> Dict[str, UserRole]:
    custom_keys_json = os.getenv("RAZP_API_KEYS")
    if custom_keys_json:
        try:
            parsed = json.loads(custom_keys_json)
            return {k: UserRole(v) for k, v in parsed.items()}
        except Exception:
            pass
    return DEFAULT_DEMO_KEYS


async def get_current_actor(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth)
) -> ActorContext:
    """
    Validates token from X-API-Key or Authorization: Bearer.
    Extracts actor role and request correlation ID.
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
# In-Memory Sliding Window Rate Limiter
# =============================================================================

class RateLimiter:
    """
    In-memory rate limiter per IP / token with sliding window.
    """
    def __init__(self, requests_per_minute: int = 60):
        self.limit = requests_per_minute
        self.window = 60.0  # seconds
        self._history: Dict[str, List[float]] = {}

    def check_rate_limit(self, request: Request, key_prefix: str = "default") -> None:
        client_ip = request.client.host if request.client else "unknown"
        token = request.headers.get("X-API-Key") or request.headers.get("Authorization") or client_ip
        bucket_key = f"{key_prefix}:{token}"

        now = time.time()
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
