from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import get_current_token, get_current_user
from app.models.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth as auth_service


router = APIRouter()


@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(request: RegisterRequest):
    try:
        return auth_service.register_user(
            username=request.username,
            password=request.password,
            phone=request.phone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    user = auth_service.authenticate_user(
        account=request.account,
        password=request.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid account or password",
        )

    session = auth_service.create_session(user["id"])
    return {**session, "user": user}


@router.get("/auth/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/auth/logout")
async def logout(token: str = Depends(get_current_token)):
    auth_service.delete_session(token)
    return {"success": True}


@router.post("/auth/password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        changed = auth_service.change_password(
            user_id=current_user["id"],
            old_password=request.old_password,
            new_password=request.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not changed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect",
        )
    return {"success": True}
