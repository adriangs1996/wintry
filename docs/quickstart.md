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
    sku: str
    purchased_quantity: int
    reference: str = field(metadata={"id": True})
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

Models are automatically converted to dataclasses. Futhermore, we can now build instances of our models
using `#!python Batch.build()` or serialize them using `#!python Batch.to_dict()`

## One Aggregate = One Repository
---------------------------------

This is by no means enforced, but it is a good rule of thumb.
Thinking in Repositories at Aggregates levels allows to simplify
data access logic at the same time you guarantee some degree of 
cohesion between dependant models. Again, I follow this approach
as in the book, but it is here just to make a point.

Repositories are abstractions over Data Access, that allow us to treat databases as if we were controlling an in-memory data store. Usually Repositories are coupled to databases with a 
specific dialect. Wintry provides a unified view over data access, but not the same way as Django. Django Model's Managers 
represent what is called an Active Record, and that aproach promotes the "Fat Models" antipattern. Well, is all a matter of opinions, but there is always one friction:
> Writting Queries for managing domain logic usually involve
pretty straight forward queries, specially for writting data.

So, with Wintry, you dont have to write your Queries at all, you can do it, though you most likely wont need it.

```python title="repositories.py" linenums="1"
from wintry.repository import Repository
from .models import Product

class ProductRepository(Repository[Product, str], entity=Product):
    async def get_by_sku(self, *, sku: str) -> Product | None:
        ...
```

So you may ask: Ok, where is `#!python get_by_sku` implemented?

That's the beauty, yo don't, it is already there, in the name. Repositories are query compilers and automatically translate
your method names into queries, and yes, it automatically knows
how to build your object from your data source, and whether to return a list or a single object.

Speaking of data source, we better configure one to make the whole thing real, right?
We will be using Postgresql for this tutorial, but any SQLAlchemy
compatible database will do. To ensure we have a Postgresql instance running in our localhost, we can use Docker with the following docker-compose:

```yaml title="docker-compose.yml" linenums="1"
services:
  postgres:
    container_name: postgres
    image: postgres:14-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_PASSWORD=secret
      - POSTGRES_USER=postgres
      - POSTGRES_DB=tests
```

<div class="termy">

```console
$ docker compose up -d

⠿ Container postgres  Started 
```

</div>