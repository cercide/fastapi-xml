from typing import Any
from typing import Callable
from typing import ClassVar
from typing import Dict
from typing import Optional

from fastapi.responses import JSONResponse
from xsdata.formats.dataclass.serializers import XmlSerializer

from .decoder import DEFAULT_XML_CONTEXT

__all__ = [
    "XmlResponse",
    "XmlAppResponse",
    "XmlTextResponse",
]

NS_MAP: Dict[Optional[str], str] = {}


class XmlResponse(JSONResponse):
    """fastapi.openapi.utils.get_openapi_path does not support any
    response_schema except for JSONResponse:"""

    media_type: str = "application/xml"
    xml_serializer_factory: ClassVar[
        Callable[[], XmlSerializer]
    ] = lambda: XmlSerializer(context=DEFAULT_XML_CONTEXT)
    serializer: ClassVar[Optional[XmlSerializer]] = None

    @classmethod
    def get_serializer(cls) -> XmlSerializer:
        """
        The get_serializer function is a class method that returns an instance
        of the XmlSerializer class. The first time it is called, it creates an
        instance and stores it in the serializer attribute of the class.
        Subsequent calls return this same object.

        :return: The serializer for the class
        """
        if cls.serializer is None:
            cls.serializer = cls.xml_serializer_factory()
        return cls.serializer

    def render(self, content: Any) -> bytes:
        """
        The render function is responsible for taking the content and
        serializing it into a string. The render function should return a bytes
        object, not a str.

        :param content: Any: Pass the data to be serialized
        :return: A xml serialized byte string
        """
        serializer = self.get_serializer()
        return serializer.render(content, ns_map=NS_MAP).encode("utf-8")


class XmlTextResponse(XmlResponse):
    media_type: str = "text/xml"


class XmlAppResponse(XmlResponse):
    media_type: str = "application/xml"
