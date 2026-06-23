import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import io
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.receipts import router

app = FastAPI()
app.include_router(router)


@pytest.fixture
def client():
    return TestClient(app)


def test_upload_receipt_success(client):
    """Happy path: valid file upload returns Receipt schema."""
    with patch("backend.app.routers.receipts.supabase_upload") as mock_upload:
        mock_upload.return_value = (
            "https://supabase.co/storage/v1/object/public/"
            "receipts/user123/abc123.pdf"
        )
        response = client.post(
            "/receipts/upload",
            files={"file": ("receipt.pdf", io.BytesIO(b"fake receipt content"), "application/pdf")},
            data={"user_id": "user123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user123"
    assert data["filename"] == "receipt.pdf"
    assert data["content_type"] == "application/pdf"
    assert data["size"] == 20
    assert "id" in data
    assert "storage_path" in data
    assert "url" in data
    assert "created_at" in data
    mock_upload.assert_called_once()


def test_upload_file_too_large_returns_422(client):
    """File over 10MB returns 422 with RECEIPT_001 error code."""
    large_content = b"x" * (10 * 1024 * 1024 + 1)

    response = client.post(
        "/receipts/upload",
        files={"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")},
        data={"user_id": "user123"},
    )

    assert response.status_code == 422
    data = response.json()
    assert data["detail"]["code"] == "RECEIPT_001"


def test_upload_missing_file_returns_422(client):
    """Missing file field returns 422."""
    response = client.post(
        "/receipts/upload",
        data={"user_id": "user123"},
    )

    assert response.status_code == 422


def test_upload_missing_user_id_returns_422(client):
    """Missing user_id field returns 422."""
    response = client.post(
        "/receipts/upload",
        files={"file": ("receipt.pdf", io.BytesIO(b"content"), "application/pdf")},
    )

    assert response.status_code == 422


def test_upload_invalid_user_id_returns_422(client):
    """user_id with path traversal characters returns 422."""
    for bad_id in ["../admin", "user/../etc", "foo\\bar", "user..name"]:
        response = client.post(
            "/receipts/upload",
            files={"file": ("receipt.pdf", io.BytesIO(b"content"), "application/pdf")},
            data={"user_id": bad_id},
        )
        assert response.status_code == 422, f"Expected 422 for user_id={bad_id!r}"
        assert response.json()["detail"]["code"] == "RECEIPT_002"


def test_upload_supabase_failure_returns_502(client):
    """Supabase upload failure returns 502 with error message."""
    with patch("backend.app.routers.receipts.supabase_upload") as mock_upload:
        mock_upload.side_effect = Exception("Storage error")
        response = client.post(
            "/receipts/upload",
            files={"file": ("receipt.pdf", io.BytesIO(b"content"), "application/pdf")},
            data={"user_id": "user123"},
        )

    assert response.status_code == 502
    assert "Storage error" in response.json()["detail"]
