import os
import sqlite3
from contextvars import ContextVar

from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk
from langchain_core.tools import tool

from app.common.logger import logger
from app.services import items as item_service
from app.services import image_generation
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.sqlite import SqliteSaver

load_dotenv()

model = init_chat_model(
    model=os.getenv("REMEMBER_ITEM_MODEL", "qwen3.6-35b-a3b"),
    model_provider="openai",
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
os.makedirs(db_dir, exist_ok=True)
connection = sqlite3.connect(
    os.path.join(db_dir, "remember_item_checkpoints.db"),
    check_same_thread=False,
)
# 初始化checkpointer
checkpointer = SqliteSaver(connection)
# 自动建表
checkpointer.setup()

current_user_id: ContextVar[int | None] = ContextVar(
    "current_user_id",
    default=None,
)
current_image_url: ContextVar[str | None] = ContextVar(
    "current_image_url",
    default=None,
)

MEMORY_SUMMARY_TRIGGER_MESSAGES = int(
    os.getenv("REMEMBER_ITEM_MEMORY_TRIGGER_MESSAGES", "10"),
)
MEMORY_SUMMARY_KEEP_MESSAGES = int(
    os.getenv("REMEMBER_ITEM_MEMORY_KEEP_MESSAGES", "9"),
)
memory_middleware = SummarizationMiddleware(
    model=model,
    trigger=("messages", MEMORY_SUMMARY_TRIGGER_MESSAGES),
    keep=("messages", MEMORY_SUMMARY_KEEP_MESSAGES),
)
INTERNAL_SUMMARY_PREFIX = "Here is a summary of the conversation to date:"


def _require_user_id() -> int:
    user_id = current_user_id.get()
    if user_id is None:
        raise RuntimeError("Missing current user")
    return user_id


def _is_user_visible_stream_chunk(metadata: dict | None) -> bool:
    """Only stream the final agent model node, not middleware-internal model calls."""
    node = (metadata or {}).get("langgraph_node")
    return node in (None, "model")


def _is_internal_summary_message(content) -> bool:
    if not isinstance(content, str):
        return False
    return content.startswith(INTERNAL_SUMMARY_PREFIX)


@tool
def search_items(keyword: str = "", limit: int = 10) -> list[dict]:
    """Search saved items by name. Use empty keyword to list recent items."""
    return item_service.list_items(
        user_id=_require_user_id(),
        keyword=keyword or None,
        limit=limit,
    )


@tool
def add_item(name: str, description: str | None = None, image_url: str | None = None) -> dict:
    """Add a new remembered item with required name and optional description/image URL.

    If the user uploaded an image in the current message, use that image URL when
    image_url is not explicitly provided. If no image is available, generate a
    reference image for the item and save that URL when possible.
    """
    user_id = _require_user_id()
    resolved_image_url = image_url or current_image_url.get()
    generated_image = None
    image_generation_error = None
    if not resolved_image_url:
        try:
            generated_image = image_generation.generate_item_image(
                user_id=user_id,
                name=name,
                description=description,
            )
            resolved_image_url = generated_image.url
        except image_generation.ImageGenerationError as exc:
            image_generation_error = str(exc)
            logger.warning(
                "Item image generation skipped: user_id=%s name=%s reason=%s",
                user_id,
                name,
                image_generation_error,
            )

    item = item_service.create_item(
        user_id=user_id,
        name=name,
        description=description,
        image_url=resolved_image_url,
    )
    if generated_image:
        item["image_generated"] = True
        item["image_stored"] = generated_image.stored
    elif image_generation_error:
        item["image_generated"] = False
        item["image_generation_error"] = image_generation_error
    return item


@tool
def generate_item_image(name: str, description: str | None = None) -> dict:
    """Generate a reference image for an item and return a URL.

    Use this before add_item when the user wants to save an item but did not
    upload a picture. The image is copied to OSS for long-term access when OSS is
    configured; otherwise the returned URL may be temporary.
    """
    try:
        generated = image_generation.generate_item_image(
            user_id=_require_user_id(),
            name=name,
            description=description,
        )
    except image_generation.ImageGenerationError as exc:
        return {
            "success": False,
            "image_url": None,
            "error": str(exc),
        }
    return {
        "success": True,
        "image_url": generated.url,
        "stored": generated.stored,
        "temporary_url": generated.temporary_url,
    }


@tool
def update_saved_item(
    item_id: int,
    name: str | None = None,
    description: str | None = None,
    image_url: str | None = None,
    use_current_image: bool = False,
) -> dict:
    """Update an existing remembered item by id.

    Set use_current_image to true when the user wants to attach the image from
    the current message and no explicit image_url was provided.
    """
    item = item_service.update_item(
        user_id=_require_user_id(),
        item_id=item_id,
        name=name,
        description=description,
        image_url=image_url or (current_image_url.get() if use_current_image else None),
    )
    if not item:
        return {"error": "Item not found", "item_id": item_id}
    return item


@tool
def delete_saved_item(item_id: int) -> dict:
    """Delete a remembered item by id."""
    deleted = item_service.delete_item(_require_user_id(), item_id)
    return {"success": deleted, "item_id": item_id}


system_prompt = """
角色设定：
你是 RememberItem 的 AI 记物助手，帮助用户记录、查找和整理自己的物品。

你可以和用户自然对话，也可以调用工具操作物品库：
1. 用户想找某个物品、问“我有没有某东西”“帮我查一下”时，优先调用 search_items。
2. 用户明确说要记住、添加、保存某个物品时，调用 add_item。物品名称必填，描述和图片可选。
3. 如果用户没有上传图片，但你能判断这是在新增物品，例如“我把鼠标放在客厅中”，应先调用 generate_item_image 生成物品参考图，再把返回的 image_url 传给 add_item。即使你没有显式传 image_url，add_item 也会尽量自动生成图片。
4. 用户想修改某个已保存物品时，先确认或查到 item_id，再调用 update_saved_item。
5. 用户想删除物品时，先确认或查到 item_id，再调用 delete_saved_item。
6. 用户上传图片时，如果图片里能看出物品信息，可以结合图片和文字帮助生成名称/描述；如果信息不足，要简短追问。
7. 如果用户一边上传图片一边要求保存物品，例如“保存苹果在冰箱里”并附带冰箱照片，调用 add_item 时应保存这张图片。当前上传图片的 URL 会在用户消息中以“当前上传图片URL”给出；如果你没有显式传 image_url，工具也会自动使用当前图片。

回答风格：
- 用中文回答。
- 工具操作成功后，明确告诉用户已完成，并概括物品名称、描述、图片是否保存。
- 如果使用了 AI 生成图，告诉用户这张图是根据描述生成的参考图。
- 如果 add_item 返回 image_generation_error，说明物品已保存但图片生成失败；不要说“本次未上传”，要把失败原因简短告诉用户。
- 如果查不到，告诉用户没有找到，并建议换关键词或直接新增。
- 不要编造数据库里不存在的物品。
"""

agent = create_agent(
    model = model,
    tools=[
        search_items,
        add_item,
        generate_item_image,
        update_saved_item,
        delete_saved_item,
    ],
    middleware=[memory_middleware],
    checkpointer=checkpointer,
    system_prompt = system_prompt,
)

# 流式对话
async def chat_with_remember_item(
    prompt: str,
    image: str | None,
    thread_id: str,
    user_id: int,
):
    """调用 RememberItem Agent 处理对话和物品操作"""
    logger.info(f"[用户]: {prompt}, image: {image}, thread_id: {thread_id}")
    user_token = current_user_id.set(user_id)
    image_token = current_image_url.set(image.strip() if image else None)
    try:
        # 判断是否有图片，封装不同格式的消息
        if not image or image.strip() == "":
            message = HumanMessage(content=prompt)
        else:
            image_context = (
                f"{prompt}\n\n"
                f"当前上传图片URL：{image}\n"
                "如果用户要求保存或更新物品，并且这张图片与物品位置或物品本身有关，"
                "请把这张图片作为物品图片保存。"
            )
            message = HumanMessage(content=[
                {"type": "image_url", "image_url": {"url": image}},
                {"type": "text", "text": image_context}
            ])

        # 流式调用Agent
        for chunk, metadata in agent.stream(
            {"messages": [message]},
            {"configurable": {"thread_id": thread_id}},
            stream_mode="messages"
        ):
            if (
                isinstance(chunk, AIMessageChunk)
                and chunk.content
                and _is_user_visible_stream_chunk(metadata)
            ):
                yield chunk.content

    except Exception as e:
        logger.error(f"\n[错误]: {str(e)}")
        yield "这次处理失败了，可以换个说法再试一次。"
    finally:
        current_image_url.reset(image_token)
        current_user_id.reset(user_token)

# 清空会话
def clear_messages(thread_id: str):
    """清空会话"""
    logger.info(f"清空历史消息，thread_id: {thread_id}")
    checkpointer.delete_thread(thread_id)

# 查询会话历史
def get_messages(thread_id: str) -> list[dict[str, str]]:
    """获取会话历史"""
    logger.info(f"获取历史消息，thread_id: {thread_id}")

    # 根据 thread_id 查询 checkpoint
    checkpoint = checkpointer.get({"configurable": {"thread_id": thread_id}})

    # 如果不存在，返回空列表
    if not checkpoint:
        return []

    # 安全获取 messages
    channel_values = checkpoint.get("channel_values")
    if not channel_values:
        return []

    messages = channel_values.get("messages", [])
    if not messages:
        return []

    # 转换消息格式
    result = []
    for msg in messages:
        if not msg.content:
            continue
        if _is_internal_summary_message(msg.content):
            continue

        if isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": _message_content_to_text(msg.content)})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": _message_content_to_text(msg.content)})

    return result


def _message_content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif item.get("type") == "image_url":
                image_url = item.get("image_url", {}).get("url", "")
                if image_url:
                    parts.append(f"[图片] {image_url}")
        return "\n".join(part for part in parts if part)
    return str(content)
