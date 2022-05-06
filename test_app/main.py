from winter import ServerTypes, Winter
from winter.settings import WinterSettings

if __name__ == "__main__":
    Winter.serve(
        server_type=ServerTypes.API,
        with_settings=WinterSettings(app_path="test_app.app:api"),
    )
