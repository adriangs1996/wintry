from dataclasses import dataclass, field, fields, is_dataclass
from functools import cache
from inspect import signature
from types import MethodType
from typing import Any, TypeVar
from pydantic import BaseModel
from dataclass_wizard import fromdict
from sqlalchemy.engine import LegacyCursorResult
from sqlalchemy.engine import LegacyRow
from sqlalchemy.ext.asyncio.engine import AsyncConnection
from sqlalchemy.sql.expression import BinaryExpression
from sqlalchemy import Table
from sqlalchemy.sql import Select
from sqlalchemy import select
from sqlalchemy import Column
from sqlalchemy.sql.operators import in_op


from wintry.models import Model, TableMetadata
from wintry.utils.virtual_db_schema import get_model_fields_names, get_model_sql_table
from wintry.utils.virtual_db_schema import get_model_table_metadata


class BindingError(Exception):
    pass


TModel = TypeVar("TModel", bound=Model)


@dataclass
class SQLJoinClause:
    table: Table
    on: BinaryExpression


@dataclass
class SQLSelectQuery:
    select: list[Table] = field(default_factory=list)
    joins: list[SQLJoinClause] = field(default_factory=list)

    def render(self) -> Select:
        stmt = select(*self.select)
        for join in self.joins:
            stmt = stmt.join(join.table, join.on, isouter=True)

        return stmt


def get_payload_type_for(method: MethodType):
    sig = signature(method)
    parameters = list(sig.parameters.values())
    assert (
        len(parameters) == 2
    ), "Event method should receive a single parameter, the shape of the payload"

    return parameters[1].annotation


def bind_payload_to(payload: dict[str, Any], _type: type):
    if is_dataclass(_type):
        return fromdict(_type, payload)
    elif issubclass(_type, BaseModel):
        return _type(**payload)
    else:
        raise Exception(f"{_type} is not instance of dataclass or pydantic.BaseModel")


@cache
def get_fks(metadata: TableMetadata) -> set[str]:
    return set(fk.key_name for fk in metadata.foreing_keys)


def bind_row_to_model(row: LegacyRow, model: type[Model], single: bool = False) -> Model:
    model_table = get_model_sql_table(model)
    model_table_metadata = get_model_table_metadata(model)
    model_fields = get_model_fields_names(model)
    fks_names = get_fks(model_table_metadata)
    fks = model_table.foreign_keys

    # Generate the canonical model from the row.
    # This means that the model is first populated
    # with non-relation fields, and relation fields
    # would get a default value.
    canonical_data: dict[str, Any] = {}
    for fk in model_table_metadata.foreing_keys:
        # We only load the object if the foreign key
        # populates a field in the model
        if fk.key_name in model_fields:
            if not single:
                fk_column = next(
                    filter(lambda fk_col: fk_col.parent.name == fk.key_name, fks)
                )
                if row[fk_column.parent] is not None:
                    # Models do not talk the foreign keys language
                    # they only do reference to other objects. So
                    # when our table has a fk configured, our model
                    # is expecting an object in there (or nothing at all)
                    # Either case, if an object is expected, we will give it one,
                    # else we just ignore that dict entry.
                    # For this to work, we build the model that this fk
                    # is pointing to from the row (the row contains all fields)
                    canonical_data[fk.key_name] = bind_row_to_model(
                        row, fk.target
                    ).to_dict()
                else:
                    canonical_data[fk.key_name] = None

            else:
                canonical_data[fk.key_name] = None

    # Map the columns to the their canonical values, i.e, the
    # "builtin" or "non-composed" ones.
    row_dict: Any = row._mapping  # type: ignore
    for column in model_table.c:
        if column.key not in fks_names:
            canonical_data[column.name] = row_dict[column]

    return model.build(canonical_data)


def tree_walk_dfs(model: type[Model], stmt: SQLSelectQuery):
    root_table = get_model_sql_table(model)
    metadata = get_model_table_metadata(model)
    model_fields = get_model_fields_names(model)

    stmt.select.append(root_table)

    for fk in metadata.foreing_keys:
        if fk.key_name in model_fields:
            target_id = fk.target.id_name()[0]
            next_model = fk.target
            target_table = get_model_sql_table(next_model)
            target_id_column = next(
                filter(lambda col: col.key == target_id, target_table.c)
            )
            fk_col = next(filter(lambda col: col.key == fk.key_name, root_table.c))
            stmt.joins.append(
                SQLJoinClause(table=target_table, on=fk_col == target_id_column)
            )
            tree_walk_dfs(next_model, stmt)


def bind_query_result_to_model(
    query_result: LegacyCursorResult, model: type[Model], single: bool = False
) -> list[Model]:
    models: list[Model] = []
    for row in query_result:
        models.append(bind_row_to_model(row, model, single))

    return models


async def load_model(
    model: type[Model], connection: AsyncConnection, where: BinaryExpression | None = None
) -> list[Model]:
    query = SQLSelectQuery()
    tree_walk_dfs(model, query)

    stmt = query.render()

    if where is not None:
        stmt = stmt.where(where)

    result: LegacyCursorResult = await connection.execute(stmt)
    models = bind_query_result_to_model(result, model)

    return models


def get_reverse_column_relation(related_table: Table, origin_fk: str) -> Column:
    for fk in related_table.foreign_keys:
        if fk.parent.name == origin_fk:
            return fk.parent

    raise BindingError(f"Reverse lookup of {related_table} for {origin_fk} failed")


async def load_many_to_one_related(
    model_instances: list[TModel], model: type[TModel], connection: AsyncConnection
):
    # Load the following case:
    #
    # class Address:
    #   id: int
    #
    # class User:
    #   addresses: list[Address] = []
    #
    # In this case, address list gets loaded into users

    table = get_model_table_metadata(model)

    # Compute the primary keys of the origin model
    pks = list(list(m.ids().values())[0] for m in model_instances)

    # Perform a select "IN" load for each many-to-one relation
    # in the origin model
    for relation in table.many_to_one_relations:
        # Load the related model
        related_model = relation.with_model
        related_table = get_model_sql_table(related_model)
        fk_column = get_reverse_column_relation(related_table, relation.field_name)
        related_models = await load_model(
            related_model, connection, where=in_op(fk_column, pks)
        )
