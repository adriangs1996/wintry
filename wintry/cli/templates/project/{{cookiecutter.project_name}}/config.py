settings = {
    # Full Configuration section for Winter Settings.
    "backends": [
        {
            "name": "default",
            "driver": "wintry.drivers.pg",
            "connection_options": {"url": "sqlite+aiosqlite:///sqlite.db"},
        }
    ],
    "auto_discovery_enabled": True,
    "ensure_metadata": True,
    "modules": ["apps"],
    "middlewares": [
        {
            "name": "CORSMiddleware",
            "module": "fastapi.middleware.cors",
            "args": {
                "allow_origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
            },
        }
    ],
    "transporters": [
        # {
        #     "transporter": "Redis",
        #     "driver": "wintry.transporters.redis",
        #     "service": "RedisMicroservice",
        #     "connection_options": {
        #         "url": "redis://localhost"
        #     }
        # }
    ],
    "sever_title": "{{cookiecutter.project_name}}",
    "server_prefix": "",
    "server_version": "0.0.1",
    "include_error_handling": True,
    "host": "0.0.0.0",
    "hot_reload": True,
    "port": 8000,
    "excluded_folders": [],
    "app_path": "server:app",
}
