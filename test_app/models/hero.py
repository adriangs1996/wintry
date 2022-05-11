from dataclasses import field
from wintry.models import Model
from bson import ObjectId


class Hero(Model, name="heroes"):
    city: str
    name: str
    id: str = field(default_factory=lambda: str(ObjectId()))

    def salute(self):
        return f"I'm: {self.name}"
