from logging import Logger
import logging
from wintry.dependency_injection import provider


@provider(interface=Logger, as_provider=False)  # type: ignore
def get_logger():
    return logging.getLogger("logger")
