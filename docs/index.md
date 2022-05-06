# Winter ==> A new python web framework with cool features for ... everybody




![](https://img.shields.io/static/v1?label=code&message=python&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=web&message=framework&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=Tests&message=Passing&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)
![](https://img.shields.io/static/v1?label=pypi%20package&message=v0.1.0&color=<blue>&style=plastic&logo=github&logoColor=4ec9b0)


Hello, friend, welcome to winter. You may have stumble with this project searching
for a python web framework, well, you got what you want.

Pherhaps you know many other frameworks, pherhaps you know Django, or maybe Flask,
or hopefully FastAPI. And odds are that you are willing to take a new project for a
ride with a new alternative. Well, winter is this, your new alternative, one that
do not push you out of your confort zone, but do not take the "written before" path.

Beign accured, if you have used FastAPI, you would feel at home, winter is heavilly
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

Enough flattering, Winter will try to be the new Kid in Town, to provide a DDD
focused experience, with builtin Dependency Injection system, a dataclasses based
Repository Pattern implementation, Unit Of Work, Events Driven Components and a lot more.
Actually, I aimed to provide a similar experience with Repositories than that of
Spring JPA. Just look at the examples, it is really easy to write decoupled and modularized applications with **Winter**.

Let's see what **Winter** looks like:

```python title="app.py" linenums="1"
from winter.controllers import controller, get
from winter import ServerTypes, Winter

@controller
class MarvelController:

    @get('')
    async def hello_world(self):
        return "Hello World"

api = Winter.factory(server_type=ServerTypes.API)
```

Yeap, is that easy to build an API, self documented, everything that you would
expect from a FastAPI based framework, but already you can see some perks:

* A different rounting system (Class Based)

* The hability to use methods as endpoints, just as you would in more traditional
frameworks like .NET Core or NestJS

* An API Factory, which automatically recognizes your controller, and register it.

**Winter** aims to provide a lot of things, and at the very least, it ease the process
of writting FastAPI endpoints. But we are just scratching the surface here, this is the tip
of the Iceberg. Grab your cough, make a hot coffee, and embrace the 'cool', because winter is
comming and this penguin framework would prepare you for it.

Besides all that, **Winter** is fully build with type-annotations, which make
a developer's editor best friend.

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