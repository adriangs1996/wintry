import pydantic as pdc


class ConnectionOptions(pdc.BaseSettings):
    url: str | None = None
    host: str = "localhost"
    port: int = 27017
    database_name: str = "tests"


class WinterSettings(pdc.BaseSettings):
    backend: str = "winter.drivers"
    options: ConnectionOptions = ConnectionOptions()
