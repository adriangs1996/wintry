from wintry.dependency_injection import provider
from .repositories import AllocationViewModelRepository
from pydantic import BaseModel


class AllocationReadModel(BaseModel, orm_mode=True):
    orderid: str
    sku: str
    batchref: str


@provider
class Views:
    def __init__(self, allocations: AllocationViewModelRepository) -> None:
        self.allocations = allocations

    async def get_allocations_for(self, orderid: str):
        allocations = await self.allocations.find_by_orderid(orderid=orderid)
        return [AllocationReadModel.from_orm(alloc) for alloc in allocations]
