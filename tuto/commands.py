from datetime import date
from wintry.mqs import Command


class Allocate(Command):
    orderid: str
    sku: str
    qty: int


class CreateBatch(Command):
    ref: str
    sku: str
    qty: int
    eta: date | None = None


class ChangeBatchQuantity(Command):
    ref: str
    qty: int
