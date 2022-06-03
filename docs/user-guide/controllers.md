# 🎮Controllers🎮
----------------
In 2003, Martin Fowler published Patterns of Enterprise Application Architecture, 
which presented MVC as a pattern where an "input controller" receives a request, 
sends the appropriate messages to a model object, takes a response from the model object, 
and passes the response to the appropriate view for display. So, for <img src="/wintry/img/penguin-logo.png" width="20">
**Wintry**, we
use 🎮"controllers" to define a software layer that accepts input and converts it to commands 
for the model or view.

Latter on this tutorial, we will take the term "commands" quite literally, but for now, let's get started
with controllers.

## Introduction
---------------
This ⛩️section⛩️ will provide details about how 🎮Controllers works, some perks at
HTTP requests handling, Model Binding caveats, configurations for the controller,
correlation🤝 with other components and some features you can abuse when using controllers.
I'll try to not make use of the builtin <a href="/wintry/user-guide/di" class="external-link">Dependency Injection💉</a> as 
that's a general concept that is not specific to this, although there are some specifics in how 🎮Controllers and
<a href="/wintry/user-guide/di" class="external-link">Dependency Injection💉</a> works together.

## Create your first controller
-------------------------------
🎮Controllers are the way your App will talk to the external world. It is trending📈 that applications
divide their component in two BIG groups: Back-End and Front-End. Each of this group have different
ways of been implemented, and each talk to each other to produce the mayority of the apps we currently
know. Well, controllers are your Back-End connectors to your Front-End, or better yet, the interface
or contract that you stablish wich your client so it comunicates with that part of your App.

Mapping to other frameworks, we can see a 🎮Controller in <img src="/wintry/img/penguin-logo.png" width="20">
**Wintry** as a Router in
<a href="https://fastapi.tiangolo.com" class="external-link">FastAPI</a> or a view + urlpatterns
in <a href="https://www.djangoproject.com/" class="external-link">Django</a>. In fact, under the hood,
<img src="/wintry/img/penguin-logo.png" width="20">
**Wintry** 🎮controllers are just a <a href="https://fastapi.tiangolo.com">FastAPI</a>'s Router 
derived class with some additional behavior, and the `#!python @controller` decorator just take
a bunch of metadata and inspect the declared methods for creating the Router and register it
in the <img src="/wintry/img/penguin-logo.png" width="20">
**Wintry**'s register system.

You declare a controller like this:

```python linenums="1"
from wintry.controllers import controller, get
from wintry import App
from wintry.settings import WinterSettings

@controller
class Controller:
    @get("/")
    async def hello_world(self):
        return "Hello World"

app = App(WinterSettings(auto_discovery_enabled=False)) # ignore this config for now
```
    *This script is complete and it should run as it is*

That's it. That's the bare minimum amout of code needed for creating an API.
Actually you can do better, but is the same as declaring a single endpoint
in <a href="https://fastapi.tiangolo.com" class="external-link">FastAPI</a>
and I will say that this is the way you should go 99% of the time.

!!! info
    Through the tutorial, I might just use something like this:
    ```python
    from wintry import App
    from wintry.settings import WinterSettings

    app = App(WinterSettings(auto_discovery_enabled=False))

    @app.get('')
    async def hello_world():
        return "Hello World"
    ```

    when I'm not interested in exploit `#!python @controller` functionalities. This is 
    just for making examples, the 🎮Controller approach is more powerfull and achieve the same.
    This is the exact couterpart of <a href="https://fastapi.tiangolo.com" class="external-link">FastAPI</a>
    Hello World