from wintry.repository import Repository
from wintry.ioc import provider
from test_app.models.hero import Hero


@provider
class HeroRepository(Repository[Hero, str], entity=Hero, mongo_session_managed=True):
    async def get_by_name(self, *, name: str) -> Hero | None:
        ...
