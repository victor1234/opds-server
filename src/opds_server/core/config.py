from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "OPDS Server"
    package_name: str = "opds-server"
    calibre_library_path: Path = "/books"
    opds_prefix: str = "/opds"
    page_size: Annotated[int, Field(ge=1, le=100)] = 30

    @field_validator("calibre_library_path")
    @classmethod
    def validate_calibre_library_path(cls, value: Path) -> Path:
        """Require an unambiguous path without requiring a mounted library."""
        if not value.is_absolute():
            raise ValueError("CALIBRE_LIBRARY_PATH must be an absolute path")
        return value

    @field_validator("opds_prefix", mode="before")
    @classmethod
    def normalize_opds_prefix(cls, value: object) -> object:
        """Normalize and validate the URL path that mounts the catalog."""
        if not isinstance(value, str):
            return value

        prefix = value.strip()
        if not prefix:
            raise ValueError("OPDS_PREFIX must not be empty")
        if any(character.isspace() for character in prefix):
            raise ValueError("OPDS_PREFIX must not contain whitespace")
        if "?" in prefix or "#" in prefix:
            raise ValueError("OPDS_PREFIX must not contain a query or fragment")
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        if prefix.startswith("//"):
            raise ValueError("OPDS_PREFIX must be an application path")

        return prefix if prefix == "/" else prefix.rstrip("/")

    def opds_path(self, suffix: str = "") -> str:
        """Build an application path beneath the configured OPDS mount."""
        if not suffix:
            return self.opds_prefix
        base = "" if self.opds_prefix == "/" else self.opds_prefix
        return f"{base}/{suffix.lstrip('/')}"


@lru_cache()
def get_config() -> Config:
    return Config()
