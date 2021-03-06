<img src="img/logo.jpg" />


# Wintry: A Web Framework for you, the developer, in a clean way, a cool way. Build apps with speed and ease, with the power of the winter at your side.



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

## Installation
---------------
<div class="termy">

```console
$ pip install wintry

---> 100%
```

</div>

Let's see what **Wintry** looks like:

```python title="app.py" linenums="1"
from wintry.controllers import controller, get
from wintry import App
from wintry.settings import WinterSettings

@controller
class MarvelController:

    @get('')
    async def hello_world(self):
        return "Hello World"

settings = WinterSettings()
api = App(settings)
```

Yeap, is that easy to build an API, self documented, everything that you would
expect from a FastAPI based framework, but already you can see some perks:

* A different rounting system (Class Based)

* The hability to use methods as endpoints, just as you would in more traditional
frameworks like .NET Core or NestJS

* An API Factory, which automatically recognizes your controller, and register it.

**Wintry** aims to provide a lot of things, and at the very least, it ease the process
of writting FastAPI endpoints. But we are just scratching the surface here, this is the tip
of the Iceberg. Grab your cough, make a hot coffee, and embrace the 'cool', because winter is
comming and this penguin framework would prepare you for it.

Besides all that, **Wintry** is fully build with type-annotations, which make
a developer's editor best friend.

## Run it
---------
<div class="termy">

```console
$ uvicorn app:api --reload

INFO:     Uvicorn running on http://localhost:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [124387] using statreload
INFO:     Started server process [124390]
INFO:     Waiting for application startup.
INFO:     Application startup complete.

```
</div>

## Check it
-----------
Go to <a href=http://localhost:8000/marvel class="external-link" target=_blank>http://localhost:8000/marvel</a> and you should see:

```JSON
"Hello World"
```

## Interactive API docs
-----------------------

Go to <a href=http://localhost:8000/docs class="external-link" target=_blank>http://localhost:8000/docs</a>

You will see the automatic API Documentation, just as like you are used from FastAPI:

<img src="img/index.md.swag.png" />

## Contributions
----------------

Every single contribution is very appreciated. From ideas, issues,
PR, criticism, anything you can imagine.

If you are willing to provide a PR for a feature, just try to
give at least some tests for the feature, I try my best
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