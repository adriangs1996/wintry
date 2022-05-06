from winter import ServerTypes, Winter
from winter.settings import BackendOptions, ConnectionOptions, WinterSettings

settings = WinterSettings(
    backends=[
        BackendOptions(
            connection_options=ConnectionOptions(
                url="mongodb://localhost:27017/?replicaSet=dbrs"
            )
        )
    ],
    app_root="test_app",
    server_title="Testing Server API",
    server_version="0.0.1",
)

Winter.setup(settings)

api = Winter.factory(settings, server_type=ServerTypes.API)
