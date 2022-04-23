from typing import Any, List, Optional
import pydantic as pdc
from sqlalchemy.orm import relation, aliased
from sqlalchemy import Column, Table, MetaData, Integer, ForeignKey, String, select, update, insert
from winter.orm import for_model, __mapper__
from sqlalchemy.orm import declarative_base, RelationshipProperty
from sqlalchemy import inspect
from operator import eq

Base = declarative_base()


metadata = MetaData()


class Address(pdc.BaseModel):
    street: str
    id: int
    user: Optional["User"] = None


class User(pdc.BaseModel):
    username: str
    password: str
    age: int
    id: int
    addresses: List[Address] = []


@for_model(Address)
class AddressSchema(Base):  # type: ignore
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    street = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))


@for_model(User)
class UserSchema(Base):  # type: ignore
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String)
    password = Column(String)
    age = Column(Integer)
    addresses = relation(AddressSchema, backref="user")


UserSchematics = __mapper__[User]
AddressSchematics = __mapper__[Address]


stmt = select(UserSchematics).where(eq(UserSchematics.username, "test")).subquery()
aliased_address = aliased(UserSchematics, stmt)
stmt = select(aliased_address)

user = User(username="test", password="secret", age=26, id=1, addresses=[Address(street="Test", id=2)])

stmt = update(UserSchema).values(**user.dict(exclude_unset=True, exclude={"addresses"}))
print(stmt)
