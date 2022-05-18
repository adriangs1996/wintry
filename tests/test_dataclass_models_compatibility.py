from wintry.settings import WinterSettings
from wintry.testing import TestClient
from wintry.models import Model
from wintry import App, Body
from pydantic import BaseModel


class Item(Model, unsafe_hash=True):
    name: str
    price: int


class ItemForm(BaseModel):
    name: str
    price: int


class Nested(Model):
    item: Item
    x: str


app = App(
    settings=WinterSettings(auto_discovery_enabled=False, backends=[], transporters=[])
)


@app.post("/", response_model=Item)
async def post_item(item: Item = Body(...)):
    return item


@app.post("/pydantic", response_model=Item)
async def post_pydantic_item(item: ItemForm):
    return item


@app.post("/nested", response_model=Nested)
async def nested(n: Nested):
    return n


client = TestClient(app)


def test_endpoint_same_response_model_and_body_works():
    result = client.post("/", json={"name": "test_item", "price": 200})
    assert result.status_code == 200
    assert Item.build(result.json()) == Item(name="test_item", price=200)


def test_endpoint_dataclass_response_with_pydantic_body():
    result = client.post("/pydantic", json={"name": "test_item", "price": 200})
    assert result.status_code == 200
    assert Item.build(result.json()) == Item(name="test_item", price=200)


def test_endpoint_nested():
    result = client.post(
        "/nested", json={"item": {"name": "test_item", "price": 200}, "x": "Hello"}
    )
    assert result.status_code == 200
    assert Nested.build(result.json()) == Nested(Item(name="test_item", price=200), "Hello")


def test_schema_generation_is_ok():
    schema = app.openapi()


def test_openapi_schema_is_ok():
    schema = app.openapi_schema
