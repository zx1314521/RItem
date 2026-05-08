from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.v1.deps import get_current_user
from app.models.schemas import ChatRequest, ChatThreadCreate, ChatThreadResponse
from fastapi.responses import StreamingResponse
from app.agents.app import chat_with_remember_item, get_messages, clear_messages
from app.services import chat_threads


router = APIRouter()


def _scoped_thread_id(user_id: int, thread_id: str) -> str:
    return f"user:{user_id}:{thread_id}"


@router.post("/chat/stream")
async def chat_endpoint(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """流式对话"""
    chat_threads.ensure_thread(
        user_id=current_user["id"],
        thread_id=request.thread_id,
        title=chat_threads.title_from_message(request.message, request.image_url),
    )
    return StreamingResponse(
        chat_with_remember_item(
            request.message,
            request.image_url,
            _scoped_thread_id(current_user["id"], request.thread_id),
            current_user["id"],
        ),
        media_type="text/event-stream"
    )


@router.get("/chat/threads", response_model=list[ChatThreadResponse])
async def list_chat_threads(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """获取当前用户的对话列表"""
    return chat_threads.list_threads(current_user["id"], limit=limit)


@router.post(
    "/chat/threads",
    response_model=ChatThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_chat_thread(
    request: ChatThreadCreate,
    current_user: dict = Depends(get_current_user),
):
    """新建对话"""
    return chat_threads.create_thread(current_user["id"], request.title)


@router.delete("/chat/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_thread(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除对话及其历史"""
    deleted = chat_threads.delete_thread(current_user["id"], thread_id)
    clear_messages(_scoped_thread_id(current_user["id"], thread_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat thread not found")
    return None


@router.get("/chat/messages")
async def get_chat_messages(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取历史消息"""
    messages = get_messages(_scoped_thread_id(current_user["id"], thread_id))
    return {"messages": messages}


@router.delete("/chat/messages")
async def clear_chat_messages(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    """清空历史消息"""
    clear_messages(_scoped_thread_id(current_user["id"], thread_id))
    return {"success": True}
