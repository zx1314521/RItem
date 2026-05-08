import alibabacloud_oss_v2 as oss
from fastapi import APIRouter, Depends, HTTPException
from datetime import timedelta
import os
# 加载环境变量
from dotenv import load_dotenv

from app.api.v1.deps import get_current_user

load_dotenv()
router = APIRouter()

# 从环境变量中加载凭证信息，用于身份验证
credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()

# 加载SDK的默认配置，并设置凭证提供者
cfg = oss.config.load_default()
cfg.credentials_provider = credentials_provider

# 方式一：只填写Region（推荐）
# 必须指定Region ID，SDK会根据Region自动构造HTTPS访问域名
cfg.region = 'cn-beijing'

# 使用配置好的信息创建OSS客户端
client = oss.Client(cfg)

# OSS 域名配置
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "oss-cn-beijing.aliyuncs.com")
OSS_BUCKET = os.getenv("OSS_BUCKET")


@router.get("/oss/presign")
def presign_upload_url(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    if not OSS_BUCKET:
        raise HTTPException(
            status_code=500,
            detail="OSS_BUCKET is not configured",
        )

    # 根据文件扩展名判断 Content-Type
    content_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    safe_filename = os.path.basename(filename).strip()
    if not safe_filename:
        raise HTTPException(status_code=400, detail="filename is required")

    ext = safe_filename.split(".")[-1].lower() if "." in safe_filename else "jpg"
    content_type = content_type_map.get(ext, "application/octet-stream")
    object_key = f"users/{current_user['id']}/{safe_filename}"

    pre_result = client.presign(oss.PutObjectRequest(
        bucket=OSS_BUCKET,
        key=object_key,
        content_type=content_type,
    ), expires=timedelta(seconds=3600))

    # 返回上传 URL 和可访问的图片路径
    return {
        "uploadUrl": pre_result.url.strip('"'),
        "contentType": content_type,
        "accessUrl": f"https://{OSS_BUCKET}.{OSS_ENDPOINT}/{object_key}"
    }
