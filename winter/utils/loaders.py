from pathlib import Path
from winter.settings import WinterSettings
import importlib


class LoaderError(Exception):
    pass


def autodiscover_modules():
    settings = WinterSettings()

    app_root = Path(settings.app_root)

    if not app_root.is_dir():
        raise LoaderError(f"settings.app_root is not a dir: {app_root}")

    dirs: list[Path] = [app_root]
    while dirs:
        module = dirs.pop(0)
        for sub_module in module.iterdir():
            if sub_module.is_dir():
                dirs.append(sub_module)
            else:
                if ".py" in module.name:
                    try:
                        importlib.import_module(str(module.resolve()))
                    except ModuleNotFoundError as e:
                        raise LoaderError(str(e))
