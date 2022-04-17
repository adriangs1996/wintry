from functools import partial, partialmethod
import inspect


class A:
    def partial_method(self, x: str, y: int):
        print(self.__class__, x, y)


class B:
    a: A = A()

    @classmethod
    def get_partial(cls, s: str):
        return partial(cls.a.partial_method, s)


def decorator(cls):
    members = inspect.getmembers(cls, inspect.isfunction)

    for fname, f in members:
        if fname == "test" or fname == "test_method":
            new_method = B.get_partial(fname)
            setattr(cls, fname, new_method)

    return cls

@decorator
class C:
    def test_method(self, y: int):
        print("This is from C: " + str(y))


c = C()
c.test_method(30)