"""Supabase database helpers for Receiptly — user management, usage tracking, document persistence."""

import logging
from datetime import datetime, timezone

import streamlit as st

logger = logging.getLogger(__name__)

# Plan limits: maps plan name -> max extractions per month
PLAN_LIMITS = {
    "free": 10,
    "pro": 100,
    "unlimited": None,  # No limit
}


@st.cache_resource
def get_supabase():
    """Return a cached Supabase client. Returns None if config is missing.

    SECURITY: Uses the service_role key which bypasses Row Level Security.
    This is safe because Streamlit keeps secrets server-side (never sent to the browser).
    NEVER expose this key in a client-side framework (React, Next.js, etc.).
    """
    try:
        from supabase import create_client

        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
        return create_client(url, key)
    except (KeyError, FileNotFoundError):
        logger.warning("Supabase credentials not configured — running without persistence.")
        return None
    except Exception as e:
        logger.error("Failed to initialise Supabase client: %s", e)
        return None


def get_or_create_user(email: str, name: str | None = None, picture: str | None = None) -> dict | None:
    """Upsert a user by email. Returns the user row dict or None on failure."""
    sb = get_supabase()
    if sb is None:
        return None
    try:
        result = (
            sb.table("users")
            .upsert(
                {
                    "email": email,
                    "name": name,
                    "picture_url": picture,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="email",
            )
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("get_or_create_user failed: %s", e)
        return None


def get_monthly_usage(user_id: str) -> int:
    """Return extraction count for the current month. Returns 0 on failure."""
    sb = get_supabase()
    if sb is None:
        return 0
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        result = (
            sb.table("usage")
            .select("count")
            .eq("user_id", user_id)
            .eq("month", month_key)
            .execute()
        )
        if result.data:
            return result.data[0]["count"]
        return 0
    except Exception as e:
        logger.error("get_monthly_usage failed: %s", e)
        return 0


def increment_usage(user_id: str) -> int:
    """Increment monthly usage counter. Returns new count or -1 on failure."""
    sb = get_supabase()
    if sb is None:
        return -1
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        # Try to fetch existing row
        existing = (
            sb.table("usage")
            .select("id, count")
            .eq("user_id", user_id)
            .eq("month", month_key)
            .execute()
        )
        if existing.data:
            row = existing.data[0]
            new_count = row["count"] + 1
            sb.table("usage").update({"count": new_count}).eq("id", row["id"]).execute()
            return new_count
        else:
            sb.table("usage").insert(
                {"user_id": user_id, "month": month_key, "count": 1}
            ).execute()
            return 1
    except Exception as e:
        logger.error("increment_usage failed: %s", e)
        return -1


def check_limit(user_id: str, plan: str = "free") -> tuple[bool, int, int | None]:
    """Check if user is within their plan limit.

    Returns (allowed, current_count, limit).
    limit is None for unlimited plans.
    """
    limit = PLAN_LIMITS.get(plan)
    if limit is None:
        return True, get_monthly_usage(user_id), None
    current = get_monthly_usage(user_id)
    return current < limit, current, limit


def save_document(
    user_id: str,
    file_hash: str,
    filename: str,
    extraction_data: dict,
    confidence: float | None = None,
) -> bool:
    """Save extraction result. Deduplicates on (user_id, file_hash). Returns success."""
    sb = get_supabase()
    if sb is None:
        return False
    try:
        # Strip internal keys before saving
        clean_data = {k: v for k, v in extraction_data.items() if not k.startswith("_")}
        sb.table("documents").upsert(
            {
                "user_id": user_id,
                "file_hash": file_hash,
                "filename": filename,
                "extraction_data": clean_data,
                "confidence": confidence,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="user_id,file_hash",
        ).execute()
        return True
    except Exception as e:
        logger.error("save_document failed: %s", e)
        return False


def load_user_documents(user_id: str) -> list[dict]:
    """Load all documents for a user, ordered by creation date descending."""
    sb = get_supabase()
    if sb is None:
        return []
    try:
        result = (
            sb.table("documents")
            .select("file_hash, filename, extraction_data, confidence, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error("load_user_documents failed: %s", e)
        return []
