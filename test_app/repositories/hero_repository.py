from winter.repository import Repository
from winter.dependency_injection import provider
from test_app.models.hero import Hero


@provider
class HeroRepository(Repository[Hero, str], entity=Hero, mongo_session_managed=True):
    async def get_by_name(self, *, name: str) -> Hero | None:
        ...
