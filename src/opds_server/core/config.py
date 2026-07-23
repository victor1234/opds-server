from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    app_name: str = "OPDS Server"
    package_name: str = "opds-server"
    calibre_library_path: Path = "/books"
    opds_prefix: str = "/opds"
    page_size: int = 30

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

    def opds_path(self, suffix: str = "", root_path: str = "") -> str:
        """Build an external path beneath the proxy and OPDS mount paths."""
        proxy_path = root_path.rstrip("/")
        catalog_path = "" if self.opds_prefix == "/" else self.opds_prefix
        base = f"{proxy_path}{catalog_path}"
        if not suffix:
            return base or "/"
        return f"{base}/{suffix.lstrip('/')}"


@lru_cache()
def get_config() -> Config:
    return Config()
