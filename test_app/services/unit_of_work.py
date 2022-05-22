from wintry.transactions import UnitOfWork as WinterUnitOfWork
from wintry.ioc import provider
from test_app.repositories.hero_repository import HeroRepository


@provider
class UnitOfWork(WinterUnitOfWork):
    heroes: HeroRepository

    def __init__(self, heroes: HeroRepository) -> None:
        super().__init__(heroes=heroes)
