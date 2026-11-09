from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://root:@127.0.0.1:3306/ai_room_decor?charset=utf8mb4"
    test_database_url: str = "mysql+pymysql://root:@127.0.0.1:3306/ai_room_decor_test?charset=utf8mb4"
    jwt_secret_key: str | None = None
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    backend_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    product_storage_dir: str = "storage/products"
    room_storage_dir: str = "storage/rooms"
    max_room_image_mb: int = 10
    vision_provider: str | None = None
    vision_model: str | None = None
    vision_api_key: str | None = None
    gemini_api_key: str | None = None
    vision_api_base_url: str = "https://api.openai.com/v1"
    image_provider: str | None = None
    image_model: str | None = None
    image_api_key: str | None = None
    image_api_base_url: str = "https://api.openai.com/v1"
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    cloudflare_image_timeout_seconds: int = 300
    cloudflare_image_max_retries: int = 3
    qwencloud_api_key: str | None = None
    qwencloud_api_base_url: str = "https://maas.qwencloudapi.com/api/v1"
    qwencloud_image_timeout_seconds: int = 600
    generated_design_storage_dir: str = "storage/generated-room-designs"
    wikimedia_contact: str | None = None
    google_api_key: str | None = None
    google_cse_id: str | None = None
    admin_email: str | None = None
    admin_password: str | None = None
    admin_full_name: str = "Development Admin"
    app_env: str = "development"

    # Database TLS / Cloud settings
    database_ssl_verify: bool = False
    database_ssl_ca: str | None = None

    # Cloudinary & Cloud Storage settings
    storage_backend: str = "local"  # "local" | "cloudinary"
    storage_root_dir: str | None = None
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    cloudinary_folder: str = "ai_room_decor"

    # Reverse proxy & Rate limiting settings
    trusted_proxies: str = "127.0.0.1,localhost"
    rate_limit_enabled: bool = True

    # AI Cloud Quota & Protection settings
    enable_cloud_ai: bool = True
    gemini_daily_user_limit: int = 3
    gemini_daily_system_limit: int = 50
    cloudflare_daily_user_limit: int = 1
    cloudflare_daily_system_limit: int = 10
    ai_in_flight_timeout_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def is_testing(self) -> bool:
        return self.app_env.lower() == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
