from logging import Logger
import logging
from wintry.ioc import provider
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase

from wintry.settings import WinterSettings

DatabaseConnection = AsyncSession | AsyncIOMotorDatabase


@provider(of=Logger)
def get_logger():
    return logging.getLogger("logger")


@provider(of=WinterSettings)
def settings():
    return WinterSettings()
