from datetime import date
from wintry.models import Array, Model, RequiredId


class OutOfStock(Exception):
    pass


class OrderLine(Model):
    sku: str
    qty: int
    orderid: str = RequiredId()


class Batch(Model):
    sku: str
    purchased_quantity: int
    reference: str = RequiredId()
    allocations: list[OrderLine] = Array()
    eta: date | None = None

    def allocate(self, line: OrderLine):
        if self.can_allocate(line):
            self.allocations.append(line)

    def deallocate(self, line: OrderLine):
        if line in self.allocations:
            self.allocations.remove(line)

    def deallocate_one(self) -> OrderLine:
        return self.allocations.pop()

    @property
    def allocated_quantity(self) -> int:
        return sum(line.qty for line in self.allocations)

    @property
    def available_quantity(self) -> int:
        return self.purchased_quantity - self.allocated_quantity

    def can_allocate(self, line: OrderLine) -> bool:
        return self.sku == line.sku and self.available_quantity >= line.qty

    def __gt__(self, other):
        if self.eta is None:
            return False
        if other.eta is None:
            return True
        return self.eta > other.eta


class Product(Model):  # (1)
    sku: str = RequiredId()  # (2)
    batches: list[Batch] = Array()

    def allocate(self, line: OrderLine) -> str | None:
        try:
            batch = next(b for b in sorted(self.batches) if b.can_allocate(line))
            batch.allocate(line)
            return batch.reference
        except StopIteration:
            return None

    def change_batch_quantity(self, ref: str, qty: int):
        batch = next(b for b in self.batches if b.reference == ref)
        batch.purchased_quantity = qty
        while batch.available_quantity < 0:
            line = batch.deallocate_one()
            yield line
