import abc


class DbContext(abc.ABC):
    @abc.abstractmethod
    async def session(self):
        ...

    @abc.abstractmethod
    async def save_changes(self):
        ...
