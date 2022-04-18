from typing import Any, Callable, List, Optional, Type, TypeVar
import inspect
from pydantic import BaseModel

from winter.backend import Backend


class RepositoryError(Exception):
    pass


T = TypeVar("T", bound=BaseModel)


def is_processable(method: Callable):
    return method.__name__ != "__init__" and not getattr(method, "_raw_method", False)


def get_type_annotation_for_entity(entity, fn):
    signature = inspect.signature(fn)
    return_annotation = signature.return_annotation

    if not (
        return_annotation is None
        or return_annotation == entity
        or return_annotation == List[entity]
        or return_annotation == int
    ):
        raise RepositoryError(f"Invalid Return type for function: {return_annotation}")

    return return_annotation


def map_result_to_entity(entity, return_annotation, result):
    if return_annotation == None:
        return None
    elif return_annotation == entity:
        if isinstance(result, dict):
            return entity(**result)
        else:
            return entity.from_orm(result)
    elif return_annotation == List[entity]:
        results = []
        for r in result:
            if isinstance(r, dict):
                results.append(entity(**r))
            else:
                results.append(entity.from_orm(r))
    else:
        return result


def repository(entity: Type[T], table_name: Optional[str] = None, dry: bool = False):
    target_name = table_name or f"{entity.__name__}s".lower()

    def _runtime_method_parsing(cls: Type):
        def _getattribute(self, __name: str):
            attr = super(cls, self).__getattribute__(__name)

            def wrapper(*args, **kwargs):
                return_annotation = get_type_annotation_for_entity(entity, attr)
                result = attr(*args, **kwargs)
                return map_result_to_entity(entity, return_annotation, result)

            async def async_wrapper(*args, **kwargs):
                return_annotation = get_type_annotation_for_entity(entity, attr)
                result = await attr(*args, **kwargs)
                return map_result_to_entity(entity, return_annotation, result)

            if inspect.isfunction(attr) and is_processable(attr) and not dry:
                if inspect.iscoroutinefunction(attr):
                    return async_wrapper
                else:
                    return wrapper
            else:
                return attr

        function_members = inspect.getmembers(cls, inspect.isfunction)

        for fname, fobject in function_members:
            if is_processable(fobject):
                if inspect.iscoroutinefunction(fobject):
                    new_method = Backend.run_async(fname, target_name, dry_run=dry)
                else:
                    new_method = Backend.run(fname, target_name, dry_run=dry)

                setattr(new_method, "_raw_method", True)
                setattr(cls, fname, new_method)
        cls.__getattribute__ = _getattribute

        return cls

    return _runtime_method_parsing


def raw_method(method: Callable):
    # annotate this function as a raw method, so it is ignored
    # by the engine
    setattr(method, "_raw_method", True)
    return method
