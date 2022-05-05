import json
from pathlib import Path
from typing import Any, Dict, Optional
from unicodedata import name
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


class ConnectionOptions(pdc.BaseModel):
    url: str | None = None
    host: str = "localhost"
    port: int = 27017
    database_name: str = "tests"
    user: Optional[str] = None
    password: Optional[str] = None
    connector: str | None = "postgresql+asyncpg"


class Middleware(pdc.BaseModel):
    module: str
    name: str
    args: dict[str, Any]


class BackendOptions(pdc.BaseModel):
    name: str = "default"
    """
    Name that under which the driver is going to be registerd. This has to
    be unique among drivers. 
    """

    driver: str = "winter.drivers.mongo"
    """
    Absolute path to driver's module. This module must contain a top level
    :func:`factory(settings: BackendOptions)` which is called to get an instance
    of the driver.
    """
    connection_options: ConnectionOptions = ConnectionOptions()
    """
    A handy way to define connection options to the driver.
    Most likely, just the url is enough.
    """


class WinterSettings(pdc.BaseSettings):

    backends: list[BackendOptions] = [BackendOptions()]
    """
    List of configurations for the different drivers the app can use.
    Defaults to a MongoEngine on localhost, port 27017 under name 'default'.
    """

    auto_discovery_enabled: bool = True
    """
    Configure if `Winter` should autodiscover modules on setup.
    This is useful for not having to import controllers, models,
    repositories, etc
    """

    app_root: str = "."
    """
    The root of the server implementation. This is not like a wwwroot
    in .NET, is a config param for auto_discovery tool and for app
    to know where it is located. Should be a relative path
    """

    middlewares: list[Middleware] = [
        Middleware(
            name="CORSMiddleware",
            module="fastapi.middleware.cors",
            args={
                "allow_origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
            },
        )
    ]
    """
    List of middlewares to use in the application. Middlewares should
    conform to FastAPI, as them would be constructed and added directly
    to FastAPI instnace.
    """

    server_prefix: str = ""

    server_title: str = ""

    server_version: str = "0.1.0"

    include_error_handling: bool = True

    class Config:
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"

        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):  # type: ignore
            return (
                init_settings,
                json_config_settings_source,
                env_settings,
                file_secret_settings,
            )
