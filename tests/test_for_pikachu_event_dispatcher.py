import asyncio
from dataclasses import dataclass
import json
from typing import ClassVar
import pytest
import pytest_asyncio
import aio_pika
from wintry.controllers import microservice, on
from wintry.settings import (
    ConnectionOptions,
    TransporterSettings,
    TransporterType,
    WinterSettings,
)
from wintry.transporters.pikachu import Pikachu
from wintry.transporters.service_container import ServiceContainer


@dataclass
class ChanelPayload:
    result: int


@microservice(TransporterType.amqp)
class PikachuMicroservice:
    result: ClassVar[int] = 0

    @on("channel")
    async def handle_channel(self, data: ChanelPayload):
        PikachuMicroservice.result = data.result


@pytest_asyncio.fixture(scope="module", autouse=True)
async def container():
    service_container = ServiceContainer(
        WinterSettings(
            transporters=[
                TransporterSettings(
                    transporter=TransporterType.amqp,
                    driver="wintry.transporters.pikachu",
                    service="Pikachu",
                    connection_options=ConnectionOptions(url="amqp://localhost"),
                )
            ]
        )
    )

    service_container.add_service(Pikachu)
    service_container.start_services()
    yield service_container
    await service_container.close()


@pytest.mark.asyncio
@pytest.mark.skip
async def test_pikachu_handle_event():
    connection = await aio_pika.connect_robust("amqp://localhost/")

    async with connection:
        # Creating a channel
        channel = await connection.channel()

        # Declaring queue
        queue = await channel.declare_queue("channel")

        await channel.default_exchange.publish(
            aio_pika.Message(json.dumps({"result": 10}).encode()),
            routing_key=queue.name,
        )

    await asyncio.sleep(1)

    assert PikachuMicroservice.result == 10
