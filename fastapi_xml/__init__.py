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

__version__ = "1.0.0a2"



nonjson.OPENAPI_SCHEMA_MODIFIER.append(xmlbody.add_openapi_xml_schema)

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
