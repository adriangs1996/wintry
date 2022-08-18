"""
Tests in this file are specific to the proxy functionalities added to ODMantic,
I have no intent to tests ODMantic functionalities
"""
from typing import List, Optional

import pytest
from bson import ObjectId
from odmantic import Model, EmbeddedModel
from pytest_mock import MockerFixture

from wintry.repository.nosql import NosqlAsyncSession, ModelSessionProxy


def get_mock_with_override(func: str, mocker: MockerFixture):
    engine = mocker.MagicMock()
    session = NosqlAsyncSession(engine)
    find_mock = mocker.patch(
        f"wintry.repository.nosql.AIOEngine.{func}", mocker.AsyncMock()
    )

    return session, find_mock


@pytest.mark.asyncio
class TestAttributesChanges(object):
    @staticmethod
    async def test_mongo_context_tracks_shallow_attribute_change(mocker: MockerFixture):
        class MyModel(Model):
            name: str

        # arrange
        session, find_mock = get_mock_with_override("find_one", mocker)

        find_mock.return_value = MyModel(name="test")

        # act
        obj = await session.find_one(MyModel, MyModel.id == ObjectId())

        # assert
        find_mock.assert_called_once()

        assert obj is not None
        assert obj.id in session.transient
        obj.name = "test2"
        assert obj.id in session.dirty
        assert obj == MyModel(id=obj.id, name="test2")

    @staticmethod
    async def test_mongo_context_tracks_deep_attribute_change(mocker: MockerFixture):
        class MyModel1(EmbeddedModel):
            name: str

        class MyModel2(Model):
            name: str
            nested: MyModel1

        session, find_mock = get_mock_with_override("find_one", mocker)
        find_mock.return_value = MyModel2(name="test1", nested=MyModel1(name="test2"))

        obj = await session.find_one(MyModel2, MyModel2.id == ObjectId())
        assert obj is not None
        assert obj.id in session.transient
        obj.nested.name = "deep"

        find_mock.assert_called_once()
        assert obj.id in session.dirty
        assert obj.nested == MyModel1(name="deep")

    @staticmethod
    async def test_mongo_context_tracks_shallow_attribute_on_list_property(
        mocker: MockerFixture,
    ):
        class MyModel1(EmbeddedModel):
            name: str

        class MyModel2(Model):
            name: str
            nesteds: List[MyModel1]

        session, find_mock = get_mock_with_override("find_one", mocker)
        find_mock.return_value = MyModel2(name="test1", nesteds=[MyModel1(name="test2")])

        obj = await session.find_one(MyModel2, MyModel2.id == ObjectId())
        assert obj is not None
        assert obj.id in session.transient
        obj.nesteds[0].name = "deep"

        find_mock.assert_called_once()
        assert obj.id in session.dirty
        assert obj.nesteds == [MyModel1(name="deep")]

    @staticmethod
    async def test_mongo_context_tracks_shallow_builtin_attribute_on_list_property(
        mocker: MockerFixture,
    ):
        class MyModel1(EmbeddedModel):
            name: str
            builtins: List[int] = []

        class MyModel2(Model):
            name: str
            nesteds: List[MyModel1]

        session, find_mock = get_mock_with_override("find_one", mocker)
        find_mock.return_value = MyModel2(
            name="test1", nesteds=[MyModel1(name="test2", builtins=[1, 2, 3])]
        )

        obj = await session.find_one(MyModel2, MyModel2.id == ObjectId())
        assert obj is not None
        assert obj.id in session.transient
        obj.nesteds[0].builtins[1] = 20

        find_mock.assert_called_once()
        assert obj.id in session.dirty


@pytest.mark.asyncio
class TestListAttributesChanges(object):
    @staticmethod
    async def test_mongo_context_tracks_shallow_attribute_on_list_property(
        mocker: MockerFixture,
    ):
        class MyModel1(EmbeddedModel):
            name: str

        class MyModel2(Model):
            name: str
            nesteds: List[MyModel1] = []

        session, find_mock = get_mock_with_override("find_one", mocker)
        find_mock.return_value = MyModel2(name="test1")

        obj = await session.find_one(MyModel2, MyModel2.id == ObjectId())
        assert obj is not None
        assert obj.id in session.transient
        print(obj.nesteds)
        obj.nesteds.append(MyModel1(name="deep"))

        find_mock.assert_called_once()
        assert obj.id in session.dirty
        assert obj.nesteds == [MyModel1(name="deep")]
