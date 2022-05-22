from dataclasses import field
from wintry.models import Model
from uuid import uuid4

class Hero(Model, name="heroes"):
    city: str
    name: str
    id: str = field(default_factory=lambda: uuid4().hex)

    def salute(self):
        return f"I'm: {self.name}"
