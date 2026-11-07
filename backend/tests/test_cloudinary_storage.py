import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import UploadFile

from app.core.config import settings
from app.services.storage_service import (
    GeneratedDesignStorageService,
    ProductImageStorageService,
    RoomImageStorageService,
)

# 1x1 transparent PNG bytes
TINY_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"


def test_room_image_local_storage_default(tmp_path: Path):
    with patch.object(settings, "storage_backend", "local"):
        service = RoomImageStorageService(storage_root=str(tmp_path))
        upload = UploadFile(filename="room.png", file=io.BytesIO(TINY_PNG), headers={"content-type": "image/png"})
        stored = service.save(upload, user_id=1, project_id=1)
        assert stored.image_url.startswith("/storage/rooms/1/1/")
        assert (tmp_path / stored.storage_path).is_file()
        resolved = service.resolve(stored.storage_path)
        assert resolved.is_file()


def test_room_image_cloudinary_mock_upload(tmp_path: Path):
    mock_upload_res = {
        "secure_url": "https://res.cloudinary.com/testcloud/image/upload/v12345/ai_room_decor/rooms/1/1/mock.png",
        "url": "http://res.cloudinary.com/testcloud/image/upload/v12345/ai_room_decor/rooms/1/1/mock.png",
    }
    with patch.object(settings, "storage_backend", "cloudinary"), \
         patch.object(settings, "cloudinary_cloud_name", "testcloud"), \
         patch("cloudinary.uploader.upload", return_value=mock_upload_res):

        service = RoomImageStorageService(storage_root=str(tmp_path))
        upload = UploadFile(filename="room.png", file=io.BytesIO(TINY_PNG), headers={"content-type": "image/png"})
        stored = service.save(upload, user_id=1, project_id=1)

        assert stored.image_url == mock_upload_res["secure_url"]
        # Local copy is also retained as cache
        assert (tmp_path / stored.storage_path).is_file()
        # Resolve should return the local file Path
        resolved = service.resolve(stored.storage_path)
        assert resolved.is_file()


def test_generated_design_storage_cloudinary_mock(tmp_path: Path):
    mock_upload_res = {
        "secure_url": "https://res.cloudinary.com/testcloud/image/upload/v12345/ai_room_decor/generated/mock.jpg",
    }
    with patch.object(settings, "storage_backend", "cloudinary"), \
         patch.object(settings, "cloudinary_cloud_name", "testcloud"), \
         patch("cloudinary.uploader.upload", return_value=mock_upload_res):

        service = GeneratedDesignStorageService(storage_root=str(tmp_path))
        stored = service.save(
            data=TINY_PNG,
            content_type="image/png",
            user_id=1,
            project_id=1,
            generation_id=1,
        )
        assert stored.image_url == mock_upload_res["secure_url"]
        assert (tmp_path / stored.storage_path).is_file()
        resolved = service.resolve(stored.storage_path)
        assert resolved.is_file()


def test_product_image_storage_cloudinary_mock(tmp_path: Path):
    mock_upload_res = {
        "secure_url": "https://res.cloudinary.com/testcloud/image/upload/v12345/ai_room_decor/products/chair.png",
    }
    with patch.object(settings, "storage_backend", "cloudinary"), \
         patch.object(settings, "cloudinary_cloud_name", "testcloud"), \
         patch("cloudinary.uploader.upload", return_value=mock_upload_res):

        service = ProductImageStorageService(storage_root=str(tmp_path))
        upload = UploadFile(filename="chair.png", file=io.BytesIO(TINY_PNG), headers={"content-type": "image/png"})
        url = service.save(upload)
        assert url == mock_upload_res["secure_url"]
