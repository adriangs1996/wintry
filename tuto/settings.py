from wintry.settings import (
    BackendOptions,
    ConnectionOptions,
    TransporterSettings,
    TransporterType,
    ConnectionOptions,
    WinterSettings
)

settings = WinterSettings(
    backends=[
        BackendOptions(
            name="default",
            driver="wintry.drivers.pg",
            connection_options=ConnectionOptions(
                url="postgresql+asyncpg://postgres:secret@localhost/tests"
            ),
        ),
        BackendOptions(
            name="mongo",
            driver="wintry.drivers.mongo",
            connection_options=ConnectionOptions(
                url="mongodb://localhost:27017/?replicaSet=dbrs"
            ),
        ),
    ],
    transporters=[
        TransporterSettings(
            driver="wintry.transporters.redis",
            service="RedisMicroservice",
            transporter=TransporterType.redis,
            connection_options=ConnectionOptions(url="redis://localhost"),
        )
    ],
    app_root="tuto",
    app_path="tuto.app:api",
    server_title="Testing Server API",
    server_version="0.0.1",
)
