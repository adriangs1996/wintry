from .views import AllocationReadModel, Views
from .commands import Allocate, CreateBatch
from wintry.controllers import controller, post, get
from .services import InvalidSku, MessageBus
from wintry.responses import DataResponse
from wintry.errors import NotFoundError


@controller(prefix="", tags=["Products"])
class ProductsController:
    def __init__(self, message_bus: MessageBus, views: Views) -> None:
        self.messagebus = message_bus
        self.views = views

    @post("/add_batch", response_model=DataResponse[str])
    async def add_batch(self, cmd: CreateBatch):
        await self.messagebus.handle(cmd)
        return DataResponse[str](data="Created Batch")

    @post("/allocate", response_model=DataResponse[str])
    async def allocate(self, cmd: Allocate):
        try:
            await self.messagebus.handle(cmd)
            return DataResponse[str](data="Allocated", status_code=202)
        except InvalidSku as e:
            return DataResponse(status_code=400, message=str(e))

    @get("/allocations/{orderid}", response_model=DataResponse[list[AllocationReadModel]])
    async def allocations_view(self, orderid: str):
        results = await self.views.get_allocations_for(orderid)
        if not results:
            raise NotFoundError(f"{orderid}")

        return DataResponse[list[AllocationReadModel]](data=results)
