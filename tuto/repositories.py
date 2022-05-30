from tuto.viewmodels import AllocationsViewModel
from wintry.ioc import provider
from wintry.repository import Repository, query
from models import Product


@provider
class ProductRepository(Repository[Product, str], entity=Product):
    @query
    async def get_by_sku(self, *, sku: str) -> Product | None:
        ...

    @query
    async def get_by_batches__reference(
        self, *, batches__reference: str
    ) -> Product | None:
        ...


@provider
class AllocationViewModelRepository(
    Repository, entity=AllocationsViewModel, for_backend="mongo"
):
    @query
    async def find_by_orderid(self, *, orderid: str) -> list[AllocationsViewModel]:
        ...

    @query
    async def delete_by_orderid_and_sku(self, *, orderid: str, sku: str):
        ...
