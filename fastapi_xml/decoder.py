from dataclasses import asdict
from dataclasses import is_dataclass
from typing import Any
from typing import Callable
from typing import ClassVar
from typing import Dict
from typing import Optional

from fastapi._compat import ModelField
from starlette.requests import Request
from xsdata.exceptions import ParserError
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers import XmlParser

DEFAULT_XML_CONTEXT: XmlContext = XmlContext()

__all__ = ["BodyDecodeError", "XmlDecoder"]


class BodyDecodeError(ValueError):
    pass


class XmlDecoder:
    xml_parser_factory: ClassVar[Callable[[], XmlParser]] = lambda: XmlParser(
        context=DEFAULT_XML_CONTEXT
    )
    xml_parser: ClassVar[Optional[XmlParser]] = None

    @classmethod
    def get_parser(cls) -> XmlParser:
        """
        The get_parser function is a class method that returns an instance of
        the XmlParser class. The first time it is called, it creates an
        instance and stores it in the xml_parser attribute. Subsequent calls
        return this same object.

        :return: An instance of XmlParser
        """
        if cls.xml_parser is None:
            cls.xml_parser = cls.xml_parser_factory()
        return cls.xml_parser

    @classmethod
    def decode(
        cls, request: Request, model_field: ModelField, body: bytes
    ) -> Optional[Dict[str, Any]]:
        """
        This method decodes an xml body.

        :param request: the original request
        :param model_field:   the model field to deal with
        :param body:    the original http body


        :return: The Decoder MUST return None, if the decoding failed for any reason.
                Else, it MUST return a mapping for pydantic's constructor
        """
        xml_parser = cls.get_parser()
        clazz = model_field.type_
        if not is_dataclass(clazz):
            return None

        try:
            result: object = xml_parser.from_bytes(body, clazz=clazz)
        except ParserError as e:
            raise BodyDecodeError(str(e)) from e
        else:
            return asdict(result)  # type: ignore
