from wintry import ServerTypes, Winter
from wintry.settings import BackendOptions, ConnectionOptions, EngineType, WinterSettings

settings = WinterSettings(
    backends=[
        BackendOptions(
            connection_options=ConnectionOptions(
                url="mongodb://localhost:27017/?replicaSet=dbrs"
            )
        )
    ],
    app_root="test_app",
    app_path="test_app.main:api",
    server_title="Testing Server API",
    server_version="0.0.1",
    autogenerate_models_metadata_for_engine=EngineType.NoSql,
)

Winter.setup(settings)

api = Winter.factory(settings, server_type=ServerTypes.API)
