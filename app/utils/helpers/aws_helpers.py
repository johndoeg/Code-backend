import mimetypes

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app

import uuid
from werkzeug.utils import secure_filename

_ALLOWED_MIME = {
    "image/jpeg", "image/pjpeg", "image/x-png", "image/png",
    "image/gif", "image/bmp", "image/heic", "image/heif",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/download",
}
_MAX_FILE_MB_DEFAULT = 2

def _s3_client():
    cfg = current_app.config
    return boto3.client(
        "s3",
        aws_access_key_id     = cfg["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key = cfg["AWS_SECRET_ACCESS_KEY"],
        region_name           = cfg["REGION_NAME"],
        endpoint_url          = cfg["ENDPOINT_URL"],
        config                = boto3.session.Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )

def _s3_bucket() -> str:
    return current_app.config["AWS_S3_BUCKET"]

def _aws_presign(aws_key: str, file_name: str, expires: int = 3600) -> str | None:
    if not aws_key:
        return None
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": _s3_bucket(),
            "Key": aws_key,
            "ResponseContentDisposition": f'inline; filename="{file_name}"',
        },
        ExpiresIn=expires,
    )

def _aws_presign_bucket(aws_key: str, file_name: str, bucket: str, expires: int = 3600) -> str | None:
    if not aws_key or not bucket:
        return None
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": aws_key,
            "ResponseContentDisposition": f'inline; filename="{file_name}"',
        },
        ExpiresIn=expires,
    )

def _aws_upload(file_bytes: bytes, aws_key: str, content_type: str = "application/octet-stream") -> None:
    _s3_client().put_object(
        Bucket      = _s3_bucket(),
        Key         = aws_key,
        Body        = file_bytes,
        ContentType = content_type,
    )

def _aws_delete(aws_key: str) -> None:
    try:
        _s3_client().delete_object(Bucket=_s3_bucket(), Key=aws_key)
    except (BotoCoreError, ClientError) as exc:
        current_app.logger.warning("S3 delete failed for %s: %s", aws_key, exc)

def _validate_file(file_bytes: bytes, filename: str, max_mb: int = _MAX_FILE_MB_DEFAULT) -> str:
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if mime not in _ALLOWED_MIME:
        return "Invalid uploaded file format."

    if mime != "application/pdf" and max_mb and len(file_bytes) > max_mb * 1024 * 1024:
        return f"File size exceeded maximum allowed file size ({max_mb}MB)."
    return ""

def build_key(prefix: str, applno: str, sub_type: str, filename: str) -> str:
    safe_name = secure_filename(filename) or "file"
    return f"{prefix}/{applno}/{sub_type}/{uuid.uuid4().hex}-{safe_name}"

def upload_fileobj(key: str, file_storage) -> bool:
    from botocore.exceptions import ClientError
    try:
        _s3_client().upload_fileobj(file_storage, _s3_bucket(), key)
        return True
    except ClientError:
        current_app.logger.exception("Failed to upload to S3 — key=%s", key)
        return False

def copy_object(source_key: str, target_key: str, source_bucket: str | None = None) -> bool:
    if not source_key or not target_key:
        return False

    bucket = _s3_bucket()
    try:
        _s3_client().copy_object(
            Bucket=bucket,
            Key=target_key,
            CopySource={"Bucket": source_bucket or bucket, "Key": source_key},
        )
        return True
    except (BotoCoreError, ClientError) as exc:
        current_app.logger.warning("S3 copy failed %s -> %s: %s", source_key, target_key, exc)
        return False

def delete_object(key: str) -> None:
    from botocore.exceptions import ClientError
    if not key:
        return
    try:
        _s3_client().delete_object(Bucket=_s3_bucket(), Key=key)
    except ClientError:
        current_app.logger.exception("Failed to delete S3 object — key=%s", key)