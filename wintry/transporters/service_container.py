from asyncio import Task
import asyncio
from wintry.settings import WinterSettings
from wintry.transporters import Microservice


class ServiceContainer:
    services: set[Microservice] = set()
    tasks: list[Task] = []

    def __init__(self, settings: WinterSettings) -> None:
        self.settings = settings
        self.tasks = []
        self.services = set()

    def collect_tasks(self):
        pass

    def add_service(self, service: type[Microservice]):
        srvc = service(self.settings)
        srvc.init()
        self.services.add(srvc)

    def start_services(self):
        for service in self.services:
            future = asyncio.create_task(service.run())
            self.tasks.append(future)

    async def close(self):
        for future in self.tasks:
            if not future.done():
                future.cancel()
        self.tasks.clear()
