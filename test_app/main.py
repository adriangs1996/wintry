from wintry import ServerTypes, Winter
from wintry.settings import WinterSettings

if __name__ == "__main__":
    Winter.serve(
        server_type=ServerTypes.API,
        with_settings=WinterSettings(app_path="test_app.app:api"),
    )
