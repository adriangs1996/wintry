class A:
    def __init__(self) -> None:
        self.x = 10

A._my_prop = 10

print(A._my_prop)

a = A()

print(a.__class__._my_prop)

class c(A):
    pass

print(c._my_prop)