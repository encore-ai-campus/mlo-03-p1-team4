"""기존 환경변수와 backend/.env에서 설정을 읽는다.

사용: DB·인증·이벤트와 앱 구성에서 환경변수 및 경로 설정을 읽는다.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    db_write_url: SecretStr | None = None
    db_read_url: SecretStr | None = None
    mongo_url: SecretStr | None = None
    mongo_db: str = "space_rental_analytics"
    jwt_secret: SecretStr | None = None
    jwt_expire_minutes: int = Field(default=60, ge=1)
    internal_api_key: SecretStr | None = None
    synthetic_api_key: SecretStr | None = None
    log_dir: Path = Path("./logs")
    server_name: str = "api-1"
    cors_origins: str = "http://localhost:5173"
    booking_past_days: int = Field(default=365, ge=0)
    booking_future_days: int = Field(default=365, ge=0)
    today_override: str | None = None

    @field_validator("mongo_db")
    @classmethod
    def migrate_legacy_mongo_db(cls, value: str) -> str:
        # 기존 개발 .env의 MONGO_DB=spacecube가 새 컬렉션으로 잘못 쓰이지 않게 한다.
        return "space_rental_analytics" if value == "spacecube" else value

    @field_validator("db_write_url", "db_read_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        try:
            url = make_url(value.get_secret_value())
            if url.drivername != "mysql+pymysql" or not url.database:
                raise ValueError
        except Exception:
            # 파싱 오류 원문에는 비밀번호가 포함될 수 있다.
            raise ValueError(
                "DB 주소는 DB 이름을 포함한 mysql+pymysql 형식이어야 합니다."
            ) from None
        return value

    @field_validator("today_override")
    @classmethod
    def validate_override(cls, value: str | None) -> str | None:
        from datetime import date

        if value is not None:
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except ValueError:
                raise ValueError("TODAY_OVERRIDE는 YYYY-MM-DD 형식이어야 합니다.") from None
        return value

    @field_validator("server_name")
    @classmethod
    def validate_server_name(cls, value: str) -> str:
        if (
            not value
            or len(value) > 64
            or not all(
                character.isascii() and (character.isalnum() or character in "-_.")
                for character in value
            )
        ):
            raise ValueError("서버 이름에는 영문·숫자·하이픈·밑줄·점만 사용합니다.")
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def log_path(self) -> Path:
        return self.log_dir if self.log_dir.is_absolute() else BACKEND_DIR / self.log_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()
