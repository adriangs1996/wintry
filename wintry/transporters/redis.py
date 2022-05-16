from inspect import iscoroutinefunction
import json
import aioredis
from wintry.controllers import TransportControllerRegistry
from wintry.settings import TransporterType, WinterSettings
from wintry.transporters import Microservice
import async_timeout
import asyncio
from wintry.utils.model_binding import bind_payload_to, get_payload_type_for


class RedisError(Exception):
    pass


class RedisModelBindingError(Exception):
    pass


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
                await asyncio.sleep(0.01)
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
            except asyncio.CancelledError:
                break