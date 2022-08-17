from typing import Any, Tuple, Optional, List, Dict, Type, ClassVar, Set, Callable
from dataclasses import asdict, dataclass, is_dataclass, Field
from fastapi import Body
from fastapi.openapi.models import XML
from starlette.requests import Request
from pydantic.fields import ModelField, Undefined
from pydantic.schema import TypeModelSet, TypeModelOrEnum, default_ref_template
from pydantic import BaseModel
from xsdata.formats.dataclass.parsers import XmlParser, nodes
from xsdata.formats.dataclass.parsers.mixins import XmlNode
from xsdata.formats.dataclass.parsers.nodes import ElementNode
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.models.elements import XmlType
from xsdata.utils.constants import return_input
from xsdata.exceptions import ParserError

from .nonjson import BodyDecoder, BodyDecodeError, NonJsonResponse, OPENAPI_SCHEMA_MODIFIER


DEFAULT_XML_CONTEXT: XmlContext               = XmlContext()
NS_MAP:              Dict[Optional[str], str] = {}


@dataclass
class LessAccurateXmlParser(XmlParser):
    """Some xml protocols are less specific than others. This class aims towards protocols that are more flexible and
    extendable. The default parser :class:`XmlParser` fails to detect a proper dataclass for any child element if the
    parent does not specify the child's type itself, even though there is a matching dataclass. The default xml parser
    :class:`XmlParser` creates an instance of :class:`AnyElement` whenever this happens.

    This class addresses this issue by overloading the method :meth:`start`. The new method continues to look for
    matching dataclasses even though the parent element did not declare the child's object type.
    """

    @staticmethod
    def _get_child_node(parent: ElementNode, qname: str, attrs: Dict, ns_map: Dict, position: int) -> XmlNode:
        # this is a modified copy of :func:`xsdata.formats.dataclass.parsers.nodes.element.ElementNode.child`.
        # Repository: https://github.com/tefra/xsdata
        # xsdata's license is copied below.
        #
        # MIT License
        #
        # Copyright (c) 2021 Christodoulos Tsoulloftas
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
        for var in parent.meta.find_children(qname):
            # BEGIN EDIT
            var.clazz = var.clazz or parent.context.find_type(qname)
            # END EDIT
            unique = 0 if not var.is_element or var.list_element else var.index
            if not unique or unique not in parent.assigned:
                node = parent.build_node(var, attrs, ns_map, position)

                if node:
                    if unique:
                        parent.assigned.add(unique)

                    return node

        if parent.config.fail_on_unknown_properties:
            raise ParserError(f"Unknown property {parent.meta.qname}:{qname}")

        return nodes.SkipNode()

    def start(self, clazz: Optional[Type], queue: List[XmlNode], objects: List[Tuple[Optional[str], Any]], qname: str, attrs: Dict, ns_map: Dict):
        if len(queue) == 0:
            super().start(clazz, queue, objects, qname, attrs, ns_map)
            if len(queue) > 0 and qname != queue[0].meta.qname:
                raise ParserError("invalid root element")
        else:
            item  = queue[-1]
            assert isinstance(item, ElementNode)
            child = self._get_child_node(item, qname, attrs, ns_map, len(objects))
            queue.append(child)


class XmlDecoder(BodyDecoder):
    xml_parser_factory: ClassVar[Callable[[], XmlParser]] = lambda: LessAccurateXmlParser(context=DEFAULT_XML_CONTEXT)
    xml_parser:         ClassVar[Optional[XmlParser]]     = None

    @classmethod
    def decode(cls, request: Request, field: ModelField, body: bytes) -> Optional[Dict[str, Any]]:
        """
        This method decodes the body. Any Implementation must review if the body has the correct format. If not,
        this method MUST return None. For instance, an xml decoder is not capable to decode binary data. Hence, the
        xml decoder validates if the body is valid xml first, and proceeds decoding afterwards.

        :param request: the original request
        :param field:   the model field to deal with
        :param body:    the original http body

        :raises BodyDecodeError: if this is the correct decoder but the body is invalid for some reason.
                                 The error message should not contain sensible data since :meth:`run_decoder` will
                                 forward it.

        :return: The Decoder MUST return None, if the decoding failed for any reason.
                Else, it MUST return a mapping for pydantic's constructor
        """
        xml_parser = cls.xml_parser if cls.xml_parser is not None else cls.xml_parser_factory()
        try:
            o = xml_parser.from_bytes(body, clazz=field.type_)
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
    media_type:             ClassVar[str]                         = "application/xml"
    xml_serializer_factory: ClassVar[Callable[[], XmlSerializer]] = lambda: XmlSerializer(context=XmlContext())
    serializer:             ClassVar[Optional[XmlSerializer]]     = None

    def render(self, content: Any) -> bytes:
        clazz = type(self)
        serializer = clazz.serializer if clazz.serializer is not None else clazz.xml_serializer_factory()
        return serializer.render(content, ns_map=NS_MAP).encode("utf-8")


class XmlTextResponse(XmlResponse):
    media_type: ClassVar[str] = "text/xml"


class XmlAppResponse(XmlResponse):
    media_type: ClassVar[str] = "application/xml"


def XmlBody(default:     Any                      = Undefined, *,
            embed:       bool                     = False,
            media_type:  str                      = "application/xml",
            alias:       Optional[str]            = None,
            title:       Optional[str]            = None,
            description: Optional[str]            = None,
            gt:          Optional[float]          = None,
            ge:          Optional[float]          = None,
            lt:          Optional[float]          = None,
            le:          Optional[float]          = None,
            min_length:  Optional[int]            = None,
            max_length:  Optional[int]            = None,
            regex:       Optional[str]            = None,
            example:     Any                      = Undefined,
            examples:    Optional[Dict[str, Any]] = None,
            **extra:     Any
    ) -> Any:
    return Body(default,
                embed=embed,
                media_type=media_type,
                alias=alias, title=title,
                description=description,
                gt=gt,
                ge=ge,
                lt=lt,
                le=le,
                min_length=min_length,
                max_length=max_length,
                regex=regex,
                example=example,
                examples=examples, **extra)


def _get_dataclass(model: Type[BaseModel]) -> Optional[Type]:
    result = getattr(model, "__dataclass__", None)
    if result is None:
        # addressing https://github.com/pydantic/pydantic/issues/4353
        clazzes = [clazz for clazz in object.__subclasses__() if model.__name__ == clazz.__name__ and (model.__module__ == clazz.__module__ or model.__module__ in {"pydantic.dataclasses", "fastapi_xml.pydantic_dataclass_patch"}) and is_dataclass(clazz)]
        if len(clazzes) > 0:
            result = clazzes[0].__mro__[1] if is_dataclass(clazzes[0].__mro__[1]) else clazzes[0]
            model.__dataclass__ = result
    return result


def add_openapi_xml_schema(
    model: TypeModelOrEnum,
    *,
    schema: Dict[str, Any],
    definitions: Dict[str, Any],
    nested_models: Set[str],
    by_alias: bool = True,
    model_name_map: Dict[TypeModelOrEnum, str],
    ref_prefix: Optional[str] = None,
    ref_template: str = default_ref_template,
    known_models: TypeModelSet = None,
    field: Optional[ModelField] = None) -> None:

    dclazz:                   Type                 = _get_dataclass(model)
    meta:                     Type                 = getattr(dclazz, "Meta", type)
    element_name_generator:   Callable[[str], str] = DEFAULT_XML_CONTEXT.element_name_generator   if DEFAULT_XML_CONTEXT.element_name_generator   != return_input else getattr(meta, "element_name_generator",   return_input)
    attribute_name_generator: Callable[[str], str] = DEFAULT_XML_CONTEXT.attribute_name_generator if DEFAULT_XML_CONTEXT.attribute_name_generator != return_input else getattr(meta, "attribute_name_generator", return_input)
    rv_map = {} if NS_MAP is None else {v: k for k, v in NS_MAP.items()}
    namespace = getattr(meta, "namespace", None)
    schema["xml"] = XML(
            name      = getattr(meta, "name", None),
            namespace = namespace,
            prefix    = rv_map.get(namespace, None),
            attribute = None,
            wrapped   = None,
        )

    fields: Dict[str, Field] = getattr(dclazz, "__dataclass_fields__", {})
    for key, field in fields.items():
        is_attribute = field.metadata.get("type") == XmlType.ATTRIBUTE
        if is_attribute:
            name = attribute_name_generator(field.metadata.get("name", key))
        else:
            name = element_name_generator(field.metadata.get("name", key))

        schema["properties"][field.name]["xml"] = XML(
            name      = name,
            namespace = field.metadata.get("namespace"),
            prefix    = field.metadata.get("target_namespace"),
            attribute = is_attribute,
            wrapped   = None
        )


OPENAPI_SCHEMA_MODIFIER.append(add_openapi_xml_schema)

try:
    # https://github.com/pydantic/pydantic/issues/4353
    from .pydantic_dataclass_patch import pydantic_process_class_patched
except ImportError:
    # the patch does not work with the pydantic.dataclasses update (commit 576e4a3a8d9c98cbf5a1fe5149450febef887cc9)
    # no worries, that update works as it should and is compatible with fastapi-xml
    pass
else:
    import pydantic.dataclasses
    pydantic.dataclasses._process_class = pydantic_process_class_patched
