"""This packaged adds xml support to :mod:`fastapi`."""
from .openapi import add_openapi_extension
from .response import XmlAppResponse
from .response import XmlTextResponse
from .route import XmlRoute
from .xmlbody import XmlBody

__all__ = [
    "XmlRoute",
    "XmlTextResponse",
    "XmlAppResponse",
    "XmlBody",
    "add_openapi_extension",
]

__version__ = "1.1.0"
