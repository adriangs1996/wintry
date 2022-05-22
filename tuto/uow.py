from wintry.transactions import UnitOfWork as WintryUnitOfWork
from wintry.ioc import provider
from .repositories import ProductRepository


@provider
class UnitOfWork(WintryUnitOfWork):
    products: ProductRepository

    def __init__(self, products: ProductRepository) -> None:
        super().__init__(products=products)
