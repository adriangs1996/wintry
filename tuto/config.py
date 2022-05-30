from wintry.settings import TransporterType

settings = {
    "backends": [
        {
            "name": "default",
            "driver": "wintry.drivers.pg",
            "connection_options": {
                "url": "postgresql+asyncpg://postgres:secret@localhost/tests"
            },
        },
        {
            "name": "mongo",
            "driver": "wintry.drivers.mongo",
            "connection_options": {"url": "mongodb://localhost:27017/?replicaSet=dbrs"},
        },
    ],
    "transporters": [
        {
            "driver": "wintry.transporters.redis",
            "service": "RedisMicroservice",
            "transporter": TransporterType.redis,
            "connection_options": {"url": "redis://localhost"},
        }
    ],
    "modules": ["."],
    "app_path": "tuto.app:api",
    "server_title": "Testing Server API",
    "server_version": "0.0.1",
}
