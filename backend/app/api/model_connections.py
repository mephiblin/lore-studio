from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import ModelRole
from app.db import get_db
from app.model_connection_schemas import (
    ModelConnectionRead,
    ModelConnectionRole,
    ModelConnectionTest,
    ModelConnectionTestRead,
    ModelConnectionUpdate,
)
from app.models import AuditLog, ModelConnectionSetting, new_id
from app.services.model_connections import (
    CONFIGURABLE_ROLES,
    clear_model_connection_override,
    connection_read_data,
    effective_model_profile,
    set_model_connection_override,
)
from app.services.model_gateway import ModelGateway, ModelProfile

router = APIRouter(tags=["model-connections"])
gateway = ModelGateway()


def _role(value: ModelConnectionRole) -> ModelRole:
    return value


def _profile(payload: ModelConnectionUpdate, role: ModelRole) -> ModelProfile:
    current = effective_model_profile(role)
    if payload.clear_api_key:
        api_key = ""
    elif payload.api_key is None:
        api_key = str(current["api_key"])
    else:
        api_key = payload.api_key
    return ModelProfile(
        role=role,
        base_url=payload.base_url,
        api_key=api_key,
        model=payload.model,
        timeout_seconds=payload.timeout_seconds,
        context_budget=payload.context_budget,
        disable_thinking=payload.disable_thinking,
    )


def _safe_snapshot(role: ModelRole) -> dict[str, object]:
    return connection_read_data(role)


@router.get("/model-connections", response_model=list[ModelConnectionRead])
def list_model_connections() -> list[dict[str, object]]:
    return [connection_read_data(role) for role in CONFIGURABLE_ROLES]


@router.post("/model-connections/test", response_model=ModelConnectionTestRead)
async def test_model_connection(payload: ModelConnectionTest) -> dict[str, object]:
    profile = _profile(payload, _role(payload.role))
    return await gateway.health_profile(profile)


@router.patch("/model-connections/{role}", response_model=ModelConnectionRead)
async def update_model_connection(
    role: ModelConnectionRole,
    payload: ModelConnectionUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    model_role = _role(role)
    profile = _profile(payload, model_role)
    health = await gateway.health_profile(profile)
    if not health["available"]:
        error = health.get("error") or {"code": "MODEL_HEALTH_FAILED", "message": "모델 연결 실패"}
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)

    before = _safe_snapshot(model_role)
    row = db.get(ModelConnectionSetting, role)
    if row is None:
        row = ModelConnectionSetting(
            role=role,
            base_url=profile.base_url,
            api_key=profile.api_key,
            model=profile.model,
            timeout_seconds=profile.timeout_seconds,
            context_budget=profile.context_budget,
            disable_thinking=profile.disable_thinking,
        )
        db.add(row)
    else:
        row.base_url = profile.base_url
        row.model = profile.model
        row.timeout_seconds = profile.timeout_seconds
        row.context_budget = profile.context_budget
        row.disable_thinking = profile.disable_thinking
        if payload.clear_api_key:
            row.api_key = ""
        elif payload.api_key is not None:
            row.api_key = payload.api_key

    db.flush()
    set_model_connection_override(row)
    after = _safe_snapshot(model_role)
    db.add(
        AuditLog(
            id=new_id(),
            project_id=None,
            action="MODEL_CONNECTION_UPDATED",
            entity_type="model_connection",
            entity_id=role,
            before_json=before,
            after_json=after,
            reason="user_settings_save",
        )
    )
    db.commit()
    return after


@router.delete("/model-connections/{role}", response_model=ModelConnectionRead)
def reset_model_connection(
    role: ModelConnectionRole,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    model_role = _role(role)
    before = _safe_snapshot(model_role)
    row = db.get(ModelConnectionSetting, role)
    if row is not None:
        db.delete(row)
        db.flush()
    clear_model_connection_override(model_role)
    after = _safe_snapshot(model_role)
    db.add(
        AuditLog(
            id=new_id(),
            project_id=None,
            action="MODEL_CONNECTION_RESET",
            entity_type="model_connection",
            entity_id=role,
            before_json=before,
            after_json=after,
            reason="user_settings_reset",
        )
    )
    db.commit()
    return after
