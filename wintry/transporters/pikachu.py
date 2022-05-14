import asyncio
import functools
from inspect import iscoroutinefunction
import json
from wintry.controllers import TransportControllerRegistry
from wintry.settings import TransporterType, WinterSettings
from wintry.transporters import Microservice
from wintry.utils.model_binding import get_payload_type_for, bind_payload_to
import aio_pika


class PikachuError(Exception):
    pass


class Pikachu(Microservice):
    transporter: TransporterType = TransporterType.amqp

    def __init__(self, settings: WinterSettings) -> None:
        for config in settings.transporters:
            if config.transporter == self.transporter:
                self.settings = config
                break
        else:
            raise PikachuError(f"Not configured transporter for {self.transporter}")

    def init(self):
        service = TransportControllerRegistry.get_controller_for_transporter(
            self.transporter
        )

        if service is None:
            raise PikachuError("There is no service configured for this transporter")

        events_mapping = TransportControllerRegistry.get_events_for_transporter(service)
        events = list(events_mapping.keys())

        # Events are the queues from which we want to listen for messages
        self.queues = events
        self.handlers = events_mapping
        self.service = service

    async def run(self):
        url = self.settings.connection_options.url
        assert url is not None
        connection = await aio_pika.connect_robust(url)

        async with connection:
            ch = connection.channel()

            await ch.initialize()

            async def dispatch_handler(
                handler, message: aio_pika.abc.AbstractIncomingMessage
            ):
                data = json.loads(message.body)
                service = self.service()
                _type = get_payload_type_for(handler)
                model_binded = bind_payload_to(data, _type)
                if iscoroutinefunction(handler):
                    await handler(service, model_binded)
                else:
                    handler(service, model_binded)

            for queue in self.queues:
                q = await ch.declare_queue(queue)
                handler = self.handlers[queue]

                await q.consume(functools.partial(dispatch_handler, handler), no_ack=True)

            await asyncio.Future()
