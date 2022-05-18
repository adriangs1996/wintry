import inspect
import http.client
from enum import Enum
from typing import Any, Sequence, Union
from fastapi.datastructures import DefaultPlaceholder
from fastapi.dependencies.utils import get_flat_dependant, get_flat_params
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.constants import (
    METHODS_WITH_BODY,
    REF_PREFIX,
    STATUS_CODES_WITH_NO_BODY,
)
from fastapi.openapi.models import OpenAPI
from fastapi.openapi.utils import (
    get_flat_models_from_routes,
    get_openapi_operation_metadata,
    get_openapi_operation_parameters,
    get_openapi_operation_request_body,
    get_openapi_path,
    get_openapi_security_definitions,
    status_code_ranges,
    validation_error_definition,
    validation_error_response_definition,
)
from fastapi.routing import APIRoute
from fastapi.utils import deep_dict_update
from pydantic import BaseModel
from pydantic.dataclasses import dataclass, is_builtin_dataclass
from pydantic.fields import ModelField
from pydantic.schema import (
    field_schema,
    get_flat_models_from_fields,
    get_flat_models_from_model,
    get_model_name_map,
    model_process_schema,
)
from pydantic.utils import lenient_issubclass
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

TypeModelOrEnum = Union[type["BaseModel"], type[Enum]]
TypeModelSet = set[TypeModelOrEnum]


__dataclasses_registry__: dict[type, type] = {}


def wintry_get_flat_models_from_field(
    field: ModelField, known_models: TypeModelSet
) -> TypeModelSet:
    flat_models: TypeModelSet = set()

    # Handle dataclass-based models
    if is_builtin_dataclass(field.type_):
        if (t := __dataclasses_registry__.get(field.type_, None)) is None:
            dc = field.type_
            field.type_ = dataclass(field.type_)
            __dataclasses_registry__[dc] = field.type_
        else:
            field.type_ = t
    field_type = field.type_
    if lenient_issubclass(getattr(field_type, "__pydantic_model__", None), BaseModel):
        field_type = field_type.__pydantic_model__
    if field.sub_fields and not lenient_issubclass(field_type, BaseModel):
        flat_models |= get_flat_models_from_fields(
            field.sub_fields, known_models=known_models
        )
    elif lenient_issubclass(field_type, BaseModel) and field_type not in known_models:
        flat_models |= get_flat_models_from_model(field_type, known_models=known_models)
    elif lenient_issubclass(field_type, Enum):
        flat_models.add(field_type)
    return flat_models


def wintry_get_flat_models_from_fields(
    fields: Sequence[ModelField], known_models: TypeModelSet
) -> TypeModelSet:
    flat_models: TypeModelSet = set()
    for field in fields:
        flat_models |= wintry_get_flat_models_from_field(field, known_models=known_models)
    return flat_models


def get_model_definitions(
    *,
    flat_models: set[Union[type[BaseModel], type[Enum]]],
    model_name_map: dict[Union[type[BaseModel], type[Enum]], str],
) -> dict[str, Any]:
    definitions: dict[str, dict[str, Any]] = {}

    for model in flat_models:
        m_schema, m_definitions, m_nested_models = model_process_schema(
            model, model_name_map=model_name_map, ref_prefix=REF_PREFIX
        )
        definitions.update(m_definitions)
        model_name = model_name_map[model]
        definitions[model_name] = m_schema
    return definitions


def wintry_get_flat_model_from_routes(
    routes: Sequence[BaseRoute],
) -> set[Union[type[BaseModel], type[Enum]]]:
    body_fields_from_routes: list[ModelField] = []
    responses_from_routes: list[ModelField] = []
    request_fields_from_routes: list[ModelField] = []
    callback_flat_models: set[Union[type[BaseModel], type[Enum]]] = set()
    for route in routes:
        if getattr(route, "include_in_schema", None) and isinstance(route, APIRoute):
            if route.body_field:
                assert isinstance(
                    route.body_field, ModelField
                ), "A request body must be a Pydantic Field"
                body_fields_from_routes.append(route.body_field)
            if route.response_field:
                responses_from_routes.append(route.response_field)
            if route.response_fields:
                responses_from_routes.extend(route.response_fields.values())
            if route.callbacks:
                callback_flat_models |= get_flat_models_from_routes(route.callbacks)
            params = get_flat_params(route.dependant)
            request_fields_from_routes.extend(params)

    flat_models = callback_flat_models | wintry_get_flat_models_from_fields(
        body_fields_from_routes + responses_from_routes + request_fields_from_routes,
        known_models=set(),
    )
    return flat_models


def wintry_get_openapi_path(
    *,
    route: APIRoute,
    model_name_map: dict[TypeModelOrEnum, str],
    operation_ids: set[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    path = {}
    security_schemes: dict[str, Any] = {}
    definitions: dict[str, Any] = {}
    assert route.methods is not None, "Methods must be a list"
    if isinstance(route.response_class, DefaultPlaceholder):
        current_response_class: type[Response] = route.response_class.value
    else:
        current_response_class = route.response_class
    assert current_response_class, "A response class is needed to generate OpenAPI"
    route_response_media_type: str | None = current_response_class.media_type
    if route.include_in_schema:
        for method in route.methods:
            operation = get_openapi_operation_metadata(
                route=route, method=method, operation_ids=operation_ids
            )
            parameters: list[dict[str, Any]] = []
            flat_dependant = get_flat_dependant(route.dependant, skip_repeats=True)
            security_definitions, operation_security = get_openapi_security_definitions(
                flat_dependant=flat_dependant
            )
            if operation_security:
                operation.setdefault("security", []).extend(operation_security)
            if security_definitions:
                security_schemes.update(security_definitions)
            all_route_params = get_flat_params(route.dependant)
            operation_parameters = get_openapi_operation_parameters(
                all_route_params=all_route_params, model_name_map=model_name_map
            )
            parameters.extend(operation_parameters)
            if parameters:
                operation["parameters"] = list(
                    {param["name"]: param for param in parameters}.values()
                )
            if method in METHODS_WITH_BODY:
                request_body_oai = get_openapi_operation_request_body(
                    body_field=route.body_field, model_name_map=model_name_map
                )
                if request_body_oai:
                    operation["requestBody"] = request_body_oai
            if route.callbacks:
                callbacks = {}
                for callback in route.callbacks:
                    if isinstance(callback, APIRoute):
                        (
                            cb_path,
                            cb_security_schemes,
                            cb_definitions,
                        ) = get_openapi_path(
                            route=callback,
                            model_name_map=model_name_map,
                            operation_ids=operation_ids,
                        )
                        callbacks[callback.name] = {callback.path: cb_path}
                operation["callbacks"] = callbacks
            if route.status_code is not None:
                status_code = str(route.status_code)
            else:
                # It would probably make more sense for all response classes to have an
                # explicit default status_code, and to extract it from them, instead of
                # doing this inspection tricks, that would probably be in the future
                # TODO: probably make status_code a default class attribute for all
                # responses in Starlette
                response_signature = inspect.signature(current_response_class.__init__)
                status_code_param = response_signature.parameters.get("status_code")
                if status_code_param is not None:
                    if isinstance(status_code_param.default, int):
                        status_code = str(status_code_param.default)
            operation.setdefault("responses", {}).setdefault(status_code, {})[  # type: ignore
                "description"
            ] = route.response_description
            if (
                route_response_media_type
                and route.status_code not in STATUS_CODES_WITH_NO_BODY
            ):
                response_schema = {"type": "string"}
                if lenient_issubclass(current_response_class, JSONResponse):
                    if route.response_field:
                        response_schema, _, _ = field_schema(
                            route.response_field,
                            model_name_map=model_name_map,
                            ref_prefix=REF_PREFIX,
                        )
                    else:
                        response_schema = {}
                operation.setdefault("responses", {}).setdefault(
                    status_code, {}  # type: ignore
                ).setdefault("content", {}).setdefault(route_response_media_type, {})[
                    "schema"
                ] = response_schema
            if route.responses:
                operation_responses = operation.setdefault("responses", {})
                for (
                    additional_status_code,
                    additional_response,
                ) in route.responses.items():
                    process_response = additional_response.copy()
                    process_response.pop("model", None)
                    status_code_key = str(additional_status_code).upper()
                    if status_code_key == "DEFAULT":
                        status_code_key = "default"
                    openapi_response = operation_responses.setdefault(status_code_key, {})
                    assert isinstance(
                        process_response, dict
                    ), "An additional response must be a dict"
                    field = route.response_fields.get(additional_status_code)
                    additional_field_schema: dict[str, Any] | None = None
                    if field:
                        additional_field_schema, _, _ = field_schema(
                            field, model_name_map=model_name_map, ref_prefix=REF_PREFIX
                        )
                        media_type = route_response_media_type or "application/json"
                        additional_schema = (
                            process_response.setdefault("content", {})
                            .setdefault(media_type, {})
                            .setdefault("schema", {})
                        )
                        deep_dict_update(additional_schema, additional_field_schema)
                    status_text: str | None = status_code_ranges.get(
                        str(additional_status_code).upper()
                    ) or http.client.responses.get(int(additional_status_code))
                    description = (
                        process_response.get("description")
                        or openapi_response.get("description")
                        or status_text
                        or "Additional Response"
                    )
                    deep_dict_update(openapi_response, process_response)
                    openapi_response["description"] = description
            http422 = str(HTTP_422_UNPROCESSABLE_ENTITY)
            if (all_route_params or route.body_field) and not any(
                [
                    status in operation["responses"]
                    for status in [http422, "4XX", "default"]
                ]
            ):
                operation["responses"][http422] = {
                    "description": "Validation Error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": REF_PREFIX + "HTTPValidationError"}
                        }
                    },
                }
                if "ValidationError" not in definitions:
                    definitions.update(
                        {
                            "ValidationError": validation_error_definition,
                            "HTTPValidationError": validation_error_response_definition,
                        }
                    )
            if route.openapi_extra:
                deep_dict_update(operation, route.openapi_extra)
            path[method.lower()] = operation
    return path, security_schemes, definitions


def wintry_get_openapi(
    *,
    title: str,
    version: str,
    openapi_version: str = "3.0.2",
    description: str | None = None,
    routes: Sequence[BaseRoute],
    tags: list[dict[str, Any]] | None = None,
    servers: list[dict[str, Union[str, Any]]] | None = None,
    terms_of_service: str | None = None,
    contact: dict[str, Union[str, Any]] | None = None,
    license_info: dict[str, Union[str, Any]] | None = None,
) -> dict[str, Any]:
    info: dict[str, Any] = {"title": title, "version": version}
    if description:
        info["description"] = description
    if terms_of_service:
        info["termsOfService"] = terms_of_service
    if contact:
        info["contact"] = contact
    if license_info:
        info["license"] = license_info
    output: dict[str, Any] = {"openapi": openapi_version, "info": info}

    if servers:
        output["servers"] = servers
    components: dict[str, dict[str, Any]] = {}
    paths: dict[str, dict[str, Any]] = {}
    operation_ids: set[str] = set()

    flat_models = wintry_get_flat_model_from_routes(routes)
    model_name_map = get_model_name_map(flat_models)
    definitions = get_model_definitions(
        flat_models=flat_models, model_name_map=model_name_map
    )
    for route in routes:
        if isinstance(route, APIRoute):
            result = wintry_get_openapi_path(
                route=route, model_name_map=model_name_map, operation_ids=operation_ids
            )
            if result:
                path, security_schemes, path_definitions = result
                if path:
                    paths.setdefault(route.path_format, {}).update(path)
                if security_schemes:
                    components.setdefault("securitySchemes", {}).update(security_schemes)
                if path_definitions:
                    definitions.update(path_definitions)
    if definitions:
        components["schemas"] = {k: definitions[k] for k in sorted(definitions)}
    if components:
        output["components"] = components
    output["paths"] = paths
    if tags:
        output["tags"] = tags
    return jsonable_encoder(OpenAPI(**output), by_alias=True, exclude_none=True)  # type: ignore
