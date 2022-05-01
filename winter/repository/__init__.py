import abc
from typing import Any
from .base import raw_method, repository
from winter import get_connection
from winter.utils.keys import __winter_backend_identifier_key__


class IRepository(abc.ABC):
    def connection(self) -> Any:
        backend_name = getattr(self, __winter_backend_identifier_key__, "default")
        return get_connection(backend_name)


__all__ = ["raw_method", "repository", "IRepository"]
