# Quick Start

Here you will find a gentle introduction to **Wintry**. No in-deep API discussion
or details related to every specific possible combination of settings. Instead
you will be able to grasp the full power of **Wintry** through
a textbook-like tutorial over an imaginary APP which will allow
me to show you the approaches that lead to the creation of **Wintry**
and how easy is to build 'cool stuff' with it. We have a long road
ahead, let's get started!.

## The demo app. A Domain Driven Approach
--------------

This demo follows the same road of [this book](https://www.cosmicpython.com/book/preface.html), which I personally love. The API design is Domain Model centric, and I think that it always should be.
This means that we will try to do DDD, in the right way, with
as little (or none) details from data access as possible, and using
our Domain Models for every interaction and Domain Logic. I will jump
over most Design choices and dive directly in the implementation.

!!! tip "Think in your business logic first"

    We’ve found that many developers, when asked to design a new system, will immediately start to build a database schema, with the object model treated as an afterthought. This is where it all starts to go wrong. Instead, behavior should come first and drive our storage requirements. After all, our customers don’t care about the data model. They care about what the system does; otherwise they’d just use a spreadsheet.

Suppose we are working for a furniture retailer, and now we are
concerned with the allocation system. Some rules are:

* We need to allocate order lines to batches. When we’ve allocated an order line to a batch, we will send stock from that specific batch to the customer’s delivery address. When we allocate x units of stock to a batch, the available quantity is reduced by x.

* We can’t allocate to a batch if the available quantity is less than the quantity of the order line

* We can’t allocate the same line twice

The following class definitions could
represent an Aggregate for consinstency and boundaries checks.

!!! tip Aggregates
    An AGGREGATE is a cluster of associated objects that we treat as a unit for the purpose of data changes.

```py title="models.py", linenums="1"
from wintry.models import Model
from dataclasses import field

class OrderLine(Model, frozen=True):
    orderid: str
    sku: str
    qty: int

class Batch(Model):
    reference: str
    sku: str
    purchased_quantity: int
    allocations: set[OrderLine] = field(default_factory=set)
    eta: date | None = None

    def allocate(self, line: OrderLine):
        if self.can_allocate(line):
            self.allocations.add(line)

    def deallocate(self, line: OrderLine):
        if line in self.allocations:
            self.allocations.remove(line)

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

class Product(Model): # (1)
    sku: str = field(metadata={"id": True}) # (2)
    batches: list[Batch] = field(default_factory=list)

    def allocate(self, line: OrderLine) -> str:  #(3)
        try:
            batch = next(b for b in sorted(self.batches) if b.can_allocate(line))
            batch.allocate(line)
            return batch.reference
        except StopIteration:
            raise OutOfStock(f"Out of stock for sku {line.sku}")

```

1.  Models are transformed to dataclasses, so no need to define
a dummy constructor.
2.  `sku` is the identifier of this model.

Models are automatically converted to dataclasses, so we now
have the same representation as before in a more compact
format. Futhermore, we can no build instances of our models
using `#!python Batch.build()` or serialize them using `#!python Batch.to_dict()`

