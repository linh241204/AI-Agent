import os
import pytest
from unittest.mock import patch, MagicMock

# ✅ Sửa tên module từ main → app
from app import (
    save_posts,
    load_posts,
    generate_caption,
    upload_image_to_cloudinary,
    upload_image_to_gdrive,
)

TEST_FILE = "test_posts.json"

# ==== UT1: Test lưu & đọc file JSON ====
def test_save_and_load_posts():
    test_data = [{"id": "001", "caption": "Test bài viết"}]
    save_posts(test_data, filename=TEST_FILE)

    assert os.path.exists(TEST_FILE), "❌ File không tồn tại sau khi lưu"

    loaded = load_posts(filename=TEST_FILE)
    assert loaded == test_data, "❌ Dữ liệu đọc không khớp"

    os.remove(TEST_FILE)

# ==== UT2: Test generate_caption (mock GPT) ====
@patch("app.client.chat.completions.create")
def test_generate_caption(mock_gpt):
    mock_gpt.return_value.choices = [
        MagicMock(message=MagicMock(content="Đây là caption mẫu #xuongbinhgom"))
    ]

    result = generate_caption("Bình hoa", "gốm", "Facebook")
    assert "#xuongbinhgom" in result
    assert "caption" in result.lower() or "bài viết" in result.lower()

# ==== UT3: Test upload_image_to_cloudinary (mock) ====
@patch("app.cloudinary.uploader.upload")
def test_upload_image_to_cloudinary(mock_upload):
    mock_upload.return_value = {"secure_url": "https://fake.cloudinary.com/image.jpg"}

    image_bytes = b"fake-image"
    url = upload_image_to_cloudinary(image_bytes)

    assert url.startswith("https://fake.cloudinary.com")

# ==== UT4: Test upload_image_to_gdrive (mock) ====
@patch("app.service_account.Credentials.from_service_account_info")
@patch("app.build")
def test_upload_image_to_gdrive(mock_build, mock_creds):
    # Giả lập service Google Drive
    mock_service = MagicMock()
    mock_files = mock_service.files.return_value
    mock_files.create.return_value.execute.return_value = {"id": "fake_id"}
    mock_build.return_value = mock_service

    image_bytes = b"fake-data"
    url = upload_image_to_gdrive(image_bytes, "test.jpg")

    assert url.startswith("https://drive.google.com/uc?id=")
