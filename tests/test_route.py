# type: ignore
import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass
from dataclasses import field
from typing import Optional
from unittest import TestCase

from fastapi import APIRouter
from fastapi import Depends
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
        astack = AsyncExitStack()
        body: Optional[bytes] = None
        scope = {
            "method": "POST",
            "type": "http",
            "query_string": "",
            "headers": [(b"x", b"x")],
            "fastapi_middleware_astack": astack,
            "fastapi_inner_astack": astack,
            "fastapi_function_astack": astack,
        }
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

    def test_included_router(self) -> None:
        """Include-level prefix, dependencies and response class apply."""
        calls = []

        def dependency() -> None:
            calls.append(True)

        router = APIRouter(route_class=XmlRoute)

        @router.post("/echo")
        def endpoint(x: RequestModel = XmlBody()) -> ResponseModel:
            return ResponseModel(x=x.x)

        app = FastAPI()
        app.include_router(
            router,
            prefix="/api",
            dependencies=[Depends(dependency)],
            default_response_class=XmlAppResponse,
        )
        body = self.serializer.render(RequestModel(x="ping")).encode()
        status, headers, content = asyncio.run(self._asgi_post(app, "/api/echo", body))
        self.assertEqual(status, 200)
        self.assertEqual(calls, [True])
        self.assertEqual(
            headers.get(b"content-type"), XmlAppResponse.media_type.encode()
        )
        rsp_obj = self.parser.from_bytes(content, ResponseModel)
        self.assertEqual(rsp_obj.x, "ping")

    @staticmethod
    async def _asgi_post(app: FastAPI, path: str, body: bytes):
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "root_path": "",
            "query_string": b"",
            "headers": [(b"content-type", b"application/xml")],
        }
        messages = [{"type": "http.request", "body": body, "more_body": False}]
        sent = []

        async def receive():
            return messages.pop(0) if messages else {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        await app(scope, receive, send)
        start = next(m for m in sent if m["type"] == "http.response.start")
        content = b"".join(
            m.get("body", b"") for m in sent if m["type"] == "http.response.body"
        )
        return start["status"], dict(start["headers"]), content
