from pydantic import Field
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List


class Settings(BaseSettings):
    API_KEY: str = Field(..., env="API_KEY")
    ARTICLES: List[int] = Field(..., env="ARTICLES")

    LOG_FILEPATH: str = Field("logs/app_log.log", env="LOG_FILEPATH")
    LOG_ROTATION: int = Field(1, env="LOG_ROTATION")
    LOG_RETENTION: int = Field(30, env="LOG_RETENTION")

    class Config:
        env_file = Path(__file__).parents[1].joinpath("environment/.env")
        env_file_encoding = "utf-8"

settings = Settings()