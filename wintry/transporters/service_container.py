from asyncio import Task
import asyncio
import inspect
from multiprocessing import Process
from wintry.settings import WinterSettings
from wintry.transporters import Microservice


class ServiceContainer:
    services: set[Microservice] = set()
    threads: list[Process] = []
    tasks: list[Task] = []

    def __init__(self, settings: WinterSettings) -> None:
        self.settings = settings
        self.threads = []
        self.tasks = []
        self.services = set()

    def collect_tasks(self):
        pass

    def add_service(self, service: type[Microservice]):
        srvc = service(self.settings)
        srvc.init()
        self.services.add(srvc)

    def start_services(self, loop: asyncio.AbstractEventLoop):
        for service in self.services:
            if inspect.iscoroutinefunction(service.run):
                future = loop.create_task(service.run())
                self.tasks.append(future)
            else:
                process = Process(target=service.run)
                process.start()
                self.threads.append(process)

        self.running_futures = asyncio.gather(*self.tasks)

    def close(self):
        self.running_futures.cancel()

        for process in self.threads:
            if process.is_alive():
                process.terminate()
                process.close()
            else:
                process.close()
        self.threads.clear()
        self.tasks.clear()
