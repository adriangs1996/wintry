# 🎮Controllers🎮
----------------
In 2003, Martin Fowler published Patterns of Enterprise Application Architecture, 
which presented MVC as a pattern where an "input controller" receives a request, 
sends the appropriate messages to a model object, takes a response from the model object, 
and passes the response to the appropriate view for display. So, for 🐧**Wintry**, we
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

Mapping to other frameworks, we can see a 🎮Controller in 🐧**Wintry** as a Router in
<a href="https://fastapi.tiangolo.com" class="external-link">FastAPI</a>
