from logging import Logger
import logging
from wintry.ioc import provider

@provider(of=Logger)
def get_logger():
    return logging.getLogger("logger")