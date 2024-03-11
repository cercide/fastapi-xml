#  type: ignore
import unittest
from dataclasses import dataclass
from dataclasses import field

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel

from fastapi_xml.decoder import XmlParser
from fastapi_xml.response import XmlResponse
from fastapi_xml.response import XmlSerializer
from fastapi_xml.xmlbody import XmlBody


class TestXmlResponse(unittest.TestCase):
    def setUp(self) -> None:
        """
        The setUp function is called before each test function.

        It creates a FastAPI app with two endpoints, one using a
        dataclass and the other not. The setUp function also stores the
        API routes in self.api_routes.
        """

        class NotADataclass(BaseModel):
            x: str

        @dataclass
        class Model:
            x: str = field(metadata={"type": "Element"})

        router = APIRouter()

        @router.get("/model")
        def endpoint_model(x: Model = XmlBody()) -> None:  # pragma: no cover
            """a dummy endpoint."""
            x.x = x.x

        @router.get("/dclazz")
        def endpoint_dclazz(x: NotADataclass = XmlBody()) -> None:  # pragma: no cover
            """a dummy endpoint."""
            x.x = x.x

        self.app = FastAPI()
        self.app.include_router(router)
        self.api_routes = [r for r in self.app.routes if isinstance(r, APIRoute)]

    def test_get_serializer(self) -> None:
        """The test_get_serializer function tests the
        :func:`fastapi_xml.xmlbody.XmlResponse.get_serializer` function The
        test checks if a serializer is returned and if it is an instance of
        XmlSerializer."""
        # a previous serializer might be available. Hence, backup and reset it
        current_serializer = XmlResponse.serializer
        XmlResponse.serializer = None

        # actual test
        serializer = XmlResponse.get_serializer()
        self.assertIsInstance(serializer, XmlSerializer)

        # reset to previous serializer
        XmlResponse.serializer = current_serializer

    def test_render(self) -> None:
        """
        The test_render function tests the
        :meth:`fastapi_xml.xmlbody.XmlResponse.render` method.

        It creates a dummy dataclass, instantiates it with a value for
        its only field, and validates that the render method odes return
        a byte string for bytestring. Next, the test validates that the
        serialized string deserializes the same datastructure.
        """

        @dataclass
        class Dummy:
            x: str = field(metadata={"type": "Element"})

        test_obj = Dummy(x="test")
        test_response = XmlResponse(content=test_obj)
        test_body = test_response.render(test_obj)
        self.assertIsInstance(test_body, bytes)

        parsed_obj = XmlParser().from_bytes(test_body, clazz=Dummy)
        self.assertIsInstance(parsed_obj, Dummy)
        self.assertEqual(parsed_obj.x, test_obj.x)
