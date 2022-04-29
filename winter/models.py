from typing import Any, Callable, Tuple, TypeVar, Union, overload
from dataclasses import dataclass
from winter.utils.keys import (
    __winter_in_session_flag__,
    __winter_tracker__,
    __winter_track_target__,
    __winter_modified_entity_state__,
    __winter_old_setattr__,
)
from winter.sessions import MongoSessionTracker


T = TypeVar("T")


def __dataclass_transform__(
    *,
    eq_default: bool = True,
    order_default: bool = False,
    kw_only_default: bool = False,
    field_descriptors: Tuple[Union[type, Callable[..., Any]], ...] = (()),
) -> Callable[[T], T]:
    # If used within a stub file, the following implementation can be
    # replaced with "...".
    return lambda a: a


def _is_private_attr(attr: str):
    return attr.startswith("_")


@overload
@__dataclass_transform__()
def model(cls: type[T], /) -> type[T]:
    ...


@overload
@__dataclass_transform__()
def model(cls: None, /) -> Callable[[type[T]], type[T]]:
    ...


@overload
@__dataclass_transform__()
def model(
    *,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
    match_args=True,
    kw_only=False,
    slots=False,
) -> Callable[[type[T]], type[T]]:
    ...


@__dataclass_transform__()
def model(
    cls: type[T] | None = None,
    /,
    *,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
    match_args=True,
    kw_only=False,
    slots=False,
) -> type[T] | Callable[[type[T]], type[T]]:
    def make_proxy_ref(cls: type[T]) -> type[T]:
        """
        Transform the given class in a Tracked entity.

        Tracked entities are used to automatically synchronize
        database with entities actions. This is done pretty nicely
        by SQLAlchemy session, but Motor (PyMongo) does not have the same
        goodness. So we must hand code one. This function augment the
        given entity so whenever a non_private attribute is being set,
        it is added to the tracker Updated set, and when an entity is created,
        it is added to the tracker's Created set. This resembles a little bit
        the states transitions in SQLAlchemy, but it is a lot simpler.

        Augmentation should work at instance level so we do not poison
        the global class, ie, proxy should check for specific flags so we
        can act on the instance. Flags must not be added directly to the
        class to avoid race conditions.
        """

        def _winter_proxied_setattr_(self, __name: str, __value: Any) -> None:
            # Check for presence of some state flag
            # same as self.__winter_in_session_flag__
            if getattr(self, __winter_in_session_flag__, False) and not _is_private_attr(__name):
                # all instances marked with __winter_in_session_flag__ should be augmented with
                # a __winter_track_target__ which contains the tracker
                # being marked for a session and not contain the tracker is an error

                # leave it to fail if no tracker present
                tracker: MongoSessionTracker = getattr(self, __winter_tracker__)
                target = getattr(self, __winter_track_target__)

                # Check for modified flag, so we ensure that this object is addded just once
                modified = getattr(target, __winter_modified_entity_state__, False)

                if not modified:
                    tracker.add(target)
                    setattr(target, __winter_modified_entity_state__, True)

            return super(cls, self).__setattr__(__name, __value)  # type: ignore

        cls = dataclass(
            init=init,
            repr=repr,
            eq=eq,
            order=order,
            unsafe_hash=unsafe_hash,
            frozen=frozen,
            match_args=match_args,
            kw_only=kw_only,
            slots=slots,
        )(cls)

        # For each field in the dataclass, we recurse making a deep proxy ref
        # This is done at class creation, so not a big deal

        # save the old __setattr__ just in case. For future use
        setattr(cls, __winter_old_setattr__, cls.__setattr__)
        cls.__setattr__ = _winter_proxied_setattr_  # type: ignore
        return cls

    if cls is None:
        return make_proxy_ref
    else:
        return make_proxy_ref(cls)
