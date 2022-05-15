from wintry.settings import (
    BackendOptions,
    ConnectionOptions,
    TransporterSettings,
    TransporterType,
    WinterSettings,
)
from wintry import ServerTypes, Winter

settings = WinterSettings(
    transporters=[
        TransporterSettings(
            transporter=TransporterType.redis,
            driver="wintry.transporters.pikachu",
            service="Pikachu",
            connection_options=ConnectionOptions(url="redis://localhost/"),
        )
    ],
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
    app_root="tuto",
    app_path="tuto.app:api",
    server_title="Testing Server API",
    server_version="0.0.1",
)

Winter.setup(settings)

api = Winter.factory(server_type=ServerTypes.SUBSCRIBER, settings=settings)
Winter.serve(app=api, server_type=ServerTypes.SUBSCRIBER)
