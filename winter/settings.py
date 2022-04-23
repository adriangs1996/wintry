import json
from pathlib import Path
from typing import Any, Dict, Optional
import pydantic as pdc


def json_config_settings_source(settings: pdc.BaseSettings) -> Dict[str, Any]:
    """
    A simple settings source that loads variables from a JSON file
    at the project's root.

    Here we happen to choose to use the `env_file_encoding` from Config
    when reading `config.json`
    """
    encoding = settings.__config__.env_file_encoding
    try:
        return json.loads(Path("config.json").read_text(encoding))
    except FileNotFoundError:
        return {}


class ConnectionOptions(pdc.BaseSettings):
    url: str | None = None
    host: str = "localhost"
    port: int = 27017
    database_name: str = "tests"
    user: Optional[str] = None
    password: Optional[str] = None
    connector: str | None = "postgresql+asyncpg"


class WinterSettings(pdc.BaseSettings):
    backend: str = "winter.drivers"
    connection_options: ConnectionOptions = ConnectionOptions()

    class Config:
        env_file_encoding = "utf-8"

        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            return (
                init_settings,
                json_config_settings_source,
                env_settings,
                file_secret_settings,
            )
