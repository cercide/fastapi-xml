"""This packaged adds xml support to :mod:`fastapi`."""
from . import nonjson
from . import xmlbody
from .nonjson import add_openapi_extension
from .nonjson import NonJsonResponse
from .nonjson import NonJsonRoute
from .xmlbody import XmlAppResponse
from .xmlbody import XmlBody
from .xmlbody import XmlResponse
from .xmlbody import XmlTextResponse

__all__ = [
    "nonjson",
    "xmlbody",
    "NonJsonResponse",
    "NonJsonRoute",
    "XmlResponse",
    "XmlTextResponse",
    "XmlAppResponse",
    "XmlBody",
    "add_openapi_extension",
]

__version__ = "1.0.0b1"

nonjson.OPENAPI_SCHEMA_MODIFIER.append(xmlbody.add_openapi_xml_schema)
