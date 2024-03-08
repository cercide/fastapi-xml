from dataclasses import Field
from dataclasses import fields
from dataclasses import is_dataclass
from types import MethodType
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Type
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.models import Components
from fastapi.openapi.models import Schema
from fastapi.openapi.models import XML
from fastapi.openapi.utils import get_fields_from_routes
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.utils import OpenAPI
from pydantic import TypeAdapter
from pydantic.dataclasses import dataclass as pydantic_dataclass
from xsdata.formats.dataclass.models.elements import XmlType

from .decoder import DEFAULT_XML_CONTEXT

OpenApiSchemaModifier = Callable[[FastAPI, OpenAPI, Optional[Mapping[str, Any]]], bool]
OPENAPI_SCHEMA_MODIFIER: List[OpenApiSchemaModifier] = []

if TYPE_CHECKING:  # pragma: nocover
    from pydantic.dataclasses import PydanticDataclass


def _get_element_name_generator(meta: "Type[object]") -> Callable[[str], str]:
    """
    The _get_element_name_generator function is a helper function that returns
    the element_name_generator attribute of the given config class, or if it
    does not exist, returns DEFAULT_XML_CONTEXT.element_name_generator. The
    element name generator is used to generate XML tag names for elements in an
    XML document.

    :param meta: a model xml configuration class
    :return: A function that takes a string and returns a string
    """
    return getattr(
        meta, "element_name_generator", DEFAULT_XML_CONTEXT.element_name_generator
    )


def _get_attribute_name_generator(meta: "Type[object]") -> Callable[[str], str]:
    """
    The _get_attribute_name_generator function is a helper function that
    returns the attribute_name_generator attribute of the given meta class, or
    if it does not exist, returns DEFAULT_XML_CONTEXT.attribute_name_generator.
    This allows for customizing how XML attributes are converted to Python
    object attributes.

    :param meta: the config meta class
    :return: A function that takes a string and returns a string
    """
    return getattr(
        meta, "attribute_name_generator", DEFAULT_XML_CONTEXT.attribute_name_generator
    )


def _add_model_schema(
    dclazz: Type[object], model_schema: Schema, ns_map: Mapping[str, str]
) -> None:
    """
    The _add_model_schema function adds an XML schema to the given model
    schema.

    :param dclazz: A dataclass for which an OpenAPI schema is created.
    :param model_schema: The current schema information for dclazz
    :param ns_map: Map the namespace to a prefix
    """
    model_meta = getattr(dclazz, "Meta", type)
    namespace = getattr(model_meta, "namespace", None)
    prefix = None if not isinstance(namespace, str) else ns_map.get(namespace)
    xml_schema = XML(
        name=getattr(model_meta, "name", dclazz.__name__),
        namespace=namespace,
        prefix=prefix,
        attribute=None,
        wrapped=None,
    )
    model_schema.xml = xml_schema


def _is_xml_schema_empty(xml_schema: XML) -> bool:
    """
    The _is_xml_schema_empty function is used to determine if an XML schema has
    been defined.

    :param xml_schema: The XML schema to check
    :return: True if the xml schema is empty
    """
    return (
        xml_schema.name is None
        and xml_schema.namespace is None
        and xml_schema.prefix is None
        and xml_schema.attribute is None
        and xml_schema.wrapped is None
    )


def _switch_ref_to_all_of(prop: Schema, xml_schema: XML) -> None:
    """
    The _switch_ref_to_all_of function is used to convert a property that has
    both an XML Schema and a $ref to one that uses allOf instead.

    This is necessary because the OpenAPI Specification does not allow
    for both an XML Schema and a $ref to be present on the same
    property. The _switch_ref_to_all_of function will take in a
    property, check if it has an XML Schema, and then create an allOf
    array with the original ref as its only item.
    """
    if not _is_xml_schema_empty(xml_schema):
        prop.xml = xml_schema
        if prop.ref is not None:
            prop.allOf = [Schema(**{"$ref": prop.ref})]  # type: ignore
            prop.ref = None


def _add_field_schema(
    dclazz: Type[object],
    model_field: Field[Any],
    model_schema: Schema,
    ns_map: Mapping[str, str],
) -> None:
    """
    The _add_field_schema function is responsible for adding the XML schema
    information to a dataclass model schema. This function adjust the schema
    based on the given data field.

    :param dclazz: A dataclass for which an OpenAPI schema is created.
    :param model_field: The data field currently in focus.
    :param model_schema: Schema: Pass the schema of for dclazz.
    :param ns_map: Map a namespace to a prefix
    """
    if model_schema.properties is None:
        return

    model_meta = getattr(dclazz, "Meta", type)
    prop = model_schema.properties[model_field.name]
    assert isinstance(prop, Schema)

    namespace = model_field.metadata.get("namespace")
    is_attribute = model_field.metadata.get("type") == XmlType.ATTRIBUTE
    meta_name = model_field.metadata.get("name")
    wrapper_name = model_field.metadata.get("wrapper")
    prefix = None if not isinstance(namespace, str) else ns_map.get(namespace)
    name_gen = (
        _get_attribute_name_generator(model_meta)
        if is_attribute
        else _get_element_name_generator(model_meta)
    )

    if wrapper_name is None:
        field_name = name_gen(meta_name) if meta_name is not None else None
        array_name = None
    else:
        field_name = name_gen(wrapper_name)
        array_name = name_gen(meta_name) if meta_name is not None else None

    if wrapper_name is not None and prop.type != "array":
        raise TypeError(
            f"invalid wrapping type on {dclazz.__name__}.{model_field.name}: "
            f"{prop.type}"
        )

    xml_schema = XML(
        name=field_name,
        namespace=namespace,
        prefix=prefix,
        attribute=is_attribute if is_attribute is True else None,
        wrapped=True if wrapper_name is not None else None,
    )
    if not _is_xml_schema_empty(xml_schema):
        prop.xml = xml_schema

    if prop.type == "array":
        if not isinstance(prop.items, Schema):
            raise TypeError(
                f"missing property items on {model_schema.title}.{model_field.name}"
            )
        _switch_ref_to_all_of(
            prop.items,
            XML(
                name=array_name,
                namespace=None,
                prefix=None,
                attribute=None,
                wrapped=None,
            ),
        )


def _get_route_models(
    app: FastAPI, openapi: OpenAPI
) -> List[Type["PydanticDataclass"]]:
    """
    The _get_route_models function is used to get the Pydantic models that are
    defined in the OpenAPI schema.

    :param app: Access the routes of the api
    :param openapi: Get the schemas from the openapi object
    :return: A list of pydantic dataclasses that are used as route parameters or response bodies
    """
    if isinstance(openapi.components, Components) and isinstance(
        openapi.components.schemas, dict
    ):
        return [
            pydantic_dataclass(field.type_)
            for field in get_fields_from_routes(app.routes)
            if is_dataclass(field.type_)
            and field.type_.__name__ in openapi.components.schemas
        ]
    else:  # pragma: nocover
        return []


def add_openapi_xml_schema(
    app: FastAPI, openapi: OpenAPI, ns_map: Optional[Mapping[str, str]] = None
) -> bool:
    """
    The add_openapi_xml_schema function adds XML schema information to the
    OpenAPI document.

    :param app: Get the models from the routes
    :param openapi: Add the xml schema to the openapi object
    :param ns_map: Map xml namespaces to prefixes
    :return: True if it has added any schemas
    """
    if openapi.components is None or openapi.components.schemas is None:
        return False

    ns_map = ns_map or {}
    flat_models = _get_route_models(app, openapi)

    model_counter = 0
    field_counter = 0
    for model in flat_models:
        schema = Schema(
            **TypeAdapter(model).json_schema(
                by_alias=True, ref_template="#/components/schemas/{model}"
            )
        )
        openapi.components.schemas[model.__name__] = schema
        _add_model_schema(model, schema, ns_map)
        model_counter += 1

        for field in fields(model):
            _add_field_schema(model, field, schema, ns_map)
            field_counter += 1
    return model_counter > 0 and field_counter > 0


def _get_unmodified_openapi(app: FastAPI) -> OpenAPI:
    """
    .. testsetup::

        >>> from dataclasses import dataclass
        >>> from dataclasses import field
        >>> from fastapi_xml.xmlbody import XmlBody
        >>> from fastapi_xml.route import XmlRoute

        >>> app = FastAPI()
        >>> app.router.route_class = XmlRoute

        >>> @dataclass
        ... class Dummy:
        ...     x: str = field(metadata={"type": "Element"})
        ...
        >>> @app.router.post("/")
        ... def endpoint(x: Dummy = XmlBody()) -> None:  # pragma: nocover
        ...     pass

     .. doctest:: schema unchanged

        >>> a = app.openapi()
        >>> b = _get_unmodified_openapi(app).model_dump(exclude_none=True, by_alias=True)
        >>> assert a == b
    """
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
    )
    return OpenAPI(**openapi_schema)


def _extend_openapi(app: FastAPI, **extension_kwargs: Any) -> Dict[str, Any]:
    """
    .. testsetup::

        >>> from dataclasses import dataclass
        >>> from fastapi_xml.xmlbody import XmlBody
        >>> @dataclass
        ... class Dummy:
        ...     x: str
        >>> app = FastAPI()
        >>> @app.router.post("/")
        ... def endpoint(x: Dummy = XmlBody()) -> None:  # pragma: nocover
        ...     pass

     .. doctest:: predefined schema

        >>> predefined = dict()
        >>> app.openapi_schema = predefined
        >>> result = _extend_openapi(app)
        >>> assert id(result) == id(predefined)
        >>> app.openapi_schema = None

     .. doctest:: schema modification

        >>> openapi_unmodified = _get_unmodified_openapi(app)
        >>> openapi_modified   = _extend_openapi(app)
        >>> assert openapi_modified != openapi_unmodified
    """
    if app.openapi_schema is not None:
        return app.openapi_schema
    openapi = _get_unmodified_openapi(app)

    add_openapi_xml_schema(app, openapi, extension_kwargs)

    app.openapi_schema = jsonable_encoder(openapi, by_alias=True, exclude_none=True)
    return app.openapi_schema


def add_openapi_extension(app: FastAPI, **extension_kwargs: Any) -> None:
    """
    .. testsetup::

        >>> from fastapi import FastAPI
        >>> from dataclasses import dataclass
        >>> from fastapi_xml.xmlbody import XmlBody

     .. doctest::

        >>> app = FastAPI()
        >>> add_openapi_extension(app)
        >>> assert isinstance(app.openapi, MethodType)
        >>> assert app.openapi.__func__ == _extend_openapi
        >>> assert isinstance(app.openapi(), dict)
    """
    app.openapi = MethodType(_extend_openapi, app)  # type: ignore[method-assign]
