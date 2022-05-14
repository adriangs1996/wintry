from dataclasses import is_dataclass
from inspect import iscoroutinefunction, signature
import json
from types import MethodType
from typing import Any
import aioredis
from wintry.controllers import TransportControllerRegistry
from wintry.settings import TransporterType, WinterSettings
from wintry.transporters import Microservice
import async_timeout
import asyncio
from pydantic import BaseModel
from dataclass_wizard import fromdict


class RedisError(Exception):
    pass


class RedisModelBindingError(Exception):
    pass


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
        raise RedisModelBindingError(
            f"{_type} is not instance of dataclass or pydantic.BaseModel"
        )


class RedisMicroservice(Microservice):
    transporter: TransporterType = TransporterType.redis

    def __init__(self, settings: WinterSettings) -> None:
        for config in settings.transporters:
            if config.transporter == self.transporter:
                self.settings = config
                break
            else:
                raise RedisError("Redis transporter is not configured")

    def init(self) -> None:
        if self.settings.connection_options.url is None:
            assert self.settings.connection_options.host is not None
            host = self.settings.connection_options.host
            url = f"redis://{host}"
        else:
            url = self.settings.connection_options.url
        password = self.settings.connection_options.password
        if password is not None:
            self.client = aioredis.from_url(url, password=password, decode_responses=True)
        else:
            self.client = aioredis.from_url(url, decode_responses=True)

        self.ps = self.client.pubsub()

    async def run(self):
        service = TransportControllerRegistry.get_controller_for_transporter(
            self.transporter
        )

        if service is None:
            raise RedisError("No Service for this transporter")

        events = TransportControllerRegistry.get_events_for_transporter(service)

        channels = list(events.keys())
        if not channels:
            raise RedisError("There is no channels")

        await self.ps.subscribe(*channels)

        while True:
            try:
                async with async_timeout.timeout(1):
                    message = await self.ps.get_message(ignore_subscribe_messages=True)
                    if message is not None:
                        event: str = message["channel"]
                        data: dict = json.loads(message["data"])
                        handler = events.get(event, None)
                        if handler is not None:
                            # Services would use autoparams for DI
                            # so we call it without parameters
                            _self = service()
                            _type = get_payload_type_for(handler)
                            model_binded = bind_payload_to(data, _type)
                            if iscoroutinefunction(handler):
                                await handler(_self, model_binded)
                            else:
                                handler(_self, model_binded)
            except asyncio.TimeoutError:
                pass
