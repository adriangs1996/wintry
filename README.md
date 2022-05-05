# Winter

Hello, friend, welcome to winter. You may have stumble with this project searching
for a python web framework, well, not quite, but you almost got what you want.

Pherhaps you know many other frameworks, pherphas you know Django, or maybe Flask,
or hopefully FastAPI. And odds are that you are willing to take a new project for a
ride with a new alternative. Well, winter is this, your new alternative, one that
do not push you out of your confort zone, but do not take the "written before" path.

Beign accured, if you have used FastAPI, you would feel at home, winter is heavilly
inspired in FastAPI, it actually uses it whenever it can. But it add a bunch of 
'cool' stuff on top.

Let me tell you a story, that would give an idea from where this project come from.

## Inspirations

I have used FastAPI a lot for the last year, and I am absolutely fascinated about it.
Speed + Python on the same sentence, that something really to appreciate. I know, a big
thanks to starlette project which is the real hero on that movie, but, FastAPI adds a ton
of cool features on top, if I would describe them in one word, it would be: Pydantic.

Ok, but, Django has a lot of cool features too, it is even called 'Batteries included
framework', and it is true, I mean, who doesn't love the Django's builtin Admin Interface,
or Django Forms?, not to mention DjangoRestFramework which is a REAALLY cool piece of software.

Ok, enough flattering, where is the problem then ? Well, there is no problem at all, that's the
point. All this well behaved framworks makes you want to use them all. But wait, there are
actually some inconvenients.

Let's start with FastAPI first (just because it is my preference and I am biased :).

A normal implementation of an endpoint from a FastAPI app looks like
(let's assume we have a Postgres db running on our localhost, and we are using sqlalchemy for this):

```python
router = ApiRouter()

@router.post('')
async def save(db: AsyncSession = Depends(get_db), user_data: UserFormData = Body(...)):
    user = User(**user_data.dict())

    async with db.begin():
        user = await db.add(user)

    return user
```

This is cool, but wait a minute, there is a lot's going on there. First of all, we are calling domain logic inside a controller (this is not a good idea, controllers should take care only of handling parameters and responses at the HTTP layer and calling the respective services).
Second, we have stablish that our controller endpoint have a dependency on a db connection, and this is cool because we can
make use of FastAPI dependency injection for resolving this, but
here is the catch, FastAPI DI only triggers on endpoint call (this is
not exactly true, but the idea is that you have to leverage the dependes at endpoint level or wrap them on function calls)

It would be nice if we could do something like:

```python
router = ApiRouter()

@router.post('')
async def save(user_service = Depends(get_user_service), user_data: UserFormData = Body(...)):
    user = User(**user_data.dict())
    inserted_user = await user_service.save(user)
    return inserted_user
```

Even better:


```python
router = ApiRouter()

user_service = UserService()

@router.post('')
async def save(user_data: UserFormData = Body(...)):
    user = User(**user_data.dict())
    inserted_user = await user_service.save(user)
    return inserted_user
```

It is not a simple matter of taste, handling scopes with these dependencies
is not easy. And one big problema is that now **user_service** is global to all the importers of this module. That may not seen as a problem
but on big complex applications, these "Singletons" tends to be the cause
of a big ball of mud, specially if they are stateful. Besides, there is one big drawback,
We cant use Dependency Injection in the constructor of the **UserService**, for that we must call it inside a depends on an endpoint.

Winter is build following the clean architecture principle, and builds 
on top of FastAPI to achieve that. The main idea is to put Domain Models as the center of the development, and try to leave as many
details to framework as possible.

Let me give you a hint about that: most libraries provide a Model
centric aproach to map entities in databases. For FastAPI, there is
an awesome library called SQLModel, wrote by the same author of FastAPI
that really makes easy to bring the gap between domain models and
tables (SQLAlchemy Models). But it leave you with two little problems.
You must be somewhat aware of configuring your database relations and
it only support SQLAlchemy (ie, only relational databases). So moving to mongo is not as straight forward, for example if you
rely on a repository implementation using this as your input and output model, switching may not be as easy as it looks.

Let's see what winter looks like:

```python
from winter.models import entity, fromdict
from winter.repository import Repository
from winter.controllers import controller, post, get
from winter.dependency_injection import provider
from winter.errors import NotFoundError
from dataclasses import field
from bson import ObjectId
from pydantic import BaseModel

@entity(create_metadata=True)
class Hero:
    city: str
    name: str
    id: str = field(default_factory=str(ObjectId()))

@entity(create_metadata=True)
class Villain:
    name: str
    city: str
    id: str = field(default_factory=str(ObjectId()))
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
```

Yeah, I know, is a lot more than the FastAPI examples, but of, course
there is a lot's going on there. Just consider, to extend the FastAPI
example to do the same thing this is doing, you would need a lot more.
Note that the method **get_by_name** is NOT IMPLEMENTED, but it somewhow still works :). The thing is Repositories are query compilers,
and you dont need to implement them, only learn a very simple
query syntax. That's not the only thing, the **@provider** decorator
allows the repositories to be injected inside the marvel controller
constructor, just like happens in .NET Core or Java Spring.

Note that my Hero and Villain entities, does not contain nothing special, they are merely dataclasses (That's the only restriction, models needs to be dataclasses), and the relation is being auto
matically build for us. We even get an instance of **Hero** when
we call **get_villain** if the **Villain** has any **Hero** assigned.

Futhermore, if I want to change to use **MongoDB** instead of **Postgres**, is as easy as
to change the configuration in a settings.json, and THERE IS NO NEED TO CHANGE THE CODE,
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

## Features
There is a lot more to know about winter:

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

## ROADMAP

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

Every single contribution is very appreciated. From ideas, issues,
PR, criticism, anything you can imagine.

If you are willing to provide a PR for a feature, just try to
give at least some tests for the feature, I try my best
mantaining a pool of tests that will be growing with time