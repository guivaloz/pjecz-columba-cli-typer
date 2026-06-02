"""
Config settings
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings"""

    AUDIENCIAS_API_KEY: str = ""
    AUDIENCIAS_PANTALLA_URL: str = ""
    AUDIENCIAS_FECHA_URL: str = ""

    class Config:
        """Config"""

        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get settings"""
    return Settings()
