from dataclasses import field
from winter.models import entity
from bson import ObjectId


@entity(name="heroes")
class Hero:
    city: str
    name: str
    id: str = field(default_factory=lambda: str(ObjectId()))

    def salute(self):
        return f"I'm: {self.name}"
