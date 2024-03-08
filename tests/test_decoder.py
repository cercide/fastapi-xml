#  type: ignore
import unittest
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Dict

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Request
from fastapi.routing import APIRoute
from pydantic import BaseModel

from fastapi_xml.decoder import BodyDecodeError
from fastapi_xml.decoder import XmlDecoder
from fastapi_xml.decoder import XmlParser
from fastapi_xml.xmlbody import XmlBody


class TestXmlDecoder(unittest.TestCase):
    def setUp(self) -> None:
        """
        The setUp function is called before each test function.

        It creates a FastAPI app with two endpoints, one using a
        dataclass and the other not.
        """

        class NotADataClazz(BaseModel):
            x: str

        @dataclass
        class Model:
            x: str = field(metadata={"type": "Element"})

        router = APIRouter()

        @router.get("/model")
        def endpoint_model(x: Model = XmlBody()) -> None:  # pragma: no cover
            """dummy endpoint."""
            pass

        @router.get("/dclazz")
        def endpoint_dclazz(x: NotADataClazz = XmlBody()) -> None:  # pragma: no cover
            """dummy endpoint."""
            pass

        self.app = FastAPI()
        self.app.include_router(router)
        self.api_routes = [r for r in self.app.routes if isinstance(r, APIRoute)]

    def test_get_parser(self) -> None:
        """
        The test_get_parser function tests the get_parser function in the
        XmlDecoder class.

        It asserts that an instance of XmlParser is returned.
        """
        result = XmlDecoder.get_parser()
        self.assertIsInstance(result, XmlParser)

    def test_decode__decode_body(self) -> None:
        """
        The function is responsible for evaluating the
        :meth:`fastapi_xml.XmlDecoder.decode` function. This function
        establishes a test environment, represented as a dictionary containing
        details related to an HTTP request.

        Within this test scope, it specifies the nature of the request (HTTP) and
        indicates the absence of query parameters in this specific instance.
        Furthermore, the scope includes headers, specifically one header titled "content-type"
        with the value "text/xml." This signifies the intention to transmit XML data to the
        API endpoint located at "/model/."

        Subsequently, the test proceeds to craft a Request object, utilizing the test scope
        as the input for its constructor method.
        """
        test_scope: Dict[str, Any] = {"type": "http", "query_string": ""}
        route_model = [r for r in self.api_routes if r.path == "/model"][0]
        test_scope["headers"] = [(b"content-type", b"text/xml")]
        test_request = Request(scope=test_scope)
        test_body = b"<Model><x>test</x></Model>"
        test_field = route_model.body_field
        test_result = XmlDecoder.decode(test_request, test_field, test_body)
        self.assertIsInstance(test_result, dict)
        self.assertTrue("x" in test_result)
        self.assertEqual(test_result["x"], "test")

    def test_decode__return_non_if_model_is_not_a_dataclass(self) -> None:
        """
        This function tests the :meth:`fastapi_xml.XmlDecoder.decode` method.

        It validates that the function returns `None` if the body is
        empty.
        """
        route_dclazz = [r for r in self.api_routes if r.path == "/dclazz"][0]
        test_scope = {"type": "http", "query_string": "", "headers": []}
        test_field = route_dclazz.body_field
        request = Request(scope=test_scope)
        self.assertIsNone(XmlDecoder.decode(request, test_field, b""))

    def test_decode__BodyDecodeError(self) -> None:
        """
        This function tests the :meth:`XmlDecoder.decode` function to ensure
        that it raises a BodyDecodeError if the content type is xml and an
        error occurs during decoding.

        Likewise, the test assures that no exception is thrown when the
        content type is not xml.
        """
        route_model = [r for r in self.api_routes if r.path == "/model"][0]
        test_field = route_model.body_field

        # raise error if content type is xml
        test_scope = {
            "type": "http",
            "query_string": "",
            "headers": [(b"content-type", b"text/xml")],
        }
        test_request = Request(scope=test_scope)
        self.assertRaises(
            BodyDecodeError, XmlDecoder.decode, test_request, test_field, b"invalid"
        )
