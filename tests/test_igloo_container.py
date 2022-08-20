from dataclasses import dataclass
from wintry import App
from wintry.controllers import controller, get
from wintry.ioc import provider, inject
from wintry.ioc.container import IGlooContainer
from wintry import Depends, Header
from wintry.controllers import __controllers__
from fastapi.testclient import TestClient

container = IGlooContainer()


def test_simple_ioc_provides_singletons_by_default():
    @provider(container=container, singleton=True)
    class Provider(object):
        pass

    @inject(container=container)
    class Consumer(object):
        def __init__(self, provider: Provider) -> None:
            self.provider = provider

    assert Consumer().provider == Consumer().provider  # type: ignore
    container.clear()


def test_provider_also_injects():
    @provider(container=container, singleton=True)
    class Provider(object):
        pass

    @provider(container=container)
    class Consumer(object):
        def __init__(self, provider: Provider) -> None:
            self.provider = provider

    assert Consumer().provider == Consumer().provider  # type: ignore

    container.clear()


def test_a_function_can_be_a_provider():
    class Interface(object):
        pass

    @provider(of=Interface, container=container, singleton=True)  # type: ignore
    def provider_():
        return Interface()

    @inject(container=container)
    class Consumer(object):
        def __init__(self, _provider: Interface) -> None:
            self.provider = _provider

    assert Consumer().provider == Consumer().provider  # type: ignore

    container.clear()


def test_a_function_can_be_injected():
    @provider(container=container)
    @dataclass
    class Interface(object):
        x: int = 20

    @inject(container=container)
    def injected(i: Interface):
        return i.x

    assert injected() == 20  # type: ignore
    container.clear()


def test_an_injected_function_can_be_overwritten_by_arguments():
    @provider(container=container)
    @dataclass
    class Interface(object):
        x: int = 20

    @inject(container=container)
    def injected(i: Interface):
        return i.x

    assert injected(Interface(x=10)) == 10
    container.clear()


def test_an_injected_class_can_be_overwritten_by_arguments():
    @provider(container=container)
    @dataclass
    class Interface(object):
        x: int = 20

    @inject(container=container)
    class Consumer(object):
        def __init__(self, i: Interface) -> None:
            self.x = i.x

    assert Consumer().x == 20  # type: ignore
    assert Consumer(Interface(10)).x == 10

    container.clear()


def test_nested_injection():
    @provider(container=container, singleton=True)
    class ServiceA(object):
        pass

    @provider(container=container, singleton=True)
    class ServiceB(object):
        def __init__(self, a: ServiceA) -> None:
            self.a = a

    @inject(container=container)
    class ServiceC(object):
        def __init__(self, b: ServiceB, a: ServiceA) -> None:
            self.b = b
            self.a = a

    c = ServiceC()  # type: ignore
    assert c.a == c.b.a

    container.clear()


def test_scoped_injection():
    @provider(singleton=False, container=container)
    class Provider(object):
        pass

    @inject(container=container)
    class Consumer(object):
        def __init__(self, provider: Provider) -> None:
            self.provider = provider

    assert Consumer().provider != Consumer().provider  # type: ignore
    container.clear()


def test_controllers_works_with_classical_injection():
    @provider(container=container)
    class Service(object):
        @staticmethod
        def do_something():
            return 10

    @controller(prefix="/some", container=container)
    class SomeController(object):
        service: Service

        @get("")
        async def run(self):
            return self.service.do_something()

    app = App()
    client = TestClient(app)

    response = client.get("/some")
    assert response.json() == 10

    container.clear()


def test_controllers_can_merge_fastapi_di_api_with_builtin_di():
    @dataclass
    class User(object):
        name: str
        password: str

    @provider(container=container)
    class UserService(object):
        @staticmethod
        def do_something_user(user: User):
            return user.name + " " + user.password

    @controller(container=container)
    class Controller(object):
        service: UserService
        # This should be populated on each request
        user: User = Depends()

        @get("/user")
        async def get_user(self):
            return self.user

        @get("/something")
        async def get_something(self):
            return self.service.do_something_user(self.user)

    app = App()
    client = TestClient(app)
    user = {"name": "Jon", "password": "Snow"}
    response = client.get("/user", params=user)
    assert response.json() == user

    response = client.get("/something", params=user)
    assert response.json() == "Jon Snow"

    container.clear()


def test_controller_handles_single_depends_from_fastapi():
    @dataclass
    class User(object):
        name: str
        password: str

    @controller(container=container)
    class Controller(object):
        # This should be populated on each request
        user: User = Depends()

        @get("/user2")
        async def get_user(self):
            return self.user

    app = App()
    client = TestClient(app)
    user = {"name": "Jon", "password": "Snow"}
    response = client.get("/user2", params=user)
    assert response.json() == user

    __controllers__.clear()
    container.clear()


def test_controller_handles_nested_fastapi_dependencies():
    def get_name(name: str = Header(...)):
        return name.capitalize()

    @dataclass(kw_only=True)
    class User(object):
        password: str
        name: str = Depends(get_name)

    @controller(container=container)
    class Controller(object):
        # This should be populated on each request
        user: User = Depends()

        @get("/user3")
        async def get_user(self):
            return self.user

    app = App()
    client = TestClient(app)
    user = {"name": "Jon", "password": "Snow"}
    response = client.get("/user3", params={"password": "Snow"}, headers={"name": "jon"})
    assert response.json() == user

    __controllers__.clear()
    container.clear()


def test_complex_dependencies():
    def get_name(name: str = Header(...)):
        return name.capitalize()

    @dataclass(kw_only=True)
    class User(object):
        password: str
        name: str = Depends(get_name)

    @provider(container=container)
    class UserService(object):
        @staticmethod
        def do_something_user(user: User):
            return user.name + " " + user.password

    @provider(container=container)
    class UserTextService(object):
        user_service: UserService

        def get_text_for_user(self, user: User):
            text = self.user_service.do_something_user(user)
            return text.swapcase()

    @controller(container=container)
    class Controller(object):
        service: UserTextService
        # This should be populated on each request
        user: User = Depends()

        @get("/user4")
        async def get_user(self):
            return self.user

        @get("/something1")
        async def get_something(self):
            return self.service.get_text_for_user(self.user)

    app = App()
    client = TestClient(app)
    user = {"name": "Jon", "password": "Snow"}

    response = client.get("/user4", params={"password": "Snow"}, headers={"name": "jon"})
    assert response.json() == user

    response = client.get(
        "/something1", params={"password": "Snow"}, headers={"name": "jon"}
    )
    assert response.json() == "jON sNOW"

    __controllers__.clear()
    container.clear()
