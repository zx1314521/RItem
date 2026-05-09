import json
import os
import uuid
from dataclasses import dataclass
from urllib import error, request

import alibabacloud_oss_v2 as oss
from dotenv import load_dotenv

from app.common.logger import logger

load_dotenv()

DASHSCOPE_IMAGE_ENDPOINT = os.getenv(
    "DASHSCOPE_IMAGE_ENDPOINT",
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
)
DASHSCOPE_IMAGE_MODEL = os.getenv("DASHSCOPE_IMAGE_MODEL", "qwen-image-2.0-pro")
DASHSCOPE_IMAGE_SIZE = os.getenv("DASHSCOPE_IMAGE_SIZE", "1024*1024")
MAX_GENERATED_IMAGE_BYTES = int(os.getenv("REMEMBER_ITEM_MAX_GENERATED_IMAGE_BYTES", "20971520"))


@dataclass
class GeneratedImage:
    url: str
    temporary_url: str
    stored: bool


class ImageGenerationError(RuntimeError):
    """Raised when an item reference image cannot be generated."""


def generate_item_image(
    *,
    user_id: int,
    name: str,
    description: str | None = None,
) -> GeneratedImage:
    if os.getenv("REMEMBER_ITEM_GENERATE_IMAGES", "true").lower() == "false":
        raise ImageGenerationError("图片生成功能已关闭")

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ImageGenerationError("DASHSCOPE_API_KEY 未配置，无法调用图片生成模型")

    prompt = _build_item_image_prompt(name, description)
    logger.info(
        "Generating item image: user_id=%s name=%s model=%s",
        user_id,
        name,
        DASHSCOPE_IMAGE_MODEL,
    )
    temporary_url = _call_dashscope_image(api_key, prompt)

    stored_url = _copy_image_to_oss(user_id, temporary_url)
    logger.info(
        "Generated item image: user_id=%s name=%s stored=%s",
        user_id,
        name,
        bool(stored_url),
    )
    return GeneratedImage(
        url=stored_url or temporary_url,
        temporary_url=temporary_url,
        stored=bool(stored_url),
    )


def _build_item_image_prompt(name: str, description: str | None = None) -> str:
    text = f"物品名称：{name.strip()}"
    if description and description.strip():
        text += f"\n位置或描述：{description.strip()}"
    return (
        "生成一张用于物品记录卡片的真实照片风格图片。"
        "画面简洁、明亮、主体清楚，表现这个物品以及它所在的位置；"
        "不要生成文字、水印、价格标签或品牌 Logo。"
        f"\n{text}"
    )[:800]


def _call_dashscope_image(api_key: str, prompt: str) -> str:
    payload = {
        "model": DASHSCOPE_IMAGE_MODEL,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ]
        },
        "parameters": {
            "negative_prompt": "低清晰度，模糊，文字，水印，价格标签，品牌 Logo，畸形，过度变形",
            "prompt_extend": True,
            "watermark": False,
            "size": DASHSCOPE_IMAGE_SIZE,
            "n": 1,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        DASHSCOPE_IMAGE_ENDPOINT,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with request.urlopen(http_request, timeout=120) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.error("DashScope image generation failed: status=%s body=%s", exc.code, detail)
        raise ImageGenerationError(f"图片生成接口调用失败：HTTP {exc.code}")
    except Exception as exc:
        logger.error("DashScope image generation failed: %s", exc)
        raise ImageGenerationError(f"图片生成接口调用失败：{exc}")

    try:
        result = json.loads(body)
        contents = result["output"]["choices"][0]["message"]["content"]
        for item in contents:
            image_url = _extract_image_url(item.get("image"))
            if image_url:
                return image_url
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        logger.error("Unexpected DashScope image response: %s body=%s", exc, body)
        raise ImageGenerationError("图片生成接口返回格式异常")
    raise ImageGenerationError("图片生成接口没有返回图片 URL")


def _extract_image_url(value) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        url = value.get("url")
        if isinstance(url, str):
            return url
    return None


def _copy_image_to_oss(user_id: int, image_url: str) -> str | None:
    bucket = os.getenv("OSS_BUCKET")
    if not bucket:
        logger.warning("Skipping generated image OSS copy: OSS_BUCKET is not configured")
        return None

    try:
        with request.urlopen(image_url, timeout=120) as response:
            image_bytes = response.read(MAX_GENERATED_IMAGE_BYTES + 1)
        if len(image_bytes) > MAX_GENERATED_IMAGE_BYTES:
            logger.error("Generated image is too large to store")
            return None
    except Exception as exc:
        logger.error("Failed to download generated image: %s", exc)
        return None

    endpoint = os.getenv("OSS_ENDPOINT", "oss-cn-beijing.aliyuncs.com")
    object_key = f"users/{user_id}/generated/{uuid.uuid4().hex}.png"
    cfg = oss.config.load_default()
    cfg.credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
    cfg.region = os.getenv("OSS_REGION", "cn-beijing")
    client = oss.Client(cfg)

    try:
        client.put_object(
            oss.PutObjectRequest(
                bucket=bucket,
                key=object_key,
                body=image_bytes,
                content_type="image/png",
            )
        )
    except Exception as exc:
        logger.error("Failed to upload generated image to OSS: %s", exc)
        return None

    return f"https://{bucket}.{endpoint}/{object_key}"
