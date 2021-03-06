<img src="docs/img/logo.jpg" />

# βοΈπ§A modern python web frameworkπ§βοΈ

![](https://img.shields.io/static/v1?label=code&message=python&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=web&message=framework&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=Tests&message=Passing&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=pypi%20package&message=v0.1.0&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)

!!! Note
 FRAMEWORK'S API IS CONSTANTLY EVOLVING. I PLAN TO GIVE A STABLE VERSION WITH THE 1.0.0
 RELEASE. BUT GIVE IT A TRY, IT MIGHT BECOME A GOOD FRIEND OF YOURS :)

Hello, friend, welcome to π§**Wintry**π§. You may have stumble with this project searching
for a python web framework, well, you got what you want.

Pherhaps you know many other frameworks, pherhaps you know Django, or maybe Flask,
or hopefully FastAPI. And odds are that you are willing to take a new project for a
ride with a new alternative. Well, π§**Wintry**π§ is this, your new alternative, one that
do not push you out of your confort zone, but do not take the "written before" path.

Beign accured, if you have used FastAPI, you would feel at home, π§**Wintry**π§ is heavilly
inspired in FastAPI, it actually uses it whenever it can. But it add a bunch of 
π'cool'π stuff on top.

## Inspirations
---------------

I have used FastAPI a lot for the last year, and I am absolutely fascinated about it.
Speed + Python on the same sentence, that's something to really appreciate. I know, a big
thanks to starlette project which is the real hero on that movie, but, FastAPI adds a ton
of cool features on top, if I would describe them in one word, it would be: Pydantic.

Ok, but, Django has a lot of cool features too, it is even called 'Batteries included
framework', and it is true, I mean, who doesn't love the Django's builtin Admin Interface,
or Django Forms?, not to mention DjangoRestFramework which is a REAALLY cool piece of software.

Enough flattering, π§**Wintry**π§ will try to be the new Kid in Town, to provide a DDD
focused experience, with builtin Dependency Injection system, a dataclasses based
Repository Pattern implementation, Unit Of Work, Events Driven Components and a lot more.
Actually, I aimed to provide a similar experience with Repositories than that of
Spring JPA. Just look at the example, it is really easy to write decoupled and modularized
 applications with π§**Wintry**π§.

Let's see what π§**Wintry**π§ looks like:

```python
from wintry.models import Model, Id
from wintry.generators import AutoString
from wintry.repository import Repository, query
from wintry.controllers import controller, post, get
from wintry.ioc import provider
from wintry.errors import NotFoundError
from wintry import App, Body
from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings
from pydantic import BaseModel

class Hero(Model):
    id: str = Id(default_factory=AutoString)
    city: str
    name: str

class HeroForm(BaseModel):
    city: str
    name: str

@provider
class HeroRepository(Repository[Hero, str], entity=Hero):
    @query
    async def get_by_name(self, *, name: str) -> Hero | None:
        ...

@controller
class MarvelController:
    heroes: HeroRepository

    @post('/hero', response_model=Hero)
    async def save_hero(self, hero_form: HeroForm = Body(...)):
        hero = Hero.build(hero_form)
        await self.heroes.create(entity=hero)
        return hero

    @get('/hero/{name}', response_model=HeroForm)
    async def get_villain(self, name: str):
        hero = await self.heroes.get_by_name(name=name)
        if hero is None:
            raise NotFoundError()

        return hero


settings = WinterSettings(
    backends=[
        BackendOptions(
            driver="wintry.drivers.pg",
            connection_options=ConnectionOptions(
                url="postgresql+asyncpg://postgres:secret@localhost/tests"
            )
        )
    ],
)

api = App(settings)
```

Note that the method **get_by_name** is NOT IMPLEMENTED, but it somehow still works :). 
The thing is Repositories are query compilers,
and you dont need to implement them, only learn a very simple
query syntax. Cool ehh !?, but maybe you do not want to define your
methods in that way, because, I don't know, you feel it weird, or maybe
you need a scape-hatch for the limiting syntax that enforce the python function
namings, or maybe you feel that the query is just a little complicated and long
and goes against readabilit. Well, π§**Wintry**π§ got you cover, you can also
use a repository like this:

```python
from wintry.orm.aql import get

@provider
class HeroRepository(Repository[Hero, str], entity=Hero):
    @managed
    async def get_by_name(self, name: str) -> Hero | None:
        return await self.exec(get(Hero).by(Hero.name == name))
```

The good thing is that this is completely agnostic about what Backend you use
for storing your data (it could be MongoDB, it could be SQL Server, or PostgreSQL),
it simply doesn't matter.

Ok but still you are not satisfy right?, you want more control, you want to be able
to use specific features of your data store. Well, you can also do that. In the last
example, the repository was cofigured to be used with postgresql, so maybe we can
go and use sqlalchemy to access it right ??

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.engine.result import Result
from wintry.repository import Repository

class HeroRepository(Repository[Hero, str], entity=Hero):
    @managed
    async def get_by_name(self, name: str) -> Hero | None:
        stmt = select(self.vtable).where(self.vtable.c.name == name)
        conn: AsyncConnection = await self.connection()
        
        result: Result = await conn.execute(stmt)
        row = result.first()
        
        return Hero.build(row) if row else None
```

Ok, I grant it, this method is a somewhat awkward of setup, but this should
be used just for exceptional cases. Notice the `Hero.build()` method, this is
a handy way of mapping objects into your models. It handles pretty much anything,
lists, dicts or Custom Class Objects (CCO), and it comes with a surprise, it is
incredibly fast. You don't believe me, of course, check this out:

```python
from wintry.models import ModelRegistry, Model
from pydantic import BaseModel

class B(Model):
    y: int
    a: "A | None" = None

class A(Model):
    x: int
    y: int
    z: str
    a: float
    b: int
    bs: list[B] = field(default_factory=list)

class PydanticA(BaseModel, orm_mode=True):
    x: int
    y: int
    z: str
    a: float
    b: int
    bs: "list[PydanticB]" = []

class PydanticB(BaseModel, orm_mode=True):
    y: int
    a: "PydanticA | None" = None


obj = A(x=10, y=20, z="Hello", a=3.1, b=15, bs=[B(y=1)])

ModelRegistry.configure()
PydanticA.update_forward_refs()

if __name__ == '__main__':
    import timeit
    wintry = timeit.timeit(lambda: A.from_orm(obj), number=10000)
    pdc = timeit.timeit(lambda: PydanticA.from_orm(obj), number=10000)
    
    print(f"Wintry from obj: {wintry}")
    print(f"Pydantic from obj: {pdc}")
    print(f"Wintry is {pdc // wintry} times faster")
```

```console title="output"
Wintry from obj: 0.024381537004956044
Pydantic from obj: 0.17162273099529557
Wintry is 7.0 times faster
```

Of course this is a rough approximation, but you get the idea. Furthermore,
this is how objects are built within the framework, so you can expect it to be
really performant. This is achieved using a code-generation technique, and deferring
the method creation to runtime startup.

But wait, there is a lot more, the **@provider** decorator
allows the repositories to be injected inside the marvel controller
constructor, just like happens in .NET Core or Java Spring. But you can already
see that dependencies can be declared as attributes, making them more declarative.
Actually, the real power of the IoC System of π§**Wintry**π§ is that it allows to
combine the power of classical Dependency Injection, with Request-Based Dependency Injection
achieved by FastAPI, which gives you the ability to re-use dependencies over a whole bunch
of routes, and still been able to access its results.

```python
@dataclass
class User:
    name: str
    password: str

@provider
class UserService:
    def do_something_user(self, user: User):
        return user.name + " " + user.password

@controller
class Controller:
    service: UserService
    # This is populated on each request
    user: User = Depends()

    @get("/user")
    async def get_user(self):
        return self.user

    @get("/something")
    async def get_something(self):
        return self.service.do_something_user(self.user)
```

This is a really powerfull feature that both reduce code duplication and open doors for
a lot of functionalities, like Controller-Scoped authentication, filters, etc.

You may have noted from the first example, that my Hero entity does not contain anything special, it is merely a dataclass (That's the only restriction, models needs to be dataclasses). When using postgres (Or any compatible sqlalchemy database)
π§**Wintry**π§ will do its bests to create a database Schema that best matches your domain model without poisoning it
with DataAccess dependencies.

Futhermore, if I want to change to use **MongoDB** instead of **Postgres**, is as easy as
to change the configuration url and the driver 
and THERE IS NO NEED TO CHANGE THE CODE,
it would just work.

``` python
.... # rest of the same code
settings = WinterSettings(
    backends=[
        BackendOptions(
            driver="wintry.drivers.mongo",
            connection_options=ConnectionOptions(
                url="mongodb://localhost/?replicaSet=dbrs"
            )
        )
    ],
)
....
```

Of course, you maybe want to use refs instead of embedded documents, in that case then you need to do
exactly that, make your model split its objects with refs relations and the simply use it as usual.

One big concern when dealing with business operations, is that of logical consistency and
atomic transactions. Many ORMs provide different solutions. Well, π§**Wintry**π§ calls for an unified
approach. An actually is clean and readable, and really beautiful, check this out:

```python
@provider
class UserService:
    users: UserRepository

    @transaction
    async def update_user_and_delete_others(self, id: int, name: str):
        await self.users.delete_by_name(name=name)
        user = await self.users.get_by_id(id=id)
        assert user is not None
        assert user.address is not None
        user.address.latitude = 3.0
```

The above code, could fail if we accidentaly delete some users from database before
updating user with the given id. Well, being running in a transaction, means that
if any assertion fails, database changes automatically rollbacks and users are not
deleted, so we maintain our DB in a consistent way (according to our restrictions, yeah I know,
this is a bizarre one). Futhermore, notice how we never have to call update on a
transaction (except in some rare cases), because the transaction keeps track of changes
in objects properties and issue updates for them accordingly.

You can look for a complete example at this [test app](https://github.com/adriangs1996/wintry/tree/master/tuto) or
[this app](https://github.com/adriangs1996/wintry/tree/master/test_app)

You can also go and read the [πdocumentation, it is still under development, but eventually will cover the whole API, just as FastAPI or Django](https://adriangs1996.github.io/wintry)

## Installation
---------------
As simple as use

```
$ pip install wintry
```

or with poetry

```
$ poetry add wintry
```

## Features
-----------
There is a lot more to know about Wintry:

* Stack of patterns (RepositoryPattern, UnitOfWork, ProxyPattern,
MVC, Event-Driven-Desing,
CQRS, etc.)

* Automatic Relational Database metadata creation.

* Automatic Query Creation.

* Reactive Domain Models.

* Dependency Injection (Next Level).

* Transactional methods. This a really powerful feature that pairs with Dependency Injection
and Command&Event handler, providing a robust implementation of atomic write/update/delete operations.

* Publisher Subscribers.

* Services.

* Domain Model based on dataclasses.

* Short: Focus on what really matters, write less code, get more results.

* Everything from FastAPI in a really confortable way

* Settings based on Pydantic.

* A handy cli for managing projects (Feeling jealous of Rails ?? Not any more): Work in progress.


## ROADMAP
----------
* Performance similar to FastAPI (When possible, actually FastAPI is a LOWER BOUND) (need benchmarks and identify bottle necks).

* Create documentation

* Add more features to the feature list with links to
the corresponding documentation

* Add RPC support (Maybe protobuf, raw TCP, Redis, RabbitMQ, Kafka, etc)

* Ease registration of Middlewares

* Provide Implementation of Authorization Services

* Create CLI for managing project

* Provide Support for migrations (from the cli)

* Templates

* Maybe some ViewEngine (Most likely will be based on Jinja2)

* Implement a builtin Admin (Similar to Django), but taking advantage of the registry system.
Cool stuff here, perhaps we can dynamically create models and manage the databases in the admin
with a UI. IDK, maybe, just maybe.

## Contributions
----------------

Every single contribution is very appreciated. From ideas, issues,
PR, criticism, anything you can imagine.

If you are willing to provide a PR for a feature, just try to
give at least some tests for the feature, I do my best
mantaining a pool of tests that will be growing with time

- [Issue Tracker](https://github.com/adriangs1996/wintry/issues)

- [Fork the repo, change it, and make a PR](https://github.com/adriangs1996/wintry)

## Thanks
--------
To @tiangolo for the amazing [SQLModel](https://github.com/tiangolo/sqlmodel) and [FastAPI](https://github.com/tiangolo/fastapi)

To the amazing [Django Team](https://github.com/django/django)

To the Spring Project and [NestJS](https://nestjs.com/) for such amazing frameworks


License
-------

This project is licensed under the MIT License