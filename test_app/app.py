from wintry import App
from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings

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
)


api = App(settings=settings)
