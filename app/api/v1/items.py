from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.deps import get_current_user
from app.models.schemas import ItemCreate, ItemResponse, ItemUpdate
from app.services import items as item_service


router = APIRouter()


@router.get("/items", response_model=list[ItemResponse])
async def list_items(
    keyword: str | None = Query(default=None, description="按物品名称模糊搜索"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    return item_service.list_items(
        user_id=current_user["id"],
        keyword=keyword,
        limit=limit,
    )


@router.post(
    "/items",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    request: ItemCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        return item_service.create_item(
            user_id=current_user["id"],
            name=request.name,
            description=request.description,
            image_url=request.image_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    current_user: dict = Depends(get_current_user),
):
    item = item_service.get_item(current_user["id"], item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/items/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    request: ItemUpdate,
    current_user: dict = Depends(get_current_user),
):
    try:
        item = item_service.update_item(
            user_id=current_user["id"],
            item_id=item_id,
            name=request.name,
            description=request.description,
            image_url=request.image_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not item_service.delete_item(current_user["id"], item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return None
