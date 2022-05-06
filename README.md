# Wintry ==> A new python web framework with cool features for ... everybody




![](https://img.shields.io/static/v1?label=code&message=python&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=web&message=framework&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=Tests&message=Passing&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=pypi%20package&message=v0.1.0&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)


Hello, friend, welcome to Wintry. You may have stumble with this project searching
for a python web framework, well, you got what you want.

Pherhaps you know many other frameworks, pherhaps you know Django, or maybe Flask,
or hopefully FastAPI. And odds are that you are willing to take a new project for a
ride with a new alternative. Well, Wintry is this, your new alternative, one that
do not push you out of your confort zone, but do not take the "written before" path.

Beign accured, if you have used FastAPI, you would feel at home, Wintry is heavilly
inspired in FastAPI, it actually uses it whenever it can. But it add a bunch of 
'cool' stuff on top.

Let me tell you a story, that would give an idea from where this project come from.

## Inspirations
---------------

I have used FastAPI a lot for the last year, and I am absolutely fascinated about it.
Speed + Python on the same sentence, that's something to really appreciate. I know, a big
thanks to starlette project which is the real hero on that movie, but, FastAPI adds a ton
of cool features on top, if I would describe them in one word, it would be: Pydantic.

Ok, but, Django has a lot of cool features too, it is even called 'Batteries included
framework', and it is true, I mean, who doesn't love the Django's builtin Admin Interface,
or Django Forms?, not to mention DjangoRestFramework which is a REAALLY cool piece of software.

Enough flattering, Wintry will try to be the new Kid in Town, to provide a DDD
focused experience, with builtin Dependency Injection system, a dataclasses based
Repository Pattern implementation, Unit Of Work, Events Driven Components and a lot more.
Actually, I aimed to provide a similar experience with Repositories than that of
Spring JPA. Just look at the example, it is really easy to write decoupled and modularized applications with **Wintry**.

Let's see what **Wintry** looks like:

```python
from wintry.models import entity, fromdict
from wintry.repository import Repository
from wintry.controllers import controller, post, get
from wintry.dependency_injection import provider
from wintry.errors import NotFoundError
from dataclasses import field
from bson import ObjectId
from pydantic import BaseModel
from wintry import ServerTypes, Winter
from wintry.settings import BackendOptions, ConnectionOptions, WinterSettings

@entity(create_metadata=True)
class Hero:
    city: str
    name: str
    id: str = field(default_factory=lambda: str(ObjectId()))

@entity(create_metadata=True)
class Villain:
    name: str
    city: str
    id: str = field(default_factory=lambda: str(ObjectId()))
    hero: Hero | None = None

class HeroForm(BaseModel):
    city: str
    name: str

class HeroDetails(BaseModel):
    name: str
    id: str

    class Config:
        orm_mode = True

class VillainDetails(BaseModel):
    name: str
    id: str
    hero: Hero | None = None

    class Config:
        orm_mode = True

@provider
class HeroRepository(Repository[Hero, str], entity=Hero):
    pass

@provider
class VillainRepository(Repository[Villain, str], entity=Villain):
    async def get_by_name(self, *, name: str) -> Villain | None:
        ...

@controller
class MarvelController:
    def __init__(self, heroes: HeroRepository, villains: VillainRepository):
        self.heroes = heroes
        self.villains = villains

    @post('/hero', response_model=HeroDetails)
    async def save_hero(self, hero_form: HeroForm = Body(...)):
        hero = fromdict(hero_form.dict())
        await self.heroes.create(hero)
        return hero

    @get('/villain/{name}', response_model=VillainDetails)
    async def get_villain(self, name: str):
        villain = await self.villains.get_by_name(name=name)
        if villain is None:
            raise NotFoundError()

        return villain


settings = WinterSettings(
    backends=[
        BackendOptions(
            connection_options=ConnectionOptions(
                url="postgresql+asyncpg://postgres:secret@localhost/tests"
            )
        )
    ],
    app_root="test_app",
    server_title="Testing Server API",
    server_version="0.0.1",
)

Winter.setup(settings)

api = Winter.factory(settings, server_type=ServerTypes.API)
```

Note that the method **get_by_name** is NOT IMPLEMENTED, but it somewhow still works :). The thing is Repositories are query compilers,
and you dont need to implement them, only learn a very simple
query syntax. That's not the only thing, the **@provider** decorator
allows the repositories to be injected inside the marvel controller
constructor, just like happens in .NET Core or Java Spring.

Note that my Hero and Villain entities, does not contain anything special, they are merely dataclasses (That's the only restriction, models needs to be dataclasses), and the relation is being automatically build for us. We even get an instance of **Hero** when
we call **get_villain** if the **Villain** has any **Hero** assigned.

Futhermore, if I want to change to use **MongoDB** instead of **Postgres**, is as easy as
to change the configuration url, and THERE IS NO NEED TO CHANGE THE CODE,
it would just work. In fact, for consistency, the only recomended change to the code would
be to remove the create_metadata=True from the @entity decorator:

```python

...

@entity
class Hero:
    ...

@entity
class Villain:
    ...

...
```

You can look for a complete example under [test_app](https://github.com/adriangs1996/winter/tree/master/test_app)

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

* Automatic Relational Database metadata creation

* Automatic Query Creation

* Reactive Domain Models

* Dependency Injection

* Publisher Subscribers

* Services

* Everything from FastAPI y a really confortable way

* Settings based on Pydantic

This is the continuation of NEXTX, which would be deprecated
in favor of this

## ROADMAP
----------
* Create documentation

* Add more features to the feature list with links to
the corresponding documentation

* Add RPC support (Maybe protobuf, raw TCP, Redis, RabbitMQ, Kafka, etc)

* Ease registration of Middlewares

* Provide Implementation of Authorization Services

* Create CLI for managing project

* Provide Support for migrations (from the cli)

* Templates

* Maybe some ViewEngine (Jinja, or we could go deep and try Brython ??? IDK)

## Contributions
----------------

Every single contribution is very appreciated. From ideas, issues,
PR, criticism, anything you can imagine.

If you are willing to provide a PR for a feature, just try to
give at least some tests for the feature, I try my best
mantaining a pool of tests that will be growing with time

- [Issue Tracker](https://github.com/adriangs1996/winter/issues)

- [Fork the repo, change it, and make a PR](https://github.com/adriangs1996/winter)

## Thanks
--------
To @tiangolo for the amazing [SQLModel](https://github.com/tiangolo/sqlmodel) and [FastAPI](https://github.com/tiangolo/fastapi)

To the amazing [Django Team](https://github.com/django/django)

To the Spring Project and [NestJS](https://nestjs.com/) for such amazing frameworks


License
-------

This project is licensed under the MIT License