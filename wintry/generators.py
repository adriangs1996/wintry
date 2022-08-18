from dataclasses import fields
from datetime import date, datetime
from enum import Enum
from types import GenericAlias
from typing import Any, ForwardRef
from uuid import UUID, uuid4

from wintry.utils.type_helpers import resolve_generic_type_or_die


builtin_types = {int, str, float, bool, datetime, date, Enum, UUID}


class CodeGenerator:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self._indents: int = 0

    def classmethod_(self, method_name: str, *args: str, **kwargs: str):
        self._add_line("@classmethod")
        self._add_line(
            f"def {method_name}(cls, {','.join(args)}, {','.join(f'{k}={v}' for k,v in kwargs.items())}):"
        )

    def method(self, method_name: str, *args: str, **kwargs: str):
        self._add_line(
            f"def {method_name}(self, {','.join(args)}, {','.join(f'{k}={v}' for k,v in kwargs.items())}):"
        )

    def _add_line(self, line: str):
        self.lines.append(" " * (self._indents * 4) + line)

    def indent(self):
        self._indents += 1
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        if self._indents > 0:
            self._indents -= 1

    def code(self):
        return "\n".join(self.lines)

    def reset(self):
        self.lines.clear()
        self._indents = 0

    def compile(self, globalns=globals(), localns=locals(), return_: bool = False):
        text = self.code()
        exec(text, globalns, localns)
        if return_:
            return text

    def model_from_orm(self, model: type, globs=globals(), locs=locals()):
        self.reset()
        self.classmethod_("from_orm", "obj")
        with self.indent():
            self._add_line("if obj is None:")
            with self.indent():
                self._add_line("return None")
            self._add_line("if isinstance(obj, list):")
            with self.indent():
                self._add_line("return [cls.from_orm(o) for o in obj]")
            for f in fields(model):
                if isinstance(f.type, GenericAlias) and f.type.__origin__ == list:
                    type_ = resolve_generic_type_or_die(f.type)

                    if isinstance(type_, str):
                        type_ = eval(type_, globs, locs)
                        type_ = resolve_generic_type_or_die(type_)

                    if type_ in builtin_types:
                        # If we got a list of builtin types, then just assign it
                        self._add_line(f"__{f.name} = getattr(obj, '{f.name}', [])")
                    else:
                        self._add_line(
                            f"__{f.name} = [{type_.__name__}.from_orm(o) for o in getattr(obj, '{f.name}', [])]"
                        )

                elif isinstance(f.type, str):
                    type_ = eval(f.type, globs, locs)
                    if isinstance(type_, GenericAlias) and type_.__origin__ == list:
                        type_ = resolve_generic_type_or_die(type_)
                        if isinstance(type_, str):
                            type_ = eval(type_, globs, locs)
                            type_ = resolve_generic_type_or_die(type_)
                        self._add_line(
                            f"__{f.name} = [{type_.__name__}.from_orm(o) for o in getattr(obj, '{f.name}')]"
                        )
                    else:
                        type_ = resolve_generic_type_or_die(type_)
                        self._add_line(
                            f"__{f.name} = {type_.__name__}.from_orm(getattr(obj, '{f.name}'))"
                        )
                elif isinstance(f.type, ForwardRef):
                    type_ = f.type.__forward_arg__
                    type_ = eval(type_, globs, locs)
                    if isinstance(type_, GenericAlias) and type_.__origin__ == list:
                        type_ = resolve_generic_type_or_die(type_)
                        if isinstance(type_, str):
                            type_ = eval(type_, globs, locs)
                            type_ = resolve_generic_type_or_die(type_)
                        self._add_line(
                            f"__{f.name} = [{type_.__name__}.from_orm(o) for o in getattr(obj, '{f.name}')]"
                        )
                    else:
                        self._add_line(
                            f"__{f.name} = {type_.__name__}.from_orm(getattr(obj, '{f.name}'))"
                        )
                elif not f.type in builtin_types:
                    type_ = resolve_generic_type_or_die(f.type)
                    if isinstance(type_, ForwardRef):
                        type_ = type_.__forward_arg__
                        type_ = eval(type_, globs, locs)
                    self._add_line(
                        f"__{f.name} = {type_.__name__}.from_orm(getattr(obj, '{f.name}'))"
                    )
                else:
                    self._add_line(f"__{f.name} = getattr(obj, '{f.name}')")
            self._add_line(
                f"return cls({','.join(f'{f.name}=__{f.name}' for f in fields(model))})"
            )
        self._add_line(f"setattr({model.__name__}, 'from_orm', from_orm)")

    def map_to(self, model: type, globs, locs):
        self.reset()
        self.method("map", "_dict")
        with self.indent():
            for field in fields(model):
                self._add_line(
                    f"if (value := _dict.get('{field.name}', Undefined)) is not Undefined:"
                )
                with self.indent():
                    # Here is where we directly set the new value
                    if (
                        isinstance(field.type, GenericAlias)
                        and field.type.__origin__ == list
                    ):
                        type_ = resolve_generic_type_or_die(field.type)
                        if isinstance(type_, str):
                            type_ = eval(type_, globs, locs)
                            type_ = resolve_generic_type_or_die(type_)
                        if type_ in builtin_types:
                            # If we got a list of builtin types, then just assign it
                            self._add_line(f"self.{field.name} =  _dict['{field.name}']")
                        else:
                            # If it is a list of custom objects, then we need to build
                            # each nested object and then assign the list
                            self._add_line(
                                f"self.{field.name} = [{type_.__name__}.build(o) for o in _dict['{field.name}']]"
                            )

                    elif isinstance(field.type, str):
                        type_ = eval(field.type, globs, locs)

                        if isinstance(type_, GenericAlias) and type_.__origin__ == list:
                            type_ = resolve_generic_type_or_die(type_)
                            if isinstance(type_, str):
                                type_ = eval(type_, globs, locs)
                                type_ = resolve_generic_type_or_die(type_)

                            if type_ in builtin_types:
                                # If we got a list of builtin types, then just assign it
                                self._add_line(
                                    f"self.{field.name} =  _dict['{field.name}']"
                                )

                            else:
                                # If it is a list of custom objects, then we need to build
                                # each nested object and then assign the list
                                self._add_line(
                                    f"self.{field.name} = [{type_.__name__}.build(o) for o in _dict['{field.name}']]"
                                )
                        else:
                            type_ = resolve_generic_type_or_die(type_)
                            if type_ in builtin_types:
                                # if a builtin type, then just assign it
                                self._add_line(
                                    f"self.{field.name} =  _dict['{field.name}']"
                                )

                            else:
                                # this is an object, so if it is not none, we go and updated it
                                # otherwise we create it and assign it
                                self._add_line(
                                    f"if self.{field.name} is not None and isinstance(self.{field.name}, Model):"
                                )
                                with self.indent():
                                    self._add_line(
                                        f"self.{field.name}.map(_dict['{field.name}'])"
                                    )
                                self._add_line(f"else:")
                                with self.indent():
                                    self._add_line(
                                        f"self.{field.name} = {type_.__name__}.build(_dict['{field.name}'])"
                                    )

                    elif isinstance(field.type, ForwardRef):
                        type_ = field.type.__forward_arg__
                        type_ = eval(type_, globs, locs)

                        if isinstance(type_, GenericAlias) and type_.__origin__ == list:
                            type_ = resolve_generic_type_or_die(type_)
                            if isinstance(type_, str):
                                type_ = eval(type_, globs, locs)
                                type_ = resolve_generic_type_or_die(type_)

                            if type_ in builtin_types:
                                # If we got a list of builtin types, then just assign it
                                self._add_line(
                                    f"self.{field.name} =  _dict['{field.name}']"
                                )

                            else:
                                # If it is a list of custom objects, then we need to build
                                # each nested object and then assign the list
                                self._add_line(
                                    f"self.{field.name} = [{type_.__name__}.build(o) for o in _dict['{field.name}']]"
                                )
                        else:
                            type_ = resolve_generic_type_or_die(type_)
                            if type_ in builtin_types:
                                # if a builtin type, then just assign it
                                self._add_line(
                                    f"self.{field.name} =  _dict['{field.name}']"
                                )

                            else:
                                # this is an object, so if it is not none, we go and updated it
                                # otherwise we create it and assign it
                                self._add_line(
                                    f"if self.{field.name} is not None and isinstance(self.{field.name}, Model):"
                                )
                                with self.indent():
                                    self._add_line(
                                        f"self.{field.name}.map(_dict['{field.name}'])"
                                    )
                                self._add_line(f"else:")
                                with self.indent():
                                    self._add_line(
                                        f"self.{field.name} = {type_.__name__}.build(_dict['{field.name}'])"
                                    )

                    elif field.type not in builtin_types:
                        type_ = resolve_generic_type_or_die(field.type)

                        if isinstance(type_, ForwardRef):
                            type_ = type_.__forward_arg__
                            type_ = eval(type_, globs, locs)

                        self._add_line(
                            f"if self.{field.name} is not None and isinstance(self.{field.name}, Model):"
                        )
                        with self.indent():
                            self._add_line(
                                f"self.{field.name}.map(_dict['{field.name}'])"
                            )
                        self._add_line(f"else:")
                        with self.indent():
                            self._add_line(
                                f"self.{field.name} = {type_.__name__}.build(_dict['{field.name}'])"
                            )

                    else:
                        self._add_line(f"self.{field.name} =  _dict['{field.name}']")

        self._add_line(f"setattr({model.__name__}, 'map', map)")


code_gen = CodeGenerator()
