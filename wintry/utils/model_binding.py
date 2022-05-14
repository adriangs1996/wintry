from dataclasses import is_dataclass
from inspect import signature
from types import MethodType
from typing import Any
from pydantic import BaseModel
from dataclass_wizard import fromdict


def get_payload_type_for(method: MethodType):
    sig = signature(method)
    parameters = list(sig.parameters.values())
    assert (
        len(parameters) == 2
    ), "Event method should receive a single parameter, the shape of the payload"

    return parameters[1].annotation


def bind_payload_to(payload: dict[str, Any], _type: type):
    if is_dataclass(_type):
        return fromdict(_type, payload)
    elif issubclass(_type, BaseModel):
        return _type(**payload)
    else:
        raise Exception(
            f"{_type} is not instance of dataclass or pydantic.BaseModel"
        )