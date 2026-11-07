import io
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

try:
    import cloudinary
    import cloudinary.uploader
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Local cache directory for remote Cloudinary assets when running on serverless/ephemeral hosts
CACHE_DIR = Path(tempfile.gettempdir()) / "ai_room_decor_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def configure_cloudinary() -> bool:
    if not CLOUDINARY_AVAILABLE or not settings.cloudinary_cloud_name:
        return False
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    return True


def fetch_and_cache_remote_image(url: str) -> Path:
    """Download a remote CDN/Cloudinary image to local temp cache so local AI processors can read it."""
    url_hash = sha256(url.encode("utf-8")).hexdigest()
    ext = ".jpg"
    for e in [".png", ".webp", ".jpg", ".jpeg"]:
        if e in url.lower():
            ext = e
            break
    cached_path = CACHE_DIR / f"{url_hash}{ext}"
    if not cached_path.exists() or cached_path.stat().st_size == 0:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Room-Decor/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(cached_path, "wb") as out:
            shutil.copyfileobj(resp, out)
    return cached_path


@dataclass
class StoredRoomImage:
    image_url: str
    storage_path: str
    original_filename: str
    content_type: str
    size_bytes: int
    checksum: str


@dataclass
class StoredGeneratedDesign:
    image_url: str
    storage_path: str
    content_type: str
    size_bytes: int
    checksum: str


def validate_image_signature(data: bytes, extension: str, content_type: str) -> bool:
    if content_type == "image/png" or extension == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp" or extension == ".webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if content_type == "image/jpeg" or extension in {".jpg", ".jpeg"}:
        return data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")
    return False


class ProductImageStorageService:
    def __init__(self, storage_root: str | None = None) -> None:
        configured_root = storage_root or (
            Path(settings.storage_root_dir) / "products" if settings.storage_root_dir else settings.product_storage_dir
        )
        path = Path(configured_root)
        self.storage_root = path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.use_cloudinary = (
            settings.storage_backend.lower() == "cloudinary"
            and bool(settings.cloudinary_cloud_name)
            and CLOUDINARY_AVAILABLE
        )
        if self.use_cloudinary:
            configure_cloudinary()

    def save(self, file: UploadFile) -> str:
        extension = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
        if extension is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPEG, PNG, or WEBP images are allowed")
        filename = f"{uuid4().hex}{extension}"
        destination = self.storage_root / filename
        data = file.file.read()
        with destination.open("wb") as buffer:
            buffer.write(data)

        if self.use_cloudinary:
            folder = f"{settings.cloudinary_folder}/products"
            upload_res = cloudinary.uploader.upload(
                data,
                folder=folder,
                public_id=Path(filename).stem,
                resource_type="image",
                overwrite=True,
            )
            return upload_res.get("secure_url") or upload_res.get("url") or f"/storage/products/{filename}"

        return f"/storage/products/{filename}"

    def resolve(self, image_url: str) -> Path:
        normalized = (image_url or "").strip()
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return fetch_and_cache_remote_image(normalized)

        prefix = "storage/products/"
        cleaned = normalized.lstrip("/")
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
        if not cleaned:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product image path")
        relative = Path(cleaned)
        if relative.is_absolute() or ".." in relative.parts:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product image path")
        candidate = (self.storage_root / relative).resolve()
        if candidate.is_file():
            return candidate

        # Fallback check under PROJECT_ROOT / storage / products
        alt = (PROJECT_ROOT / "storage" / "products" / relative).resolve()
        if alt.is_file():
            return alt

        if self.storage_root not in candidate.parents and candidate != self.storage_root:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product image path")
        return candidate


class RoomImageStorageService:
    def __init__(self, storage_root: str | None = None, max_size_mb: int | None = None) -> None:
        configured_root = storage_root or (
            Path(settings.storage_root_dir) / "rooms" if settings.storage_root_dir else settings.room_storage_dir
        )
        path = Path(configured_root)
        self.storage_root = path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
        self.max_size_bytes = (max_size_mb or settings.max_room_image_mb) * 1024 * 1024
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.use_cloudinary = (
            settings.storage_backend.lower() == "cloudinary"
            and bool(settings.cloudinary_cloud_name)
            and CLOUDINARY_AVAILABLE
        )
        if self.use_cloudinary:
            configure_cloudinary()

    def resolve(self, storage_path: str) -> Path:
        raw = (storage_path or "").strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            return fetch_and_cache_remote_image(raw)

        candidate = (self.storage_root / raw).resolve()
        if candidate.is_file():
            return candidate

        # Check PROJECT_ROOT / "storage" / "rooms" / raw
        alt = (PROJECT_ROOT / "storage" / "rooms" / raw).resolve()
        if alt.is_file():
            return alt

        # Check PROJECT_ROOT / raw if raw starts with storage/
        if raw.startswith("/storage/") or raw.startswith("storage/"):
            alt2 = (PROJECT_ROOT / raw.lstrip("/")).resolve()
            if alt2.is_file():
                return alt2

        if self.use_cloudinary and settings.cloudinary_cloud_name:
            folder = settings.cloudinary_folder.strip("/")
            clean_stem = Path(raw).stem
            cdn_url = f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}/image/upload/{folder}/rooms/{raw}"
            return fetch_and_cache_remote_image(cdn_url)

        if self.storage_root not in candidate.parents and candidate != self.storage_root:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room image path")
        return candidate

    def save(self, file: UploadFile, user_id: int, project_id: int) -> StoredRoomImage:
        content_type = file.content_type or ""
        expected_extension = ALLOWED_IMAGE_TYPES.get(content_type)
        if expected_extension is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPEG, PNG, or WEBP room images are allowed")

        original_filename = Path(file.filename or "room-image").name
        original_extension = Path(original_filename).suffix.lower()
        if original_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room image extension")
        if original_extension == ".jpeg":
            original_extension = ".jpg"
        if original_extension != expected_extension:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image extension does not match content type")

        data = file.file.read()
        size_bytes = len(data)
        if size_bytes == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room image is empty")
        if size_bytes > self.max_size_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Room image is too large")
        if not validate_image_signature(data, original_extension, content_type):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room image appears to be invalid or corrupt")

        destination_dir = (self.storage_root / str(user_id) / str(project_id)).resolve()
        if self.storage_root not in destination_dir.parents and destination_dir != self.storage_root:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room image path")
        destination_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid4().hex}{expected_extension}"
        destination = destination_dir / filename
        destination.write_bytes(data)
        storage_path = str(Path(str(user_id)) / str(project_id) / filename).replace("\\", "/")

        image_url = f"/storage/rooms/{user_id}/{project_id}/{filename}"
        if self.use_cloudinary:
            folder = f"{settings.cloudinary_folder}/rooms/{user_id}/{project_id}"
            upload_res = cloudinary.uploader.upload(
                data,
                folder=folder,
                public_id=Path(filename).stem,
                resource_type="image",
                overwrite=True,
            )
            image_url = upload_res.get("secure_url") or upload_res.get("url") or image_url

        return StoredRoomImage(
            image_url=image_url,
            storage_path=storage_path,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum=sha256(data).hexdigest(),
        )


class GeneratedDesignStorageService:
    def __init__(self, storage_root: str | None = None) -> None:
        configured_root = storage_root or (
            Path(settings.storage_root_dir) / "generated-room-designs" if settings.storage_root_dir else settings.generated_design_storage_dir
        )
        path = Path(configured_root)
        self.storage_root = path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.use_cloudinary = (
            settings.storage_backend.lower() == "cloudinary"
            and bool(settings.cloudinary_cloud_name)
            and CLOUDINARY_AVAILABLE
        )
        if self.use_cloudinary:
            configure_cloudinary()

    def resolve(self, storage_path: str) -> Path:
        raw = (storage_path or "").strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            return fetch_and_cache_remote_image(raw)

        candidate = (self.storage_root / raw).resolve()
        if candidate.is_file():
            return candidate

        alt = (PROJECT_ROOT / "storage" / "generated-room-designs" / raw).resolve()
        if alt.is_file():
            return alt

        if raw.startswith("/storage/") or raw.startswith("storage/"):
            alt2 = (PROJECT_ROOT / raw.lstrip("/")).resolve()
            if alt2.is_file():
                return alt2

        if self.use_cloudinary and settings.cloudinary_cloud_name:
            folder = settings.cloudinary_folder.strip("/")
            cdn_url = f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}/image/upload/{folder}/generated-room-designs/{raw}"
            return fetch_and_cache_remote_image(cdn_url)

        if self.storage_root not in candidate.parents and candidate != self.storage_root:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid generated image path")
        return candidate

    def save(self, data: bytes, content_type: str, user_id: int, project_id: int, generation_id: int) -> StoredGeneratedDesign:
        extension = ALLOWED_IMAGE_TYPES.get(content_type)
        if extension is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Generated image content type is not supported")
        if not data:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Generated image is empty")

        destination_dir = (self.storage_root / str(user_id) / str(project_id) / str(generation_id)).resolve()
        if self.storage_root not in destination_dir.parents and destination_dir != self.storage_root:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid generated image path")
        destination_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid4().hex}{extension}"
        destination = destination_dir / filename
        destination.write_bytes(data)
        storage_path = str(Path(str(user_id)) / str(project_id) / str(generation_id) / filename).replace("\\", "/")

        image_url = f"/storage/generated-room-designs/{user_id}/{project_id}/{generation_id}/{filename}"
        if self.use_cloudinary:
            folder = f"{settings.cloudinary_folder}/generated-room-designs/{user_id}/{project_id}/{generation_id}"
            upload_res = cloudinary.uploader.upload(
                data,
                folder=folder,
                public_id=Path(filename).stem,
                resource_type="image",
                overwrite=True,
            )
            image_url = upload_res.get("secure_url") or upload_res.get("url") or image_url

        return StoredGeneratedDesign(
            image_url=image_url,
            storage_path=storage_path,
            content_type=content_type,
            size_bytes=len(data),
            checksum=sha256(data).hexdigest(),
        )
