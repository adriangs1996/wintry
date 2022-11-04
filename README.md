<img src="docs/img/logo.jpg" />

# ❄️🐧A modern python web framework🐧❄️

![](https://img.shields.io/static/v1?label=code&message=python&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=web&message=framework&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=Tests&message=Passing&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=pypi%20package&message=v0.1.0&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)

!!! Note
 FRAMEWORK'S API IS CONSTANTLY EVOLVING. I PLAN TO GIVE A STABLE VERSION WITH THE 1.0.0
 RELEASE. BUT GIVE IT A TRY, IT MIGHT BECOME A GOOD FRIEND OF YOURS :)

Hello, friend, welcome to 🐧**Wintry**🐧. You may have stumble with this project searching
for a python web framework, well, you got what you want.

Pherhaps you know many other frameworks, pherhaps you know Django, or maybe Flask,
or hopefully FastAPI. And odds are that you are willing to take a new project for a
ride with a new alternative. Well, 🐧**Wintry**🐧 is just that, your new alternative, one that
do not push you out of your comfort zone, one that do not get in your away, no matter how
much you scale.

Beign accured, if you have used FastAPI, you would feel at home, 🐧**Wintry**🐧 is heavilly
inspired in FastAPI, it actually uses it whenever it can. But it adds a bunch of 
😎'cool'🆒 stuff on top.

## Inspirations
---------------

I have used FastAPI a lot for the last year, and I am absolutely fascinated about it.
Speed + Python on the same sentence, that's something to really appreciate. I know, a big
thanks to [starlette](https://github.com/encode/starlette) project which is the real hero on 
that movie, but, FastAPI adds a ton
of cool features on top: if I would describe them in three words, it would be: Pydantic 
and Dependency Injection.

On the other hand, we have [Django](https://github.com/django/django), a full-featured Framework,
which has an implementation for nearly everything you could imagine. But it is really opinionated
about how to do stuff. When a project starts to get big, usually developers found themselves
fighting the framework, instead of using it, just because they were trying to apply patterns and
techniques for which the framework was not designed for. FastAPI is like the sweet spot here,
because it offers just enough to get you started fast, and then you can use a vast ecosystem
to flesh it as your project gets big. And that's the problem. Too many tools, too many ways
they can be combined, to many relations that can be configured, and can potentially go wrong.

Is cool when you can build a rest api with 10 lines of code. Is cool when you see Pydantic used
in such a clever way to achieve model-binding at request time. Is cool that FastAPI gives us
already scoped (Request based) dependency injection. But if we are coming from .NET, or Spring,
or we are really committed to Microservices or Fully Decoupled Monolith with advanced techniques
such as CQRS and DDD, we start missing some good old controllers, some good old Constructor
based IoC. Also, it would be nice to have some form of Repository, right? Maybe some support for
Command and Query separation (And Events🤞). What about atomic transactions, can we have that too ?
And please, support for SQL and NoSQL DB 😊, because that's trending, and I want to split
my data into Write models and read models. Speaking of which, allow me to easily configure more
than one DB right. And please, I love the ORM and change tracking functionalities of SQLAlchemy,
can we have that for all our DB and integrated with the atomic transactions ? And can we .....

Yeah, a lot of good features, and all of them fully compatible with each other. That's what
🐧**Wintry**🐧 is all about. Be opinionated about some conventions and provide a large
range of tools, fully compatible with each other, that allows you, the developer, to
"DESIGN" and "IMPLEMENT" your system in the way you want, without the framework interposing
in your way, with the performance of the latest technologies, with the language that we all
love 😊.

Sounds good right ? Lets see how it looks like

```python
from wintry import scoped, controller, get, post, App, AppBuilder
from wintry.sql import Field
from pydantic import BaseModel
from sqlmodel import SQLModel

class Hero(SQLModel, table=True):
    id: str | None = Field(primary_key=True, default_factory=lambda: str(ObjectId()))
    name: str
    city: str | None = None

class CreateHeroModel(BaseModel):
    name: str
    city: str | None = None

@scoped
class HeroRepo:
    def __init__(self):
        pass
     
@controller
class HeroesController(object):
    heroes: HeroRepo

    @get("/", response_model=list[Hero])
    async def get_heroes(self):
        return await self.heroes.find()

    @post("/")
    @atomic(with_context=AppDbContext)
    async def create_hero(self, create_hero_model: CreateHeroModel):
        new_hero = Hero.from_orm(create_hero_model)
        await self.heroes.add(new_hero)
        return "Ok"

app = App()
AppBuilder.use_sql_context(app, SQLEngineContext, "sqlite+aiosqlite:///:memory:")
```

Cool ehh !?. Right now, you would have a fully-featured app. It is not your typical "hello world" app,
because that's boring. Instead, you now have an api, that creates and list heroes, with a clear separation
of your models, data access, and a presentation layer in the form of controllers. A paradise for testing and
decoupling. Furthermore, you have the ```@atomic``` decorator, which will roll-back your db changes
whenever an error occurs withing the post method. You have, as expected from FastAPI, a fully documented
API, with type annotations everywhere. Even more, you have a repository automatically created for you,
and the controller already depends on an abstraction, not the concrete repo, so it could easily be changed
for a mock for testing or whatever you want. Almost forgot, you can exchange the DB provider for any async
backend, sqlalchemy will handle it for you 😉.

Umm, but I want to use MongoDB, now, can I do it. YES!! Of course you can, and even more,
because you only depend on abstractions to build your controllers, it is now really easy
to swap the implementation for a NoSQL one.

First we need to use a different context
```python
from wintry import scoped
from wintry import NosqlAsyncSession
from wintry import DbContext
from wintry import MotorContext

@scoped
class MongoContext(NosqlAsyncSession, DbContext):
    def __init__(self):
        super().__init__(MotorContext.get_client(), database="test")

    async def dispose(self):
        pass
```

Then we register the new repository and remove the SQLModel from our model

```python
from wintry import NoSQLModel
from wintry import NoSQLRepository
from odmantic.bson import ObjectId

class Hero(NoSQLModel):
    id : str = Field(primary_field=True, default_factory=lambda: str(ObjectId()))
    name: str
    city: str | None = None
    
@scoped(of=AbstractRepository[Hero, str])
class HeroRepo(NoSQLRepository):
    def __init__(self, context: MongoContext):
        super().__init__(context, Hero)
```

And finally we register our new backend

```python
AppBuilder.use_mongo_context(app, MotorContext, "mongodb://localhost:27017")
```
That's it. Our controller still will be working the same.

Side Note !!: If you run your application with:
```commandline
 $ gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app 
```
You will see a surprise. Usually, when using MongoDb with Motor for the async Backend, and run
the app with gunicorn, because of the global client, the app will crash, with a Detached Task error.
You might be surprised that wintry handles this case for you, be defining the client inside a
Context var on the MotorContext, and then, retrieving it on each request when instantiating
the MongoContext, that's what `MotorContext.get_client()` is intended for.

If you are diving into Clean Architecture, DDD, and some advance stuff, you might be
unconformable by changing your model, after all, my hero should be just fine with its
new data store, it should not even care about ir right !?.

Well, that's pretty easy to achieve using SQLAlchemy (and soon with NoSQL too, thanks to
the incoming mapping layer for nosql-wintry). We can use imperative mapping as described
[here](https://docs.sqlalchemy.org/en/14/orm/mapping_styles.html#imperative-mapping),
and now our Hero will be a pure Python Object, and our repos will still behave the same,
and you can go and tweak your DB as much as you need and maintain our domain models as
clean as possible.

So far so good. At this point, wintry will prove to be really helpful, but it is not
bringing too much new to the table right ? I mean, yeah, you got repositories, decoupling
with abstractions, some fancy config API for setting up new DB Contexts as we can do
in .NET, we have Dependency Injection .... , wait, I said Dependency Injection, do I said
fully compatible with FASTAPI 😱😱!!!???

If you have used FastAPI before, you may have noticed that Dependencies, are not truly
Dependency Injection, is more like a Request Bound Resolution method, which is really cool
and helpful, but at the same time, tides you to the controller level. Furthermore, if I want
to use the same dependency in a bunch of methods, I will have to either replicate that
dependency on each method signature, or rescind from its return value. Imagine that you
want to secure now your two endpoints, using the same approach as the security section
in the FastAPI tutorial. In order to access the user information inside the endpoint,
you will have to declare something like this
```python
@app.get("/")
async def my_awsome_endpoint(user: Depends(get_logged_user)):
    ...
```

Not cool. I want to secure all my endpoints inside a controller and I don't want to
repeat my self. FastAPI with a penguin to the rescue, inside controllers, you can use
your FastAPI dependencies as usual, BUT, you can access their values, like this:

```python
@controller
class MyAwsomeController:
    user: LoggedUser = Depends(get_logged_user)

    @get("/")
    async def secured_endpoint(self):
        return self.user
```

But wait, there is a lot more, the **@scoped** decorator
allows the repository to be injected inside the controller
constructor, just like happens in .NET Core or Java Spring, and combine
it with the FastAPI Dependency Injection for giving you, the developer,
an extremely powerful tool to extend, reuse and configure your entire
application (tip: Most of the FastAPI ecosystem is build around Dependency Injection).
In fact, wintry relies heavily on the IoC (Inversion of Control) module, which, is
I like to call the Igloo.

Non-Fastapi DI is configured using two decorators: **@scoped** and **@provider**, which
gives you the ability to create Scoped (request bound), Transient (on demand) and Singleton
instances for each declared dependency. To prepare an object for injection, you could
use the **@inject** decorator. **@scoped** and **provider** mark their classes or functions
for injection as well. Other decorators already prepare their targets for injection, as
**@controller** and **@microservice**

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

* Dependency Injection (Next Level).

* Publisher Subscribers.

* Services.

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

* Templates

* Maybe some ViewEngine (Most likely will be based on Jinja2)

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