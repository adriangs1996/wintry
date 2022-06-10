from types import NoneType
from typing import Iterable, get_args


def discard_nones(iterable: Iterable[type]) -> list[type]:
    return list(filter(lambda x: x != NoneType, iterable))


class ModelError(Exception):
    pass

def resolve_generic_type_or_die(_type: type):
    """
    Get a simple or generic type and try to resolve it
    to the canonical form.

    Example:
    =======

    >>> resolve_generic_type_or_die(list[list[int | None]])
    >>> int

    Generic types can be nested, but this function aimed to resolve a table
    reference, so it must be constrained to at most 1 Concrete type or None.
    Like so, the following is an error:

    >>> resolve_generic_type_or_die(list[int | str])
    """

    # Base case, get_args(int) = ()
    concrete_types = get_args(_type)

    if not concrete_types:
        return _type

    # Ok, we got nested generics, maybe A | None
    # clean it up
    cleaned_types = discard_nones(concrete_types)

    # If we get a list with more than one element, then this was not
    # a single Concrete type  generic, so panic
    if len(cleaned_types) != 1:
        raise ModelError(
            f"Model cannot have a field configured for either {'or '.join(str(t) for t in cleaned_types)}"
        )

    return resolve_generic_type_or_die(cleaned_types[0])
