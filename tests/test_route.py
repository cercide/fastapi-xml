#  type: ignore
import asyncio
from dataclasses import dataclass
from dataclasses import field
from typing import Optional
from unittest import TestCase

from fastapi import FastAPI
from fastapi import Request
from fastapi.routing import APIRoute
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer

from fastapi_xml import XmlAppResponse
from fastapi_xml import XmlBody
from fastapi_xml.route import XmlRoute


@dataclass
class RequestModel:
    x: str = field(metadata={"type": "Element"})


@dataclass
class ResponseModel:
    x: str = field(metadata={"type": "Element"})


class FastAPITests(TestCase):
    def setUp(self) -> None:
        self.parser = XmlParser()
        self.serializer = XmlSerializer()

        self.app = FastAPI()
        router = self.app.router
        router.route_class = XmlRoute
        router.default_response_class = XmlAppResponse

    def test_same_model_io(self) -> None:
        path = "/same_model"
        rq_object = RequestModel(x="ping")

        @self.app.router.post(path, response_model=RequestModel)
        def endpoint(x: RequestModel = XmlBody()) -> RequestModel:
            self.assertIsInstance(x, RequestModel)
            self.assertEqual(type(x), RequestModel)
            self.assertEqual(x.x, "ping")
            return x

        self.app.openapi()

        route = [
            r
            for r in self.app.routes
            if isinstance(r, APIRoute) and r.path_regex.match(path)
        ][0]
        request_handler = route.get_route_handler()
        request = self._get_request(rq_object)
        response = asyncio.run(request_handler(request))
        self.assertEqual(
            response.headers.get("content-type"), XmlAppResponse.media_type
        )

        rsp_obj: RequestModel = self.parser.from_bytes(response.body)
        assert isinstance(rsp_obj, RequestModel)
        self.assertEqual(type(rsp_obj), RequestModel)
        self.assertEqual(rsp_obj.x, "ping")

    def _get_request(self, obj: Optional[object] = None) -> Request:
        body: Optional[bytes] = None
        scope = {"type": "http", "query_string": "", "headers": [(b"x", b"x")]}
        if obj is not None:
            scope["headers"] = [(b"content-type", b"application/xml")]
            body = self.serializer.render(obj).encode()

        request = Request(scope=scope)

        if isinstance(body, bytes):
            request._body = body
        return request

    def test_route(self) -> None:
        path = "/ping_pong"
        rq_object = RequestModel(x="ping")

        @self.app.router.post(path, response_model=ResponseModel)
        def endpoint(x: RequestModel = XmlBody()) -> ResponseModel:
            self.assertIsInstance(x, RequestModel)
            self.assertEqual(type(x), RequestModel)
            self.assertEqual(x.x, "ping")
            return ResponseModel(x="pong")

        route = [
            r
            for r in self.app.routes
            if isinstance(r, APIRoute) and r.path_regex.match(path)
        ][0]
        request_handler = route.get_route_handler()
        request = self._get_request(rq_object)
        response = asyncio.run(request_handler(request))
        self.assertEqual(
            response.headers.get("content-type"), XmlAppResponse.media_type
        )

        rsp_obj: ResponseModel = self.parser.from_bytes(response.body)
        assert isinstance(rsp_obj, ResponseModel)
        self.assertEqual(type(rsp_obj), ResponseModel)
        self.assertEqual(rsp_obj.x, "pong")
