# Quick Start

Here you will find a gentle introduction to **Wintry**. No in-deep API discussion
or details related to every specific possible combination of settings. Instead
you will be able to grasp the full power of **Wintry** through
a textbook-like tutorial over an imaginary APP which will allow
me to show you the approaches that lead to the creation of **Wintry**
and how easy is to build 'cool stuff' with it. We have a long road
ahead, let's get started!.

## The demo
--------------
👋 Hello there. Whether you are a newbie or a seassoned developer, you are at the right place.
You will develop a full CRUD app, from scratch, using **Wintry** to ease your development
flow. You'll find that the framework tries to remove the hazzle of setting up your
environment, and let you instead focus on what really matters, your business logic.

Pherphaps a lot of what you will see next feels like magic 🧙‍♂️, that's ok,
a lot of what **Wintry** ☃️ do under the hood is pretty advanced stuff, but rest assure,
it is developed with speed 🚀, performance, and confort in mind. Also, I expect you to find
it really, really cool 🥶

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
from datetime import date
from wintry.models import Model
from dataclasses import field   # (3)


class OutOfStock(Exception):
    pass


class OrderLine(Model, frozen=True):
    sku: str
    qty: int
    orderid: str = field(metadata={"id": True})


class Batch(Model):
    sku: str
    purchased_quantity: int
    reference: str = field(metadata={"id": True})
    allocations: list[OrderLine] = field(default_factory=list)
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
    sku: str = field(metadata={"id": True})  # (2)
    batches: list[Batch] = field(default_factory=list)

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
```

1.  Models are transformed to dataclasses, so no need to define
a dummy constructor.
2.  `sku` is the identifier of this model.
3.  `Model` convert classes to `dataclasses`, so we can use everything from dataclass in our models

Models are automatically converted to dataclasses. Futhermore, we can now build instances of our models
using `#!python Batch.build()` or serialize them using `#!python Batch.to_dict()`

Note that we define the models interaction inside the model itself, don't worry about persistance,
we will see that in a moment. First, let's tackle an issue that is not appearent when first starting
the app's development, but this is a tutorial, and I'm allowed to cheat and go with time travel⌛.
The issues is "Query Segregation". Wait, WTF you just say. Is easy, usually when we develop an app,
we try to model two things at the same time: Relations and Representations.
We always want our Relations to be consistent, we want our representations to be efficient.
Translating to code, I want to represent `Batch` allocations as a list, because is easy to
remove or add new `OrderLines`, and to easyly and accuratly compute `available_quantity` and
`allocated_qunatity`. But when I query the system, I don't expect it to search to an entire
array for an `Allocation`, it would be better if this query is optimized too. The problem is,
we should split our model into "Write Data" and "Read Data", and there is a pattern that really
apply here: CQRS:

!!! note
    I'm not using Event-Sourcing here, usually comes together, but we should not confuse one
    with the other.

```python linenums="1" title="viewmodels.py"
from wintry.models import Model


class AllocationsViewModel(Model):
    orderid: str
    sku: str
    batchref: str
```

I know I said we will not be concerned with data access at the moment, but the real
benefit of this split comes when we are querying a DB: we are eliminating the joins
from the query.

Ok, we have run from our persistance layer for a long time, let's tackle that next.

## One Aggregate = One Repository
---------------------------------

This is by no means enforced, but it is a good rule of thumb.
Thinking in Repositories at Aggregates levels allows to simplify
data access logic at the same time you guarantee some degree of 
cohesion between dependant models. Again, I follow this approach
as in the book, but it is here just to make a point.

Repositories are abstractions over Data Access, that allow us to treat databases as if we were controlling an in-memory data store. Usually Repositories are coupled to databases with a 
specific dialect. ☃️**Wintry**☃️ provides a unified view over data access, but not the same way as Django. Django Model's Managers 
represent what is called an Active Record, and that aproach promotes the "Fat Models" antipattern. Well, is all a matter of opinions, but there is always one friction:
> Writting Queries for managing domain logic usually involve
pretty straight forward queries, specially for writting data.

So, with ☃️**Wintry**☃️ , you dont have to write your Queries at all, you can do it, though you most likely wont need it. Sounds confusing, let me show you how our persistance layer could look like:

```python title="repositories.py" linenums="1"
from tuto.viewmodels import AllocationsViewModel
from wintry.dependency_injection import provider
from wintry.repository import Repository, raw_method, IRepository
from .models import Product


@provider # (3)
class ProductRepository(Repository[Product, str], entity=Product):
    async def get_by_sku(self, *, sku: str) -> Product | None:
        ... # (1)

    async def get_by_batches__reference(
        self, *, batches__reference: str
    ) -> Product | None:
        ...


@provider
class AllocationViewModelRepository(
    IRepository, entity=AllocationsViewModel, for_backend="mongo" # (2)
):
    async def find_by_orderid(self, *, orderid: str) -> list[AllocationsViewModel]:
        ...

    async def create(self, *, entity: AllocationsViewModel) -> AllocationsViewModel:
        ...

    async def delete_by_orderid_and_sku(self, *, orderid: str, sku: str):
        ...

```

1.  🧙‍♂️Hey dude, you forgot to implement your method, this will crush you in your face.... Well, no it didn't... BAZINGA!!🧙‍♂️
2.  ⚙️Do not give to much thinking to this, it would be explained in the Repository Chapter.
3.  💉This comes from the dependency injection module, it allows to latter on inject instances of this class

So you may ask: Ok, where are all these methods implemented?

That's the beauty, yo don't have to, it is already there, in the name. Repositories are query compilers and automatically translate
your method names into queries, and yes, it automatically knows
how to build your object from your data source, and whether to return a list or a single object.

Speaking of data source, we better configure one to make the whole thing real, right?
We will be using Postgresql, Mongo and Redis for this tutorial, but any SQLAlchemy
compatible database will do. Do you remember when we talked 
about data separation? Well, ☃️**Wintry**☃️ allow us to do that
at persistance layer very very easily too. 
For the setup, we can use Docker with the following docker-compose:

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

  mongo:
    container_name: mongo
    image: mongo:5.0.6-focal
    ports:
      - "27017:27017"
    restart: always
    volumes:
      - ./scripts/rs-init.sh:/scripts/rs-init.sh
    entrypoint:
      [
        "/usr/bin/mongod",
        "--bind_ip_all",
        "--replSet",
        "dbrs"
      ]

  redis:
    container_name: redis
    image: redis:6-alpine
    ports:
      - "6379:6379"
    restart: always
```

<div class="termy">

```console
$ docker compose up -d

[+] Running 5/5
 ⠿ Network winter_default Created                                                                                                      0.4s
 ⠿ Container postgres      Started                                                                                                      8.5s
 ⠿ Container redis         Started                                                                                                      8.7s
 ⠿ Container mongo         Started                                                                                                      6.5s
Starting replica set initialization
Connecting to:          mongodb://mongo:27017/?directConnection=true&appName=mongosh+1.3.1
MongoNetworkError: connect ECONNREFUSED 172.22.0.2:27017
Current Mongosh Log ID: 62803fdacc3f016a401c7b6f
Connecting to:          mongodb://mongo:27017/?directConnection=true&appName=mongosh+1.3.1
Using MongoDB:          5.0.6
Using Mongosh:          1.3.1

For mongosh info see: https://docs.mongodb.com/mongodb-shell/


To help improve our products, anonymous usage data is collected and sent to MongoDB periodically (https://www.mongodb.com/legal/privacy-policy).
You can opt-out by running the disableTelemetry() command.

------
   The server generated these startup warnings when booting:
   2022-05-14T23:48:28.619+00:00: Using the XFS filesystem is strongly recommended with the WiredTiger storage engine. See http://dochub.mongodb.org/core/prodnotes-filesystem
   2022-05-14T23:48:32.745+00:00: Access control is not enabled for the database. Read and write access to data and configuration is unrestricted
   2022-05-14T23:48:32.745+00:00: You are running this process as the root user, which is not recommended
------

waited for connection

Connection finished
Creating replica set
Current Mongosh Log ID: 62803fe159c7cb9bf4f581bd
Connecting to:          mongodb://mongo:27017/?directConnection=true&appName=mongosh+1.3.1
Using MongoDB:          5.0.6
Using Mongosh:          1.3.1

For mongosh info see: https://docs.mongodb.com/mongodb-shell/

------
   The server generated these startup warnings when booting:
   2022-05-14T23:48:28.619+00:00: Using the XFS filesystem is strongly recommended with the WiredTiger storage engine. See http://dochub.mongodb.org/core/prodnotes-filesystem
   2022-05-14T23:48:32.745+00:00: Access control is not enabled for the database. Read and write access to data and configuration is unrestricted
   2022-05-14T23:48:32.745+00:00: You are running this process as the root user, which is not recommended
------

test> {
  ok: 1,
  '$clusterTime': {
    clusterTime: Timestamp({ t: 1652572133, i: 1 }),
    signature: {
      hash: Binary(Buffer.from("0000000000000000000000000000000000000000", "hex"), 0),
      keyId: Long("0")
    }
  },
  operationTime: Timestamp({ t: 1652572133, i: 1 })
}
dbrs [direct: secondary] test> replica set created 
```

</div>


!!! tip
    All the output of the above console is necessary to show you that you need
    to configure the mongodb server as a replica set because that's the only way
    to use sessions.
    You can configure yours with the following script, this is the one used
    in the docker-compose file from above
    ```bash title="rs-init.sh"
        #!/bin/bash

        echo "Starting replica set initialization"
        until mongosh --host mongo --eval "print(\"waited for connection\")"
        do
        sleep 2
        done

        echo "Connection finished"
        echo "Creating replica set"

        MONGO1IP=$(getent hosts mongo | awk '{ print $1 }')

        read -r -d '' CMD <<EOF
        var config = {
            "_id": "dbrs",
            "version": 1,
            "members": [
                {
                    "_id": 1,
                    "host":'${MONGO1IP}:27017',
                }
            ]
        };
        rs.initiate(config, { force: true });
        EOF

        echo $CMD | mongosh --host mongo
        echo "replica set created"
    ```

## Service layer
---------------
Alright, we now need to define the interaction of our app, the way our Models talks one to another.
We will do it in a Event-Based fashion. In fact, we will write our service layer in a way that
will transform our app into a Message Pipeline.

### First thing First, ensure atomicity and consistency, use an UnitOfWork

Out of the box, ☃️**Wintry**☃️ integrates an UnitOfWork with your Repositories,
let's declare one for our app:

```python title="uow.py" linenums="1"
from wintry.transactions import UnitOfWork as WintryUnitOfWork
from wintry.dependency_injection import provider
from .repositories import ProductRepository


@provider
class UnitOfWork(WintryUnitOfWork):
    products: ProductRepository

    def __init__(self, products: ProductRepository) -> None:
        super().__init__(products=products)

```