from wintry.settings import WinterSettings
from wintry.testing import TestClient
from wintry.models import Model
from wintry import App
from pydantic import BaseModel


class Item(Model):
    name: str
    price: int


class ItemForm(BaseModel):
    name: str
    price: int


app = App(
    settings=WinterSettings(auto_discovery_enabled=False, backends=[], transporters=[])
)


@app.post("/", response_model=Item)
async def post_item(item: Item):
    return item

@app.post("/pydantic", response_model=Item)
async def post_pydantic_item(item: ItemForm):
    return item


client = TestClient(app)


def test_endpoint_same_response_model_and_body_works():
    result = client.post("/", json={"name": "test_item", "price": 200})
    assert result.status_code == 200
    assert Item.build(result.json()) == Item(name="test_item", price=200)


def test_endpoint_dataclass_response_with_pydantic_body():
    result = client.post("/pydantic", json={"name": "test_item", "price": 200})
    assert result.status_code == 200
    assert Item.build(result.json()) == Item(name="test_item", price=200)


def test_schema_generation_is_ok():
    schema = app.openapi()


def test_openapi_schema_is_ok():
    schema = app.openapi_schema