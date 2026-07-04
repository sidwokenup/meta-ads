"""
FastAPI Dependency Injection

Provides get_collector() — the only way a route should obtain a
CollectorService instance.

FastAPI routes must NEVER:
  - Import AdsPower, CDP, GraphClient, SessionManager, or any token logic
  - Create CollectorService directly
  - Know anything about the browser internals

Routes must ONLY call CollectorService methods.
"""

import os
from typing import Annotated

from fastapi import Depends, Header

from app.services.collector_service import CollectorService

# ---------------------------------------------------------------------------
# Config read from environment (with sane defaults for development)
# ---------------------------------------------------------------------------

_PROFILE_ID: str = os.getenv("ADSPOWER_PROFILE_ID", "k1dvlyr0")
_ACCOUNT_ID: str = os.getenv("FACEBOOK_ACCOUNT_ID", "1559140139101704")
_ADSPOWER_URL: str = os.getenv("ADSPOWER_BASE_URL", "http://local.adspower.net:50325")


def get_collector(
    x_adspower_profile_id: Annotated[str | None, Header(alias="X-AdsPower-Profile-Id")] = None,
    x_ad_account_id: Annotated[str | None, Header(alias="X-Ad-Account-Id")] = None,
) -> CollectorService:
    """
    FastAPI dependency — returns a fresh CollectorService for each request.
    """
    print(f"DEBUG HEADERS: profile={x_adspower_profile_id}, account={x_ad_account_id}")
    profile_id = (x_adspower_profile_id or _PROFILE_ID).strip()
    account_id = (x_ad_account_id or _ACCOUNT_ID).strip()

    return CollectorService(
        profile_id=profile_id,
        ad_account_id=account_id,
        adspower_base_url=_ADSPOWER_URL,
    )


# Annotated shorthand — use in route signatures for cleaner code
Collector = Annotated[CollectorService, Depends(get_collector)]
