from logging import Logger
from tuto.viewmodels import AllocationsViewModel
from wintry.settings import TransporterType
from views import AllocationReadModel, Views
from commands import Allocate, ChangeBatchQuantity, CreateBatch
from wintry.controllers import controller, microservice, on, post, get
from services import InvalidSku, MessageBus
from wintry.responses import DataResponse
from wintry.errors import NotFoundError
from fastapi import BackgroundTasks


@controller(prefix="", tags=["Products"])
class ProductsController:
    messagebus: MessageBus
    views: Views

    @post("/add_batch", response_model=DataResponse[str])
    async def add_batch(self, cmd: CreateBatch, background_tasks: BackgroundTasks):
        await self.messagebus.handle(cmd, background_tasks)
        return DataResponse[str](data="Created Batch")

    @post("/allocate", response_model=DataResponse[str])
    async def allocate(self, cmd: Allocate, background_tasks: BackgroundTasks):
        try:
            await self.messagebus.handle(cmd, background_tasks)
            return DataResponse[str](data="Allocated", status_code=202)
        except InvalidSku as e:
            return DataResponse(status_code=400, message=str(e))

    @get("/allocations/{orderid}", response_model=DataResponse[list[AllocationReadModel]])
    async def allocations_view(self, orderid: str):
        results = await self.views.get_allocations_for(orderid)
        if not results:
            raise NotFoundError(f"{orderid}")

        return DataResponse(data=results)


@microservice(TransporterType.redis)
class RedisMessagesControllers:
    logger: Logger
    messagebus: MessageBus

    @on("change_batch_quantity")
    async def change_batch_quantity(self, cmd: ChangeBatchQuantity):
        self.logger.info(f"Event from Redis: {cmd}")
        await self.messagebus.handle(cmd)

    @on("line_allocated")
    async def line_allocated(self, allocation: AllocationsViewModel):
        self.logger.info(f"Hey look, a line've been allocated from redis: {allocation}")
