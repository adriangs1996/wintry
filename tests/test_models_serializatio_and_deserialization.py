from dataclasses import dataclass, field
from wintry.models import Model
from pydantic import BaseModel


class Foo(Model, mapped=False):
    x: int
    y: float


class Bar(Model, mapped=False):
    foo: Foo
    foos: list[Foo] = field(default_factory=list)


class PydanticFoo(BaseModel, orm_mode=True):
    x: int
    y: float


class AugmentedPydanticModel(BaseModel, orm_mode=True):
    x: int
    y: float
    other: str
    another: bool


class PydanticBar(BaseModel, orm_mode=True):
    foo: PydanticFoo
    foos: list[PydanticFoo] = []


class PydanticNestedModel(BaseModel, orm_mode=True):
    foo: PydanticFoo
    bar: PydanticBar
    x: int


class NestedModel(Model, mapped=False):
    foo: Foo
    bar: Bar
    x: int


@dataclass
class DataclassFoo:
    x: int
    y: float


def test_deserialize_simple_object():
    args = {"x": 10, "y": 1.13}
    model = Foo.build(args)

    assert model == Foo(x=10, y=1.13)


def test_deserialize_nested_object():
    args = {"foo": {"x": 10, "y": 1.13}}

    model = Bar.build(args)
    assert model == Bar(foo=Foo(x=10, y=1.13))


def test_deserialize_list_of_simple_objects():
    args = [{"x": 10, "y": 1.13}, {"x": 20, "y": 3.33}]
    models = Foo.build(args)

    assert models == [Foo(x=10, y=1.13), Foo(x=20, y=3.33)]


def test_deserialize_nested_list_of_objects():
    args = {
        "foo": {"x": 10, "y": 1.13},
        "foos": [{"x": 10, "y": 1.13}, {"x": 20, "y": 3.33}],
    }

    model = Bar.build(args)

    assert model == Bar(
        foo=Foo(x=10, y=1.13), foos=[Foo(x=10, y=1.13), Foo(x=20, y=3.33)]
    )


def test_deserialize_list_of_nested_objects():
    args = [
        {
            "foo": {"x": 10, "y": 1.13},
            "foos": [{"x": 10, "y": 1.13}, {"x": 20, "y": 3.33}],
        },
        {
            "foo": {"x": 11, "y": 1.13},
            "foos": [{"x": 11, "y": 1.13}, {"x": 21, "y": 3.33}],
        },
    ]

    models = Bar.build(args)
    assert models == [
        Bar(foo=Foo(x=10, y=1.13), foos=[Foo(x=10, y=1.13), Foo(x=20, y=3.33)]),
        Bar(foo=Foo(x=11, y=1.13), foos=[Foo(x=11, y=1.13), Foo(x=21, y=3.33)]),
    ]


def test_serialize_simple_object():
    model = Foo(x=10, y=1.13)
    assert model.to_dict() == {"x": 10, "y": 1.13}


def test_serialize_nested_object():
    model = Bar(foo=Foo(x=10, y=1.13), foos=[Foo(x=10, y=1.13), Foo(x=20, y=3.33)])
    assert model.to_dict() == {
        "foo": {"x": 10, "y": 1.13},
        "foos": [{"x": 10, "y": 1.13}, {"x": 20, "y": 3.33}],
    }


def test_build_from_obj():
    pydantic_foo = PydanticFoo(x=10, y=3.3)
    foo = Foo.from_obj(pydantic_foo)

    assert foo == Foo(x=10, y=3.3)


def test_build_from_dataclass():
    dataclass_foo = DataclassFoo(x=10, y=3.3)
    foo = Foo.from_obj(dataclass_foo)

    assert foo == Foo(x=10, y=3.3)


def test_build_from_list_of_obj():
    objs = [PydanticFoo(x=11, y=4.3), PydanticFoo(x=12, y=5.3), PydanticFoo(x=10, y=3.3)]
    foos = Foo.from_obj(objs)

    assert foos == [Foo(x=11, y=4.3), Foo(x=12, y=5.3), Foo(x=10, y=3.3)]


def test_build_from_dataclass_list():
    objs = [
        DataclassFoo(x=11, y=4.3),
        DataclassFoo(x=12, y=5.3),
        DataclassFoo(x=10, y=3.3),
    ]
    foos = Foo.from_obj(objs)

    assert foos == [Foo(x=11, y=4.3), Foo(x=12, y=5.3), Foo(x=10, y=3.3)]


def test_build_from_augmented_model():
    obj = AugmentedPydanticModel(x=10, y=3.3, other="Hello", another=False)
    foo = Foo.from_obj(obj)

    assert foo == Foo(x=10, y=3.3)


def test_nested_model():
    obj = PydanticNestedModel(
        foo=PydanticFoo(x=1, y=2), bar=PydanticBar(foo=PydanticFoo(x=1, y=2)), x=20
    )
    nested = NestedModel.from_obj(obj)

    assert nested == NestedModel(foo=Foo(x=1, y=2), bar=Bar(foo=Foo(x=1, y=2)), x=20)
