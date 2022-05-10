from dataclasses import field
from wintry.models import Model
import pytest


class Foo(Model, mapped=False):
    x: int
    y: float


class Bar(Model, mapped=False):
    foo: Foo
    foos: list[Foo] = field(default_factory=list)


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
