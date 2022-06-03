from logging import Logger
from tuto.publisher import Publisher
from tuto.repositories import AllocationViewModelRepository, ProductRepository
from tuto.viewmodels import AllocationsViewModel
from wintry.mqs import event_handler, command_handler, MessageQueue
from wintry.ioc import provider
from commands import Allocate, ChangeBatchQuantity, CreateBatch
from models import Batch, OrderLine, Product
from events import Allocated, Deallocated, OutOfStock as OutOfStockEvent
from wintry.transactions.transactional import transaction


class InvalidSku(Exception):
    pass


@provider
class MessageBus(MessageQueue):
    products: ProductRepository
    logger: Logger
    sender: Publisher
    allocations: AllocationViewModelRepository

    @command_handler
    @transaction
    async def allocate(self, command: Allocate):
        line = OrderLine.build(command.dict())
        product = await self.products.get_by_sku(sku=line.sku)
        if product is None:
            raise InvalidSku(f"Invalid sku {line.sku}")

        batchref = product.allocate(line)
        if batchref is not None:
            self.register(
                Allocated(
                    orderid=line.orderid,
                    sku=line.sku,
                    qty=line.qty,
                    batchref=batchref,
                )
            )
            self.logger.info(f"Allocated {line}")
        else:
            self.register(OutOfStockEvent(sku=line.sku))

    @command_handler
    @transaction
    async def add_batch(self, command: CreateBatch):
        product = await self.products.get_by_sku(sku=command.sku)
        if product is None:
            product = Product(sku=command.sku)
            product = await self.products.create(entity=product)
        product.batches.append(
            Batch(
                reference=command.ref,
                purchased_quantity=command.qty,
                sku=command.sku,
                eta=command.eta,
            )
        )

        self.logger.info("Created Batch")

    @command_handler
    @transaction
    async def change_batch_quantity(self, cmd: ChangeBatchQuantity):
        product = await self.products.get_by_batches__reference(
            batches__reference=cmd.ref
        )
        assert product is not None
        for line in product.change_batch_quantity(**cmd.dict()):
            self.register(Deallocated(**line.to_dict()))  # type: ignore

    @event_handler
    async def reallocate(self, event: Deallocated):
        product = await self.products.get_by_sku(sku=event.sku)
        self.register(Allocate(**event.dict()))

    @event_handler
    @transaction
    async def save_allocation_view(self, event: Allocated):
        allocation = AllocationsViewModel(**event.dict(exclude={"qty"}))
        allocation = await self.allocations.create(entity=allocation)
        await self.sender.send("line_allocated", allocation.to_dict())
        self.logger.info("Synced Allocation View")

    @event_handler
    async def delete_allocation_view(self, event: Deallocated):
        await self.allocations.delete_by_orderid_and_sku(
            orderid=event.orderid, sku=event.sku
        )
        self.logger.info(
            f"Deallocated orders with: orderid={event.orderid}, sku={event.sku}"
        )
