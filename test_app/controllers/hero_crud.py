from logging import Logger
from test_app.models.hero import Hero
from test_app.services.unit_of_work import UnitOfWork
from winter.controllers import controller, delete, get, post
from winter.responses import DataResponse
from winter.errors import NotFoundError
from test_app.views import HeroCreateModel, HeroViewModel
from winter.models import fromdict


@controller
class HeroesController:
    def __init__(self, uow: UnitOfWork, logger: Logger) -> None:
        self.uow = uow
        self.logger = logger

    @get("", response_model=DataResponse[list[HeroViewModel]])
    async def list_heroes(self):
        # no need for start a transaction here
        return DataResponse(data=await self.uow.heroes.find())

    @get("/hero/{name}", response_model=DataResponse[HeroViewModel])
    async def get_hero_by_name(self, name: str):
        hero = await self.uow.heroes.get_by_name(name=name)
        if hero is None:
            raise NotFoundError("Hero")

        return DataResponse(data=hero)

    @get("/{hero_id}/salute", response_model=DataResponse[str])
    async def get_hero_salute(self, hero_id: str):
        hero = await self.uow.heroes.get_by_id(id=hero_id)
        if hero is None:
            raise NotFoundError("Hero")
        return DataResponse(data=hero.salute())

    @get("/{hero_id}", response_model=DataResponse[HeroViewModel])
    async def get_hero_by_id(self, hero_id: str):
        hero = await self.uow.heroes.get_by_id(id=hero_id)
        if hero is None:
            raise NotFoundError("Hero")
        return DataResponse(data=hero)

    @post("", response_model=DataResponse[str])
    async def create_hero(self, hero_form: HeroCreateModel):
        hero = fromdict(Hero, hero_form.dict())

        async with self.uow:
            hero = await self.uow.heroes.create(entity=hero)
            await self.uow.commit()

        self.logger.info(f"Hero created: {hero}")
        return DataResponse(data=hero.id, message="Created")

    @delete("/{hero_id}", response_model=DataResponse[HeroViewModel])
    async def delete_hero(self, hero_id: str):
        async with self.uow:
            hero = await self.uow.heroes.get_by_id(id=hero_id)
            if hero is None:
                raise NotFoundError("Hero")

            await self.uow.heroes.delete_by_id(id=hero_id)
            await self.uow.commit()

        self.logger.info(f"Hero deleted: {hero}")
        return DataResponse(data=hero, message="Deleted")
