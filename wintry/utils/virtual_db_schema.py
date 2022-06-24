from dataclasses import fields
from functools import cache
from typing import Any
from wintry.models import Model
from wintry.models import VirtualDatabaseSchema
from wintry.models import TableMetadata
from sqlalchemy import Table
from wintry.utils.keys import __wintry_model_instance_phantom_fk__


@cache
def get_model_sql_table(model: type[Model]) -> Table:
    table = VirtualDatabaseSchema.sql_generated_tables[model]
    if table is None:
        raise Exception(f"Can not find virtual table for {model}.")
    return table


@cache
def get_model_table_metadata(model: type[Model]) -> TableMetadata:
    table = VirtualDatabaseSchema[model]
    if table is None:
        raise Exception(f"Can not find virtual table metadata for {model}.")
    return table


@cache
def get_model_fields_names(model: type[Model]) -> set[str]:
    return set(f.name for f in fields(model))


def normalize_data(
    model_instance: Model,
    model_fields: set[str],
    data: dict[str, Any],
    table: TableMetadata,
):
    # REPLACE foreing key objects in data with their
    # respective_model id
    for fk in table.foreing_keys:
        if fk.key_name in model_fields:
            related_model: Model = getattr(model_instance, fk.key_name)
            if related_model is not None:
                pk = list(related_model.ids().values())[0]
                # I will ignore composite keys for now and assume it only have
                # one pk
                data[fk.key_name] = pk
            yield related_model
        else:
            data[fk.key_name] = getattr(
                model_instance, __wintry_model_instance_phantom_fk__, {}
            ).get(fk.key_name, None)

    # Delete any many-to-one relation
    for relation in table.many_to_one_relations:
        if relation.field_name in data:
            data.pop(relation.field_name)


def compute_model_insert_values(model_instance: Model) -> dict[str, Any]:
    model_fields = get_model_fields_names(type(model_instance))
    table = get_model_table_metadata(type(model_instance))
    data = model_instance.to_dict(omit_none=True)

    normalize_data(model_instance, model_fields, data, table)

    return data


def serialize_for_update(model_instance: Model) -> dict[str, Any]:
    model_fields = get_model_fields_names(type(model_instance))
    table = get_model_table_metadata(type(model_instance))
    pks = model_instance.id_name()
    data = model_instance.to_dict()

    for pk in pks:
        data.pop(pk, None)

    for _ in normalize_data(model_instance, model_fields, data, table):
        pass

    return data


def mark_obj_used_by_sql(obj: Model):
    setattr(obj, "__wintry_obj_is_used_by_sql__", True)


def compute_model_related_data_for_insert(model_instance: Model) -> list[tuple[Table, dict[str, Any]]]:
    if model_instance is None:
        return []
    model_fields = get_model_fields_names(type(model_instance))
    table = get_model_table_metadata(type(model_instance))
    data = model_instance.to_dict()
    model_table = get_model_sql_table(type(model_instance))

    result: list[tuple[Table, dict[str, Any]]] = []


    for residual in normalize_data(model_instance, model_fields, data, table):
        result += compute_model_related_data_for_insert(residual)
    
    return [(model_table, data)] + result
