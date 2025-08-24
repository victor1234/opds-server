from functools import lru_cache
from pydantic_settings import BaseSettings
from pathlib import Path


class Config(BaseSettings):
    app_name: str = "OPDS Server"
    package_name: str = "opds-server"
    calibre_library_path: Path = "/books"
    opds_prefix: str = "/opds"
    page_size: int = 30


@lru_cache()
def get_config() -> Config:
    return Config()
