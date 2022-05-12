from wintry.transactions import UnitOfWork as WintryUnitOfWork
from wintry.dependency_injection import provider
from .repositories import AllocationViewModelRepository, ProductRepository


@provider
class UnitOfWork(WintryUnitOfWork):
    products: ProductRepository
    allocations: AllocationViewModelRepository

    def __init__(
        self, products: ProductRepository, allocations: AllocationViewModelRepository
    ) -> None:
        super().__init__(products=products, allocations=allocations)
