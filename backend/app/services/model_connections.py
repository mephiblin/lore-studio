from __future__ import annotations

from threading import RLock
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ModelRole, settings
from app.models import ModelConnectionSetting

CONFIGURABLE_ROLES: tuple[ModelRole, ...] = ("writer", "utility", "vision", "embedding")
_lock = RLock()
_overrides: dict[ModelRole, dict[str, object]] = {}


def load_model_connection_overrides(db: Session) -> None:
    rows = db.scalars(select(ModelConnectionSetting)).all()
    with _lock:
        _overrides.clear()
        for row in rows:
            if row.role in CONFIGURABLE_ROLES:
                _overrides[cast(ModelRole, row.role)] = _row_values(row)


def set_model_connection_override(row: ModelConnectionSetting) -> None:
    if row.role not in CONFIGURABLE_ROLES:
        return
    with _lock:
        _overrides[cast(ModelRole, row.role)] = _row_values(row)


def clear_model_connection_override(role: ModelRole) -> None:
    with _lock:
        _overrides.pop(role, None)


def _row_values(row: ModelConnectionSetting) -> dict[str, object]:
    return {
        "role": row.role,
        "base_url": row.base_url,
        "api_key": row.api_key,
        "model": row.model,
        "timeout_seconds": row.timeout_seconds,
        "context_budget": row.context_budget,
        "disable_thinking": row.disable_thinking,
    }


def effective_model_profile(role: ModelRole) -> dict[str, object]:
    values = dict(settings.model_profile(role))
    values.setdefault("disable_thinking", False)
    with _lock:
        override = _overrides.get(role)
        if override is not None:
            values.update(override)
    return values


def connection_read_data(role: ModelRole) -> dict[str, Any]:
    values = effective_model_profile(role)
    with _lock:
        source = "database" if role in _overrides else "environment"
    return {
        "role": role,
        "base_url": str(values["base_url"]),
        "model": str(values["model"]),
        "timeout_seconds": int(values["timeout_seconds"]),
        "context_budget": int(values["context_budget"]),
        "disable_thinking": bool(values["disable_thinking"]),
        "api_key_configured": bool(values["api_key"]),
        "source": source,
    }
