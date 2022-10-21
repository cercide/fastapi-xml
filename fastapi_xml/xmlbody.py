from dataclasses import asdict
from dataclasses import Field
from dataclasses import fields
from dataclasses import is_dataclass
from typing import Any
from typing import Callable
from typing import ClassVar
from typing import Dict
from typing import Iterable
from typing import List
from typing import Mapping
from typing import Optional
from typing import Type
from typing import TYPE_CHECKING

from fastapi import Body
from fastapi import FastAPI
from fastapi.openapi.models import Components
from fastapi.openapi.models import OpenAPI
from fastapi.openapi.models import Schema
from fastapi.openapi.models import XML
from fastapi.openapi.utils import get_flat_models_from_routes
from pydantic import BaseModel
from pydantic.config import BaseConfig
from pydantic.dataclasses import create_model
from pydantic.dataclasses import gather_all_validators
from pydantic.fields import Field as PydanticField
from pydantic.fields import FieldInfo
from pydantic.fields import ModelField
from pydantic.fields import Required
from pydantic.fields import Undefined
from pydantic.typing import NoArgAnyCallable
from starlette.requests import Request
from xsdata.exceptions import ParserError
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.models.elements import XmlType
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer

from .nonjson import BodyDecodeError
from .nonjson import BodyDecoder
from .nonjson import NonJsonResponse

if TYPE_CHECKING:  # pragma: nocover
    from pydantic.dataclasses import Dataclass

DEFAULT_XML_CONTEXT: XmlContext = XmlContext()
NS_MAP: Dict[Optional[str], str] = {}


class XmlDecoder(BodyDecoder):
    xml_parser_factory: ClassVar[Callable[[], XmlParser]] = lambda: XmlParser(
        context=DEFAULT_XML_CONTEXT
    )
    xml_parser: ClassVar[Optional[XmlParser]] = None
    supported_content_type: ClassVar[Iterable[str]] = ["application/xml", "text/xml"]

    @classmethod
    def get_parser(cls) -> XmlParser:
        if cls.xml_parser is None:
            cls.xml_parser = cls.xml_parser_factory()
        return cls.xml_parser

    @classmethod
    def decode(
        cls, request: Request, model_field: ModelField, body: bytes
    ) -> Optional[Dict[str, Any]]:
        """
        This method decodes the body. Any Implementation must review if the
        body has the correct format. If not, this method MUST return None. For
        instance, an xml decoder is not capable to decode binary data. Hence,
        the xml decoder validates if the body is valid xml first, and proceeds
        decoding afterwards.

        :param request: the original request
        :param field:   the model field to deal with
        :param body:    the original http body

        :raises BodyDecodeError: if this is the correct decoder but the body is
                                 invalid for some reason. The error message should
                                 not contain sensible data since :meth:`run_decoder`
                                 will forward it.

        :return: The Decoder MUST return None, if the decoding failed for any reason.
                Else, it MUST return a mapping for pydantic's constructor

        .. testsetup::

            >>> from dataclasses import dataclass
            >>> from dataclasses import field
            >>> from fastapi.routing import APIRoute
            >>> from pydantic import BaseModel

            >>> class NotADataclazz(BaseModel):
            ...     x: str

            >>> @dataclass
            ... class Model:
            ...     x: str = field(metadata={"type": "Element"})

            >>> app = FastAPI()
            >>> @app.router.get("/model")
            ... def endpoint_model(x: Model = XmlBody()) -> None:  # pragma: no cover
            ...     pass

            >>> @app.router.get("/dclazz")
            ... def endpoint_dclazz(
            ...     x: NotADataclazz = XmlBody()
            ... ) -> None:  # pragma: no cover
            ...     pass

            >>> test_scope: Dict[str, Any] = {"type": "http", "query_string": ""}
            >>> api_routes = [r for r in app.routes if isinstance(r, APIRoute)]
            >>> route_dclazz = [r for r in api_routes if r.path == "/dclazz"][0]
            >>> route_model = [r for r in api_routes if r.path == "/model"][0]

        .. doctest:: decode body

            >>> test_scope["headers"] = [(b"content-type", b"text/xml")]
            >>> test_request = Request(scope=test_scope)
            >>> test_field = route_model.body_field
            >>> test_body = b"<Model><x>test</x></Model>"
            >>> test_result = XmlDecoder.decode(test_request, test_field, test_body)
            >>> assert isinstance(test_result, dict)
            >>> assert "x" in test_result
            >>> assert test_result["x"] == "test"

        .. doctest:: return None if body model is not a dataclazz

            >>> route = route_dclazz
            >>> test_scope["headers"] = []
            >>> test_request = Request(scope=test_scope)
            >>> test_field = route_dclazz.body_field
            >>> request = Request(scope=test_scope)
            >>> assert XmlDecoder.decode(request, test_field, b"") is None

        .. doctest:: raise BodyDecodeError on ParserError

            >>> test_field = route_model.body_field
            >>> test_scope["headers"] = [(b"content-type", b"text/xml")]
            >>> test_request = Request(scope=test_scope)
            >>> XmlDecoder.decode(test_request, test_field, b"invalid")
            Traceback (most recent call last):
            fastapi_xml.nonjson.BodyDecodeError: syntax error: line 1, column 0

        .. doctest:: Do not raise an BodyDecodeErrpr if HTTP content-type does not match

            >>> test_field = route_model.body_field
            >>> test_scope["headers"] = [(b"content-type", b"text/something-else")]
            >>> test_request = Request(scope=test_scope)
            >>> assert XmlDecoder.decode(test_request, test_field, b"invalid") is None

        .. doctest:: Do not raise an BodyDecodeErrpr if HTTP content-type is empty

            >>> test_field = route_model.body_field
            >>> test_scope["headers"] = []
            >>> test_request = Request(scope=test_scope)
            >>> assert XmlDecoder.decode(test_request, test_field, b"invalid") is None
        """
        xml_parser = cls.get_parser()
        clazz = model_field.type_
        if not is_dataclass(clazz):
            return None

        try:
            o: object = xml_parser.from_bytes(body, clazz=clazz)
        except ParserError as e:
            http_content_type: str = request.headers.get("content-type", "")
            if http_content_type.endswith("/xml"):
                raise BodyDecodeError(str(e)) from e
            else:
                return None
        else:
            return asdict(o)


BodyDecoder.register(XmlDecoder)


class XmlResponse(NonJsonResponse):
    media_type: str = "application/xml"
    xml_serializer_factory: ClassVar[
        Callable[[], XmlSerializer]
    ] = lambda: XmlSerializer(context=DEFAULT_XML_CONTEXT)
    serializer: ClassVar[Optional[XmlSerializer]] = None

    @classmethod
    def get_serializer(cls) -> XmlSerializer:
        """
        .. testsetup::

           >>> current_serializer = XmlResponse.serializer
           >>> XmlResponse.serializer = None

        .. doctest::

            >>> serializer = XmlResponse.get_serializer()
            >>> assert isinstance(serializer, XmlSerializer)

        .. testcleanup::

            >>> XmlResponse.serializer = current_serializer
        """
        if cls.serializer is None:
            cls.serializer = cls.xml_serializer_factory()
        return cls.serializer

    def render(self, content: Any) -> bytes:
        """
        .. testsetup::

            >>> from dataclasses import dataclass
            >>> from dataclasses import field

            >>> @dataclass
            ... class Dummy:
            ...     x: str = field(metadata={"type": "Element"})

        .. doctest::
            >>> serializer = XmlSerializer()
            >>> test_obj = Dummy(x="test")
            >>> test_response = XmlResponse(content=test_obj)
            >>> test_body = test_response.render(test_obj)
            >>> assert isinstance(test_body, bytes)
            >>> parsed_obj = XmlParser().from_bytes(test_body, clazz=Dummy)
            >>> assert isinstance(parsed_obj, Dummy)
            >>> assert parsed_obj.x == test_obj.x
        """
        serializer = self.get_serializer()
        return serializer.render(content, ns_map=NS_MAP).encode("utf-8")


class XmlTextResponse(XmlResponse):
    media_type: str = "text/xml"


class XmlAppResponse(XmlResponse):
    media_type: str = "application/xml"


def XmlBody(
    default: Any = Undefined,
    *,
    embed: bool = False,
    media_type: str = "application/xml",
    alias: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    gt: Optional[float] = None,
    ge: Optional[float] = None,
    lt: Optional[float] = None,
    le: Optional[float] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    regex: Optional[str] = None,
    example: Any = Undefined,
    examples: Optional[Dict[str, Any]] = None,
    **extra: Any,
) -> Any:
    return Body(
        default,
        embed=embed,
        media_type=media_type,
        alias=alias,
        title=title,
        description=description,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        min_length=min_length,
        max_length=max_length,
        regex=regex,
        example=example,
        examples=examples,
        **extra,
    )


def _get_all_dataclasses(type_: "Type[Any]" = object) -> List["Type[Any]"]:
    """
    .. testsetup::

        >>> from dataclasses import dataclass

    .. doctest::

        >>> @dataclass
        ... class TestModel:
        ...     x: str
        >>>
        >>> @dataclass
        ... class TestModelChild(TestModel):
        ...     x: str
        ...
        ...     @dataclass
        ...     class Embedded:
        ...         y: str
        >>>
        >>> all_dataclasses = set(_get_all_dataclasses())
        >>> assert len(all_dataclasses) > 2
        >>> assert TestModel in all_dataclasses
        >>> assert TestModelChild in all_dataclasses
        >>> assert TestModelChild.Embedded in all_dataclasses
    """
    result = [t for t in type_.__subclasses__() if is_dataclass(t)]
    for i in range(len(result)):
        result += _get_all_dataclasses(result[i])
    return result


def _get_dataclass(
    model: "Type[BaseModel]", all_dataclasses: List["Type[Any]"]
) -> Optional["Type[Any]"]:
    """
    .. testsetup::

        >>> from dataclasses import dataclass

    .. doctest::
        >>>
        ... class NoDataclass(BaseModel):
        ...     x: str

        >>> @dataclass
        ... class UniqueModelName:
        ...     x: str

        >>> pydantic_model = _create_pydantic_model_from_dataclass(
        ...     UniqueModelName
        ... )  # ignore: type
        >>> all_dataclazzes = _get_all_dataclasses()
        >>> dclazz = _get_dataclass(pydantic_model, all_dataclazzes)
        >>> assert dclazz == UniqueModelName
        >>> assert _get_dataclass(NoDataclass, all_dataclazzes) is None
    """
    result = getattr(model, "__dataclass__", None)
    if result is None:
        # addressing https://github.com/pydantic/pydantic/issues/4353
        choices = [
            clazz
            for clazz in all_dataclasses
            if model.__name__ == clazz.__name__ and model.__module__ == clazz.__module__
        ]
        choices = list(dict.fromkeys(choices))
        if len(choices) > 0:
            result = choices[0]
            setattr(model, "__dataclass__", result)  # noqa: B010
    return result


def _get_element_name_generator(meta: "Type[object]") -> Callable[[str], str]:
    """
    .. doctest::

        >>> class meta1:
        ...     element_name_generator = lambda x: "test"
        >>> class meta2:
        ...    pass

        >>> g = _get_element_name_generator(meta1)
        >>> assert g("x") == "test"
        >>> g = _get_element_name_generator(meta2)
        >>> assert g == DEFAULT_XML_CONTEXT.element_name_generator
    """
    return getattr(
        meta, "element_name_generator", DEFAULT_XML_CONTEXT.element_name_generator
    )


def _get_attribute_name_generator(meta: "Type[object]") -> Callable[[str], str]:
    """
    .. doctest::

        >>> class meta1:
        ...     attribute_name_generator = lambda x: "test"
        >>> class meta2:
        ...    pass

        >>> g = _get_attribute_name_generator(meta1)
        >>> assert g("x") == "test"
        >>> g = _get_attribute_name_generator(meta2)
        >>> assert g == DEFAULT_XML_CONTEXT.attribute_name_generator
    """
    return getattr(
        meta, "attribute_name_generator", DEFAULT_XML_CONTEXT.attribute_name_generator
    )


def _add_model_schema(
    dclazz: "Type[object]", model_schema: Schema, ns_map: Mapping[str, str]
) -> None:
    """
    .. testsetup::

        >>> from dataclasses import dataclass

    .. doctest::

        >>> @dataclass
        ... class Dummy:
        ...     class Meta:
        ...         name = "Foo"
        ...         namespace = "http://testns"
        ...     x: str

        >>> test_schema = Schema()
        >>> test_ns_map = {"http://testns": "bla"}
        >>> _add_model_schema(Dummy, test_schema, test_ns_map)
        >>> assert isinstance(test_schema.xml, XML)
        >>> assert test_schema.xml.name == Dummy.Meta.name
        >>> assert test_schema.xml.prefix == "bla"
        >>> assert test_schema.xml.namespace == "http://testns"
        >>> assert test_schema.xml.attribute is None
        >>> assert test_schema.xml.wrapped is None
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
    .. doctest::

        >>> xml = XML()
        >>> assert _is_xml_schema_empty(XML()) is True
        >>> assert _is_xml_schema_empty(XML(name="")) is False
        >>> assert _is_xml_schema_empty(XML(prefix="")) is False
        >>> assert _is_xml_schema_empty(XML(attribute=False)) is False
        >>> assert _is_xml_schema_empty(XML(wrapped=False)) is False
    """
    return (
        xml_schema.name is None
        and xml_schema.namespace is None
        and xml_schema.prefix is None
        and xml_schema.attribute is None
        and xml_schema.wrapped is None
    )


# TODO: doctest
# def _switch_ref_to_one_of(prop: Schema, xml_schema: XML) -> None:
#    if not _is_xml_schema_empty(xml_schema):
#        prop.xml = xml_schema
#        if prop.ref is not None:
#            prop.oneOf = [Schema(**{"$ref": prop.ref})]
#            prop.ref = None


def _switch_ref_to_all_of(prop: Schema, xml_schema: XML) -> None:
    """
    .. doctest:: empty xml.

        >>> test_prop = Schema()
        >>> test_xml = XML()
        >>> assert test_prop.xml is None
        >>> _switch_ref_to_all_of(test_prop, test_xml)
        >>> assert test_prop.xml is None
        >>> assert test_prop.allOf is None
        >>> assert test_prop.ref is None

    .. doctest:: non empty xml

        >>> test_prop = Schema()
        >>> test_xml = XML(name="x")
        >>> assert test_prop.xml is None
        >>> _switch_ref_to_all_of(test_prop, test_xml)
        >>> assert test_prop.xml is not None
        >>> assert id(test_prop.xml) == id(test_xml)
        >>> assert test_prop.allOf is None
        >>> assert test_prop.ref is None

    .. doctest:: test ref

        >>> test_prop = Schema(ref="test_ref")
        >>> test_xml = XML(name="x")
        >>> assert test_prop.xml is None
        >>> _switch_ref_to_all_of(test_prop, test_xml)
        >>> assert test_prop.xml is not None
        >>> assert id(test_prop.xml) == id(test_xml)
        >>> assert isinstance(test_prop.allOf, list)
        >>> assert len(test_prop.allOf) == 1
        >>> assert isinstance(test_prop.allOf[0], Schema)
        >>> assert test_prop.allOf[0].ref == "test_ref"
        >>> assert test_prop.ref is None
    """
    if not _is_xml_schema_empty(xml_schema):
        prop.xml = xml_schema
        if prop.ref is not None:
            prop.allOf = [Schema(**{"$ref": prop.ref})]
            prop.ref = None


_FILTER_XSDATA_METADATA = {"name", "type"}


def _filter_xsdata_metadata(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    """
    .. doctest::

        >>> test_value = {**{"key": "value"}, **{k: k for k in _FILTER_XSDATA_METADATA}}
        >>> test_result = _filter_xsdata_metadata(test_value)
        >>> assert all(k not in test_result for k in _FILTER_XSDATA_METADATA)
    """
    return {k: v for k, v in metadata.items() if k not in _FILTER_XSDATA_METADATA}


def _create_pydantic_model_from_dataclass(
    dc_cls: "Type[Dataclass]",
    config: "Type[Any]" = BaseConfig,
    dc_cls_doc: Optional[str] = None,
) -> "Type[BaseModel]":  # pragma: nocover
    # Repository: https://github.com/pydantic/pydantic
    # pydanics's license copy is blow.
    #
    # The MIT License (MIT)
    #
    # Copyright (c) 2017 - 2022 Samuel Colvin and other contributors
    #
    # Permission is hereby granted, free of charge, to any person obtaining a copy
    # of this software and associated documentation files (the "Software"), to deal
    # in the Software without restriction, including without limitation the rights
    # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    # copies of the Software, and to permit persons to whom the Software is
    # furnished to do so, subject to the following conditions:
    #
    # The above copyright notice and this permission notice shall be included in all
    # copies or substantial portions of the Software.
    #
    # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    # SOFTWARE.
    import dataclasses

    field_definitions: Dict[str, Any] = {}
    for field in dataclasses.fields(dc_cls):
        default: Any = Undefined
        default_factory: Optional[NoArgAnyCallable] = None
        field_info: FieldInfo

        if field.default is not dataclasses.MISSING:
            default = field.default
        elif field.default_factory is not dataclasses.MISSING:
            default_factory = field.default_factory
        else:
            default = Required

        if isinstance(default, FieldInfo):
            field_info = default
            dc_cls.__pydantic_has_field_info_default__ = True
        else:
            # BEGIN EDIT
            field_info = PydanticField(
                default=default,
                default_factory=default_factory,
                **_filter_xsdata_metadata(field.metadata),
            )
            # END EDIT
        field_definitions[field.name] = (field.type, field_info)

    validators = gather_all_validators(dc_cls)
    model: "Type[BaseModel]" = create_model(
        dc_cls.__name__,
        __config__=config,
        __module__=dc_cls.__module__,
        __validators__=validators,
        __cls_kwargs__={"__resolve_forward_refs__": False},
        **field_definitions,
    )
    model.__doc__ = dc_cls_doc if dc_cls_doc is not None else dc_cls.__doc__ or ""
    return model


def _add_field_schema(
    dclazz: "Type[object]",
    model_field: "Field[Any]",
    model_schema: Schema,
    ns_map: Mapping[str, str],
) -> None:
    """
    .. testsetup::

        >>> from dataclasses import field

    .. doctest:: empty properties

        >>> test_schema = Schema()
        >>> _add_field_schema(object, field(), test_schema, {})
        >>> assert len(test_schema.dict(exclude_none=True)) == 0
    """
    # TODO: complete doctest
    if model_schema.properties is None:
        return

    model_meta = getattr(dclazz, "Meta", type)
    prop = model_schema.properties[model_field.name]
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
    # TODO: oneof allOf pydantic referenced
    # _switch_ref_to_one_of(
    #    prop,
    #    XML(
    #        name=field_name,
    #        namespace=namespace,
    #        prefix=prefix,
    #        attribute=is_attribute if is_attribute is True else None,
    #        wrapped=True if wrapper_name is not None else None,
    #    ),
    # )

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


def _get_route_models(app: FastAPI, openapi: OpenAPI) -> List["Type[BaseModel]"]:
    """
    .. testsetup:

        >>> from dataclasses import dataclass

    .. doctest::

        >>> @dataclass
        ... class TestModel:
        ...     x: str

        >>> app = FastAPI()
        >>> @app.router.get("/", response_model=TestModel)
        ... def dummy_endpoint() -> None:  # pragma: no cover
        ...     pass

        >>> openapi = OpenAPI(**app.openapi())
        >>> models = _get_route_models(app, openapi)
        >>> assert len(models) == 1
        >>> assert issubclass(models[0], BaseModel)
        >>> assert models[0].__name__ == TestModel.__name__
    """
    return [
        model
        for model in get_flat_models_from_routes(app.routes)
        if isinstance(openapi.components, Components)
        and isinstance(openapi.components.schemas, dict)
        and model.__name__ in openapi.components.schemas
        and issubclass(model, BaseModel)
    ]


def add_openapi_xml_schema(
    app: FastAPI, openapi: OpenAPI, ns_map: Optional[Mapping[str, str]] = None
) -> bool:
    """
    .. testsetup::

        >>> from fastapi.openapi.models import Components
        >>> from dataclasses import dataclass

        >>> @dataclass
        ... class TestModel:
        ...     x: str

        >>> test_app = FastAPI()
        >>> @test_app.router.get("/", response_model=TestModel)
        ... def dummy_endpoint() -> None:  # pragma: no cover
        ...     pass

    .. doctest:: test schema modified

        >>> test_app.openapi_schema = None
        >>> test_openapi = OpenAPI(**test_app.openapi())
        >>> assert add_openapi_xml_schema(test_app, test_openapi) is True

    .. doctest:: Return None if components or its schemas are missing

        >>> test_openapi = OpenAPI(**test_app.openapi())
        >>> test_openapi.components = None
        >>> assert add_openapi_xml_schema(test_app, test_openapi) is False
        >>> test_openapi.components = Components()
        >>> assert add_openapi_xml_schema(test_app, test_openapi) is False
    """
    if openapi.components is None or openapi.components.schemas is None:
        return False

    ns_map = ns_map or {}
    flat_models = _get_route_models(app, openapi)
    all_dataclazzes = _get_all_dataclasses()

    model_counter = 0
    field_counter = 0
    for model in flat_models:
        dclazz = _get_dataclass(model, all_dataclazzes)
        if dclazz is not None:
            rewrite_model = _create_pydantic_model_from_dataclass(dclazz)
            model_schema = Schema(
                **rewrite_model.schema(
                    by_alias=True, ref_template="#/components/schemas/{model}"
                )
            )
            openapi.components.schemas[model.__name__] = model_schema
            if isinstance(model_schema, Schema):
                _add_model_schema(dclazz, model_schema, ns_map)
                model_counter += 1

                for field in fields(dclazz):
                    _add_field_schema(dclazz, field, model_schema, ns_map)
                    field_counter += 1
    return model_counter > 0 and field_counter > 0
