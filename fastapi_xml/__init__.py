"""
This packaged adds xml support to :mod:`fastapi`.
"""

from .nonjson import NonJsonRoute, NonJsonResponse
from .xmlbody import XmlResponse, XmlTextResponse, XmlAppResponse, XmlBody

__all__ = [
    "nonjson",
    "xmlbody",
    "NonJsonResponse",
    "NonJsonRoute",
    "XmlResponse",
    "XmlTextResponse",
    "XmlAppResponse",
    "XmlBody"
]

__version__ = "1.0.0a1"