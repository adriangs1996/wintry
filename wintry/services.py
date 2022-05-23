from logging import Logger
import logging
from wintry.ioc import provider
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase

DatabaseConnection = AsyncSession | AsyncIOMotorDatabase


@provider(of=Logger)
def get_logger():
    return logging.getLogger("logger")


@provider(of=DatabaseConnection) #type: ignore
def get_database_connection():
    from wintry import get_connection

    return get_connection()
