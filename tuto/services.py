from logging import Logger
from tuto.repositories import AllocationViewModelRepository
from tuto.viewmodels import AllocationsViewModel
from wintry.mqs import event_handler, command_handler, MessageQueue
from wintry.dependency_injection import provider
from .uow import UnitOfWork
from .commands import Allocate, ChangeBatchQuantity, CreateBatch
from .models import Batch, OrderLine, Product
from .events import Allocated, Deallocated, OutOfStock as OutOfStockEvent


class InvalidSku(Exception):
    pass


@provider
class MessageBus(MessageQueue):
    uow: UnitOfWork

    def __init__(
        self, uow: UnitOfWork, logger: Logger, allocations: AllocationViewModelRepository
    ) -> None:
        super().__init__()
        self.uow = uow
        self.allocations = allocations
        self.logger = logger

    @command_handler
    async def allocate(self, command: Allocate):
        line = OrderLine.build(command.dict())

        async with self.uow as uow:
            product = await uow.products.get_by_sku(sku=line.sku)
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

            await uow.commit()

    @command_handler
    async def add_batch(self, command: CreateBatch):
        async with self.uow as uow:
            product = await uow.products.get_by_sku(sku=command.sku)
            if product is None:
                product = Product(command.sku)
                product = await uow.products.create(entity=product)
            product.batches.append(
                Batch(
                    reference=command.ref,
                    purchased_quantity=command.qty,
                    sku=command.sku,
                    eta=command.eta,
                )
            )
            await uow.commit()

        self.logger.info("Created Batch")

    @command_handler
    async def change_batch_quantity(self, cmd: ChangeBatchQuantity):
        async with self.uow as uow:
            product = await uow.products.get_by_batches__reference(
                batches__reference=cmd.ref
            )
            assert product is not None
            for line in product.change_batch_quantity(**cmd.dict()):
                self.register(Deallocated(**line.to_dict()))
            await uow.commit()

    @event_handler
    async def reallocate(self, event: Deallocated):
        async with self.uow as uow:
            product = await uow.products.get_by_sku(sku=event.sku)
            self.register(Allocate(**event.dict()))
            await uow.commit()

    @event_handler
    async def save_allocation_view(self, event: Allocated):
        allocation = AllocationsViewModel(**event.dict(exclude={"qty"}))
        await self.allocations.create(entity=allocation)
        self.logger.info("Synced Allocation View")

    @event_handler
    async def delete_allocation_view(self, event: Deallocated):
        await self.allocations.delete_by_orderid_and_sku(
            orderid=event.orderid, sku=event.sku
        )
        self.logger.info(
            f"Deallocated orders with: orderid={event.orderid}, sku={event.sku}"
        )
