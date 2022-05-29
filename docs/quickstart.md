# Quick Start

Here you will find a gentle introduction to 🐧**Wintry**🐧. No in-deep API discussion
or details related to every specific possible combination of settings. Instead
you will be able to grasp the full power of 🐧**Wintry**🐧 through
a textbook-like tutorial over an imaginary APP which will allow
me to show you the approaches that lead to the creation of 🐧**Wintry**🐧
and how easy is to build 'cool stuff' with it. We have a long road
ahead, let's get started!.

## The demo
--------------
👋 Hello there. Whether you are a newbie or a seassoned developer, you are at the right place.
You will develop a full CRUD app, from scratch, using 🐧**Wintry**🐧 to ease your development
flow. You'll find that the framework tries to remove the hazzle of setting up your
environment, and let you instead focus on what really matters, your business logic.

Pherhaps a lot of what you will see next feels like magic 🧙‍♂️, that's ok,
a lot of what 🐧**Wintry**🐧 do under the hood is pretty advanced stuff, but rest assure,
it is developed with speed 🚀, performance, and confort in mind. Also, I expect you to find
it really, really cool 🥶

This demo follows the same road of [this book📚](https://www.cosmicpython.com/book/preface.html), which I personally love. The API design is Domain Model centric, and I think that it always should be.
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
```

1.  Models are transformed to dataclasses, so no need to define
a dummy constructor.
2.  `sku` is the identifier of this model.

Models are automatically converted to dataclasses. Futhermore, we can now build instances of our models
using `#!python Batch.build()` or serialize them using `#!python Batch.to_dict()`

Notice that we define the models interaction inside the model itself, don't worry about persistance,
we will see that in a moment. First, let's tackle an issue that is not   appearent when first starting
the app's development, but this is a tutorial, and I'm allowed to cheat and go with time travel⌛.
The issues is "Query Segregation". Wait, WTF you just say. Is easy, usually when we develop an app,
we try to model two things at the same time: Relations and Representations.
We always want our Relations to be consistent, we want our representations to be efficient.
Translating to code, I want to represent `Batch` allocations as a list, because is easy to
remove or add new `OrderLines`, and to easily and accuratly compute `available_quantity` and
`allocated_quantity`. But when I query the system, I don't expect it to search to an entire
array for an `Allocation`, it would be better if this query is optimized too. The problem is,
we should split our model into "Write Data" and "Read Data", and there is a pattern that really
apply here: CQRS:

!!! note
    I'm not using Event-Sourcing here, usually comes together👪, but we should not confuse one
    with the other.

```python linenums="1" title="viewmodels.py"
from wintry.generators import AutoString
from wintry.models import Id, Model

class AllocationsViewModel(Model):
    id: str = Id(default_factory=AutoString)
    orderid: str
    sku: str
    batchref: str
```

I know I said we will not be concerned with data access at the moment, but the real
benefit of this split comes when we are querying a DB: we are eliminating the joins
from the query.

Ok, we have run from our persistance layer for a long time, let's tackle that next.

### One Aggregate = One Repository
---------------------------------

This is by no means enforced, but it is a good rule of thumb.
Thinking in Repositories at Aggregates levels allows to simplify
data access logic at the same time you guarantee some degree of 
cohesion between dependant models. Again, I follow this approach
as in the book 📚, but it is here just to make a point.

Repositories are abstractions over Data🗃️ Access, that allow us to treat databases as if we were controlling an in-memory data store. Usually Repositories are coupled to databases with a 
specific dialect. 🐧**Wintry**🐧 provides a unified view over data🗃️ access, but not the same way as Django. Django Model's Managers 
represent what is called an Active Record, and that aproach promotes the "Fat Models" antipattern. Well, is all a matter of opinions, but there is always one friction:
> Writting Queries for managing domain logic usually involve
pretty straight forward queries, specially for writting data🗃️.

So, with 🐧**Wintry**🐧 , you dont have to write your Queries at all, you can do it, though you most likely wont need it. Sounds🔊 confusing, let me show you how our persistance layer could look like:

```python title="repositories.py" linenums="1"
from tuto.viewmodels import AllocationsViewModel
from wintry.ioc import provider
from wintry.repository import Repository, query
from .models import Product

@provider # (3)
class ProductRepository(Repository[Product, str], entity=Product):
    @query
    async def get_by_sku(self, *, sku: str) -> Product | None:
        ... # (1)

    @query
    async def get_by_batches__reference(
        self, *, batches__reference: str
    ) -> Product | None:
        ...

@provider
class AllocationViewModelRepository(
    Repository, entity=AllocationsViewModel, for_backend="mongo" # (2)
):
    @query
    async def find_by_orderid(self, *, orderid: str) -> list[AllocationsViewModel]:
        ...

    @query
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
about data separation? Well, 🐧**Wintry**🐧 allow us to do that
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

Alright, we now need to define the interaction of our app, the way our Models talks one to another.
We will do it in a Event-Based fashion. In fact, we will write our service layer in a way that
will transform our app into a Message Pipeline.

### First thing First, ensure atomicity and consistency, use an UnitOfWork
--------------------------------------------------------------------------

Out of the box, 🐧**Wintry**🐧 integrates an UnitOfWork with your Repositories,
let's declare one for our app:

```python title="uow.py" linenums="1"
from wintry.transactions import UnitOfWork as WintryUnitOfWork
from wintry.ioc import provider
from .repositories import ProductRepository

@provider
class UnitOfWork(WintryUnitOfWork):
    products: ProductRepository

    def __init__(self, products: ProductRepository) -> None:
        super().__init__(products=products)
```

!!! tip "The Unit of Work pattern"
    The Unit of Work pattern is used to group one or more operations (usually database CRUD operations) into a single
    transaction or “unit of work” so that all operations either pass or fail as one unit. In simple words we can say that
    for a specific user action, say booking on a website, all the transactions like insert/update/delete and so on are
    done in one single transaction, rather than doing multiple database transactions. This means, one unit of work here
    involves insert/update/delete operations, all in one single transaction so that all operations either pass or fail as
    one unit.

Yes, thats all it takes. But how we use this?? If you read the idea of "Unit of Work", you probably
associate it with a lovely piece of python syntax: a context manager. That's how we use it, we enclose
our transaction inside a context manager and then commit the changes when we have done. If the transaction
fails for some reason, then the changes are rolled back. Let's see this in action, with the Unit of Work in place
we have everything we need to define our service layer.

### The service layer
---------------------
Service layers allows to decouple the business logic from storage requirements. Actually,
I like to think in services as if I were coding a transient app (Meaning that it gets
data from memory and so, can use all sort of `Python` representations and operate directly
on the model intances). This is actually a pretty powerfull concept, as applications tend
to become complex at the Domain Level, where restrictions and relations are enforced.
Also, services usually are represented in terms of verbs, that represent a desired action
to be executed by our system. This concept of action is what give the name to the `Command`
input that you will see in every service function. So, our service layer could look like this:

```python linenums="1" title="services.py" hl_lines="26 27 28 29 30 31 32 33 34 35 36 37 38 39 40""
from logging import Logger
from tuto.publisher import Publisher
from tuto.repositories import AllocationViewModelRepository
from tuto.viewmodels import AllocationsViewModel
from wintry.mqs import event_handler, command_handler, MessageQueue
from wintry.ioc import provider
from .uow import UnitOfWork
from .commands import Allocate, ChangeBatchQuantity, CreateBatch
from .models import Batch, OrderLine, Product
from .events import Allocated, Deallocated, OutOfStock as OutOfStockEvent

class InvalidSku(Exception):
    pass

@provider
class MessageBus(MessageQueue): # (1)
    uow: UnitOfWork # (3)
    logger: Logger
    sender: Publisher # (2)
    allocations: AllocationViewModelRepository

    @command_handler # (4)
    async def allocate(self, command: Allocate):
        line = OrderLine.build(command.dict())

        async with self.uow as uow:
            product = await uow.products.get_by_sku(sku=line.sku)
            if product is None:
                raise InvalidSku(f"Invalid sku {line.sku}")

            batchref = product.allocate(line)
            if batchref is not None:
                self.register(
                    Allocated(orderid=line.orderid, sku=line.sku, qty=line.qty, batchref=batchref)
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
                product = Product(sku=command.sku)
                product = await uow.products.create(entity=product)
            product.batches.append(
                Batch(reference=command.ref, purchased_quantity=command.qty, sku=command.sku, eta=command.eta,)
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
```

1.  The `MessageQueue` will be explained in the Message Pipeline Chapter, but long story short,  
it will allow you to translate your imperative app into a reactive pipeline of commands and events. 
You declare handlers for commands and events, and they will get fired🚀 by the `MessageQueue` at the right input.

2.  Use Dependency Injection for a Publisher interface, we will get to the implementation in short. It
just forward events to redis.

3.  Our Unit Of Work implementation, injected by the Dependency Injection System.

4.  Register a handler for the `#!python Allocate` command. Commands are just pydantic models
and usually they are used as inputs in controllers.

There is a lot going on there, but notice something: we are never calling the `#!python Repository.update()`
method, we just call functions over model instances that manage the state of the instance and its
relations with other models. And notice that we do all this inside an `#!python uow` context manager, and we
issue a `#!python uow.commit()` at the end. Should be scratching your head right now, because, I mean, this
can not work, right ??!! Well, it does, and actually is not even thanks to 🐧**Wintry**🐧 (at least not
entirely) because in here, we are using the full power of SQLAlchemy sessions to achieve this effect.
The cool part, and when 🐧**Wintry**🐧 becomes a really powerfull tool for this endeavor, is that it doesnt
matter if you change to use MongoDB as your primary DB (a NOSQL one), it will provide you with the same
features of automatic model synchronization. Futhermore, look at how clean the implementation of the
services is, and of course, testability is achieved with so many components decoupled and used through
the Depedency Injection System.

!!! note  "About Models"
    If you ever have used Vue.js in the past, the idea with reactive models is somehow similar as
    how `refs` work in Vue.js. Behind the scenes, 🐧**Wintry**🐧 is converting your model instances
    into Proxy Objects (either with SQLAlchemy sessions, or with 🐧**Wintry**🐧 builtin tracker)
    that record when a change is made to one of their properties, issuing an update for that
    property when the `#!python uow.commit()` is called. Of course, this means that this functionality is
    only available if repositories are linked with an UnitOfWork class, if used standalone, they must
    call `#!python Repository.update()` on the required instances.

Perhaps you are curious about the `#!python self.register()` function that every service
is calling. Well this is the way of the Message Pipeline to comunicate that something happened.
This are called `#!python Events`. For example, when we succesfuly allocate an orderline, we
register the `#!python Allocated` event, which is schedulled for triggering in the Message Pipeline.

But firing🚀 events is not useful if we do not supply handlers for them, right?

```python title="services.py"
# ... Rest of the code of the service layer
    @event_handler
    async def reallocate(self, event: Deallocated):
        async with self.uow as uow:
            product = await uow.products.get_by_sku(sku=event.sku)
            self.register(Allocate(**event.dict()))
            await uow.commit()

    @event_handler
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
```

Again, really clean and concise implementation thanks to all the help of the framework.
And notice a little detail, these are in-house events, meaning that they are fired🚀 and
received by the same Entity (The Message Pipeline). This might seem silly at first, because,
WTF don't we just put that code right before finishing the service function ???!! Well, this
will become clearer in the Events Handlers section, but the thing is that this events can be
run even in background, and represent a different logical unit than commands. Remember,
we want to follow the Single Responsability principle whenever we can right?

Notice that the Deallocated Event has declared two handlers. Yes, you can do that, why?, well,
because events can fail, and it is OK if they do, so you wanna split your event logic as most
as possible to ensure maximun cohesion in your app. More on this on the Events Section.

### External Events
-------------------
Notice that we use the `#!python Publisher.send()` here, but we have not implemented that yet, so let's do
that:

```python linenums="1" title="publisher.py"
import json
from typing import Protocol
from wintry.ioc import provider
import aioredis

class Publisher(Protocol):
    async def send(self, channel: str, data: dict):
        ...

@provider(of=Publisher) # (1)
class RedisPublisher(Publisher):
    def __init__(self) -> None:
        self.client = aioredis.from_url("redis://localhost")

    async def send(self, channel: str, data: dict):
        await self.client.publish(channel, json.dumps(data))
```

1.  😡😡Dude, this is brand new

Yeah I know, the `#!python @provider(of=Publisher)` line, this is how you declare
an implementation of an interface, notice that the Publisher class is just a protocol
in here. We have defined a RedisPublisher, so we will be sending events to a Redis Channel.

This could be useful in a fully Distributed System, as a notification🔔 or synchronization⏲️
mechanism. 🐧**Wintry**🐧 gives you the tools to also easily respond to such events, called
external events. Think if you are implementing a Microservice, or maybe your app has been
logically split into separated APIS, but that consume the same data source or are 
dependent somehow. Well you could use this mechanism to comunicate them. Let's see an example of
how we can go about this:

### Entrypoints
-----------

```python linenums="1" title="controllers.py"
from logging import Logger
from wintry.controllers import microservice, on
from .services import MessageBus

@microservice(TransporterType.redis)
class RedisMessagesControllers:
    logger: Logger
    messagebus: MessageBus

    @on("change_batch_quantity")
    async def change_batch_quantity(self, cmd: ChangeBatchQuantity):
        self.logger.info(f"Event from Redis: {cmd}")
        await self.messagebus.handle(cmd)

    @on("line_allocated")
    async def line_allocated(self, allocation: AllocationsViewModel):
        self.logger.info(f"Hey look, a line've been allocated from redis: {allocation}")
```

You guessed it, with this in place, we can now listen to the `line_allocated` and `change_batch_quantity`
redis channels. Notice how we injected a `MessageBus`🚌 instance and supply the `ChangeBatchQuantity` command
as an entry point to the Message Pipeline.

This same idea, is what we will use to conform our System API, so, our controllers will look like this:
```python linenums="1" title="controllers.py"
from tuto.viewmodels import AllocationsViewModel
from .views import AllocationReadModel, Views
from .commands import Allocate, CreateBatch
from wintry.controllers import controller, post, get
from .services import InvalidSku, MessageBus
from wintry.responses import DataResponse
from wintry.errors import NotFoundError

@controller(prefix="", tags=["Products"])
class ProductsController:
    messagebus: MessageBus
    views: Views

    @post("/add_batch", response_model=DataResponse[str])
    async def add_batch(self, cmd: CreateBatch):
        await self.messagebus.handle(cmd)
        return DataResponse[str](data="Created Batch")

    @post("/allocate", response_model=DataResponse[str])
    async def allocate(self, cmd: Allocate):
        try:
            await self.messagebus.handle(cmd)
            return DataResponse[str](data="Allocated", status_code=202)
        except InvalidSku as e:
            return DataResponse(status_code=400, message=str(e))

    @get("/allocations/{orderid}", response_model=DataResponse[list[AllocationReadModel]])
    async def allocations_view(self, orderid: str):
        results = await self.views.get_allocations_for(orderid)
        if not results:
            raise NotFoundError(f"{orderid}")

        return DataResponse(data=results)
```

You see the pattern here, every component in 🐧**Wintry**🐧 follows a similar pattern:

* Declare dependencies.
* Declare action handlers.
* Provide an entrypoint for those handlers.

Of course, this is only the tip of the iceberg🧊, but you can already see a little penguin🐧 at the top.
This can be a Emperor Penguin🐧, or simply a regular penguin, continue reading and find out.

### The App
-----------

So now we have everything we need in place, how do we start it?

```python linenums="1" title="app.py"
from logging import Logger
from wintry import App
from wintry.orm import metadata
from wintry import BACKENDS
from wintry.ioc import inject
from wintry.settings import (
    BackendOptions,
    ConnectionOptions,
    TransporterSettings,
    TransporterType,
    ConnectionOptions,
    WinterSettings
)

settings = WinterSettings(
    backends=[
        BackendOptions(
            name="default",
            driver="wintry.drivers.pg",
            connection_options=ConnectionOptions(
                url="postgresql+asyncpg://postgres:secret@localhost/tests"
            ),
        ),
        BackendOptions(
            name="mongo",
            driver="wintry.drivers.mongo",
            connection_options=ConnectionOptions(
                url="mongodb://localhost:27017/?replicaSet=dbrs"
            ),
        ),
    ],
    transporters=[
        TransporterSettings(
            driver="wintry.transporters.redis",
            service="RedisMicroservice",
            transporter=TransporterType.redis,
            connection_options=ConnectionOptions(url="redis://localhost"),
        )
    ],
)

app = App(settings=settings)
```

You can now run your app:

<div class="termy">
```console
$ uvicorn tuto.app:app --reload --port 8080

INFO:     Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)
INFO:     Started reloader process [1129311] using watchgod
INFO:     2022-05-28 22:22:35 | Loading module tuto.repositories
INFO:     2022-05-28 22:22:35 | Loading module tuto.events
INFO:     2022-05-28 22:22:35 | Loading module tuto.settings
INFO:     2022-05-28 22:22:35 | Loading module tuto.controllers
INFO:     2022-05-28 22:22:35 | Loading module tuto.commands
INFO:     2022-05-28 22:22:35 | Loading module tuto.services
INFO:     2022-05-28 22:22:35 | Loading module tuto.models
INFO:     2022-05-28 22:22:35 | Loading module tuto.views
INFO:     2022-05-28 22:22:35 | Loading module tuto.uow
INFO:     2022-05-28 22:22:35 | Loading module tuto.viewmodels
INFO:     2022-05-28 22:22:35 | Loading module tuto.publisher
INFO:     Started server process [1129313]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```
</div>

!!! Note
    The logs come from the autoload functionality, it will be explained latter on.
    The modules names comes from the [test app](https://github.com/adriangs1996/wintry/tree/master/tuto)
    that is shared with the github repository and it is the same from where I have been using the 
    source code for the demo.

### Check it out
----------------
Yo can now access the automatic documentation, got to <a href="http://127.0.0.1:8080/docs" class="external-link">
http://127.0.0.1:8080/docs</a>, where you should find the swagger:

<img src="/wintry/img/wintry_api_doc.png" />

Three endpoints do not make justice to what you have acomplished. You effectively:

* Defined your pristine Models💪 and handle business👨‍💼 logic in them.

* Created Segregated Repositories for Writing✍🏻 and Querying👁️‍🗨️ efficiently. You even
used two different databases for Write Operations and for Read Operations

* Made atomic transactions, which translate into data consistency.

* Communicate with an event broker and react to messages on some channels.

* Implemented your services in an asynchronous way.

* Defined your system entrypoints (API) and Model Binded the params into objects
with validation (Ok, maybe you missed that part, but I ensure you, it is there)

All that, while working with Postgres and MongoDB databases, without writting a single
line of SQL or MQL (Mongo Query Language), without worrying about ForeignKeys, Relations,
Columns or stuff like that, using components where you want, when you want, saving Models state
as if you where just manipulating objects in memory, listening to a Redis instance, that may as well
be a RabbitMQ server and still would be the same, declaring your app's requirements as if you
where telling the framework what you need instead of commanding it to do
stuffs, at the same time you get automatic documentation of your API and in general unleash the power of FastAPI,
and still you have the promise that you haven't see it all, that it just the begining,
I mean come on, I think you deserve a coffee☕, and 🐧**Wintry**🐧 deserves you to give it a shot🔫.