from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings

settings = WinterSettings(
    backends=[
        BackendOptions(
            connection_options=ConnectionOptions(
                url="mongodb://localhost:27017/?replicaSet=dbrs"
            )
        )
    ],
    modules=[
        "test_app/controllers",
        "test_app/models",
        "test_app/repositories",
        "test_app/services",
        "test_app/views",
    ],
    app_path="test_app.main:api",
    server_title="Testing Server API",
    server_version="0.0.1",
)
