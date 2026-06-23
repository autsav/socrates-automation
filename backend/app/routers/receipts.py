import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.schemas import Receipt
from backend.app.supabase_client import upload_to_storage as supabase_upload

router = APIRouter(prefix="/receipts", tags=["receipts"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
BUCKET_NAME = os.environ.get("SUPABASE_STORAGE_BUCKET", "receipts")

# Allowed characters in user_id — alphanumeric, hyphens, underscores, dots, colons
_VALID_USER_ID_RE = re.compile(r"^[a-zA-Z0-9._:-]+$")


def _validate_user_id(user_id: str) -> str:
    """Reject user_ids that could cause path traversal."""
    if not _VALID_USER_ID_RE.match(user_id):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "RECEIPT_002",
                "message": "user_id contains invalid characters",
            },
        )
    if ".." in user_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "RECEIPT_002",
                "message": "user_id must not contain '..'",
            },
        )
    return user_id


@router.post("/upload", response_model=Receipt)
async def upload_receipt(
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    """Upload a receipt file to Supabase Storage.

    Validates file size <10MB, stores at receipts/{user_id}/{uuid}.{ext},
    and returns the saved Receipt metadata.
    """
    # Validate user_id before any processing
    _validate_user_id(user_id)

    file_data = await file.read()

    # Validate file size
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=422,
            detail={"code": "RECEIPT_001", "message": "File size exceeds 10MB limit"},
        )

    # Generate storage path
    file_ext = Path(file.filename or "unknown").suffix or ".bin"
    file_uuid = str(uuid.uuid4())
    storage_path = f"receipts/{user_id}/{file_uuid}{file_ext}"

    # Upload to Supabase
    try:
        url = supabase_upload(
            bucket=BUCKET_NAME,
            path=storage_path,
            file_data=file_data,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to upload file to storage: {str(e)}",
        )

    return Receipt(
        id=file_uuid,
        user_id=user_id,
        filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        size=len(file_data),
        storage_path=storage_path,
        url=url,
        created_at=datetime.now(timezone.utc),
    )
