from fastapi import APIRouter, Depends, Request

from app.api.v1.deps import get_current_user
from app.models.schemas import SettingsResponse, SettingsUpdate
from app.services import auth as auth_service


router = APIRouter()


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return auth_service.get_settings(
        user_id=current_user["id"],
        mcp_base_url=_base_url(request),
    )


@router.patch("/settings", response_model=SettingsResponse)
async def update_settings(
    request_body: SettingsUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return auth_service.update_settings(
        user_id=current_user["id"],
        mcp_base_url=_base_url(request),
        mcp_enabled=request_body.mcp_enabled,
        mcp_read_enabled=request_body.mcp_read_enabled,
        mcp_write_enabled=request_body.mcp_write_enabled,
    )
