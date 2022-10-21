import asyncio
import email.message
import json
import sys
import traceback
from abc import abstractmethod
from types import MethodType
from typing import Any
from typing import Callable
from typing import ClassVar
from typing import Coroutine
from typing import Dict
from typing import Iterable
from typing import List
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union

from fastapi import FastAPI
from fastapi import params
from fastapi.datastructures import Default
from fastapi.datastructures import DefaultPlaceholder
from fastapi.datastructures import FormData
from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import solve_dependencies
from fastapi.encoders import DictIntStrAny
from fastapi.encoders import jsonable_encoder
from fastapi.encoders import SetIntStr
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.utils import OpenAPI
from fastapi.routing import APIRoute
from fastapi.routing import run_endpoint_function
from fastapi.routing import serialize_response
from pydantic.error_wrappers import ErrorWrapper
from pydantic.fields import ModelField
from pydantic.fields import Undefined
from starlette.background import BackgroundTasks
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import Response

OpenApiSchemaModifier = Callable[[FastAPI, OpenAPI, Optional[Mapping[str, Any]]], bool]

OPENAPI_SCHEMA_MODIFIER: List[OpenApiSchemaModifier] = []


class BodyDecodeError(ValueError):
    pass


class NonJsonRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        return self.get_request_handler(
            dependant=self.dependant,
            body_field=self.body_field,
            status_code=self.status_code,
            response_class=self.response_class,
            response_field=self.secure_cloned_response_field,
            response_model_include=self.response_model_include,
            response_model_exclude=self.response_model_exclude,
            response_model_by_alias=self.response_model_by_alias,
            response_model_exclude_unset=self.response_model_exclude_unset,
            response_model_exclude_defaults=self.response_model_exclude_defaults,
            response_model_exclude_none=self.response_model_exclude_none,
            dependency_overrides_provider=self.dependency_overrides_provider,
        )

    @staticmethod
    async def _original_fastapi_body_decode(
        request: Request,
        is_body_form: bool,
        body_field: Optional[ModelField],
    ) -> Union[Dict[str, Any], FormData, None]:  # pragma: nocover
        # Repository: https://github.com/tiangolo/fastapi
        # fastapi's license copy is blow.
        #
        # The MIT License (MIT)
        #
        # Copyright (c) 2018 Sebastián Ramírez
        #
        # Permission is hereby granted, free of charge, to any person obtaining a copy
        # of this software and associated documentation files (the "Software"), to deal
        # in the Software without restriction, including without limitation the rights
        # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        # copies of the Software, and to permit persons to whom the Software is
        # furnished to do so, subject to the following conditions:
        #
        # The above copyright notice and this permission notice shall be included in
        # all copies or substantial portions of the Software.
        #
        # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
        # THE SOFTWARE.
        try:
            body: Any = None
            if body_field:
                if is_body_form:
                    body = await request.form()
                else:
                    body_bytes = await request.body()
                    if body_bytes:
                        json_body: Any = Undefined
                        content_type_value = request.headers.get("content-type")
                        if not content_type_value:
                            json_body = await request.json()
                        else:
                            message = email.message.Message()
                            message["content-type"] = content_type_value
                            if message.get_content_maintype() == "application":
                                subtype = message.get_content_subtype()
                                if subtype == "json" or subtype.endswith("+json"):
                                    json_body = await request.json()
                        if json_body != Undefined:
                            body = json_body
                        else:
                            body = body_bytes
        except json.JSONDecodeError as e:  # pragma: no cover
            raise RequestValidationError([ErrorWrapper(e, ("body", e.pos))], body=e.doc)
        except Exception as e:  # pragma: no cover
            raise HTTPException(
                status_code=400, detail="There was an error parsing the body"
            ) from e
        return body

    @staticmethod
    async def _original_fastapi_return_response(
        raw_response: Any,
        background_tasks: Optional[BackgroundTasks],
        sub_response: Response,
        is_coroutine: bool,
        actual_response_class: "Type[Response]",
        status_code: Optional[int] = None,
        response_field: Optional[ModelField] = None,
        response_model_include: Optional[Union[SetIntStr, DictIntStrAny]] = None,
        response_model_exclude: Optional[Union[SetIntStr, DictIntStrAny]] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
    ) -> Response:  # pragma: nocover
        # Repository: https://github.com/tiangolo/fastapi
        # fastapi's license copy is blow.
        #
        # The MIT License (MIT)
        #
        # Copyright (c) 2018 Sebastián Ramírez
        #
        # Permission is hereby granted, free of charge, to any person obtaining a copy
        # of this software and associated documentation files (the "Software"), to deal
        # in the Software without restriction, including without limitation the rights
        # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        # copies of the Software, and to permit persons to whom the Software is
        # furnished to do so, subject to the following conditions:
        #
        # The above copyright notice and this permission notice shall be included in
        # all copies or substantial portions of the Software.
        #
        # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
        # THE SOFTWARE.
        if isinstance(raw_response, Response):
            if raw_response.background is None:
                raw_response.background = background_tasks
            return raw_response

        response_data = await serialize_response(
            field=response_field,
            response_content=raw_response,
            include=response_model_include,
            exclude=response_model_exclude,
            by_alias=response_model_by_alias,
            exclude_unset=response_model_exclude_unset,
            exclude_defaults=response_model_exclude_defaults,
            exclude_none=response_model_exclude_none,
            is_coroutine=is_coroutine,
        )
        response_args: Dict[str, Any] = {"background": background_tasks}
        # If status_code was set, use it, otherwise use the default from the
        # response class, in the case of redirect it's 307
        if status_code is not None:
            response_args["status_code"] = status_code
        response = actual_response_class(response_data, **response_args)
        response.headers.raw.extend(sub_response.headers.raw)
        if sub_response.status_code:
            response.status_code = sub_response.status_code
        return response

    @staticmethod
    def _original_fastapi_prepare_request_handler(
        *,
        dependant: Dependant,
        body_field: Optional[ModelField],
        response_class: Union["Type[Response]", DefaultPlaceholder],
    ) -> Tuple[bool, bool, "Type[Response]"]:
        # Repository: https://github.com/tiangolo/fastapi
        #
        # The MIT License (MIT)
        #
        # Copyright (c) 2018 Sebastián Ramírez
        #
        # Permission is hereby granted, free of charge, to any person obtaining a copy
        # of this software and associated documentation files (the "Software"), to deal
        # in the Software without restriction, including without limitation the rights
        # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        # copies of the Software, and to permit persons to whom the Software is
        # furnished to do so, subject to the following conditions:
        #
        # The above copyright notice and this permission notice shall be included in
        # all copies or substantial portions of the Software.
        #
        # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
        # THE SOFTWARE.
        assert dependant.call is not None, "dependant.call must be a function"
        is_coroutine = asyncio.iscoroutinefunction(dependant.call)
        is_body_form = body_field is not None and isinstance(
            body_field.field_info, params.Form
        )
        if isinstance(response_class, DefaultPlaceholder):
            actual_response_class: "Type[Response]" = (
                response_class.value
            )  # pragma: no cover
        else:
            actual_response_class = response_class
        return is_coroutine, is_body_form, actual_response_class

    @staticmethod
    async def _original_fastapi_call_endpoint(
        *,
        request: Request,
        dependant: Dependant,
        is_coroutine: bool,
        body: Optional[Union[Dict[str, Any], FormData]],
        dependency_overrides_provider: Optional[Any] = None,
    ) -> Tuple[Any, Optional[BackgroundTasks], Response]:  # pragma: no cover

        # Repository: https://github.com/tiangolo/fastapi
        #
        # The MIT License (MIT)
        #
        # Copyright (c) 2018 Sebastián Ramírez
        #
        # Permission is hereby granted, free of charge, to any person obtaining a copy
        # of this software and associated documentation files (the "Software"), to deal
        # in the Software without restriction, including without limitation the rights
        # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        # copies of the Software, and to permit persons to whom the Software is
        # furnished to do so, subject to the following conditions:
        #
        # The above copyright notice and this permission notice shall be included in
        # all copies or substantial portions of the Software.
        #
        # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
        # THE SOFTWARE.
        solved_result = await solve_dependencies(
            request=request,
            dependant=dependant,
            body=body,
            dependency_overrides_provider=dependency_overrides_provider,
        )
        values, errors, background_tasks, sub_response, _ = solved_result
        if errors:
            raise RequestValidationError(errors, body=body)
        else:
            raw_response = await run_endpoint_function(
                dependant=dependant, values=values, is_coroutine=is_coroutine
            )
            return raw_response, background_tasks, sub_response

    @staticmethod
    async def _request_handler(
        *,
        request: Request,
        dependant: Dependant,
        is_body_form: bool,
        body_field: Optional[ModelField],
        is_coroutine: bool,
        actual_response_class: "Type[Response]",
        status_code: Optional[int] = None,
        response_field: Optional[ModelField] = None,
        response_model_include: Optional[Union[SetIntStr, DictIntStrAny]] = None,
        response_model_exclude: Optional[Union[SetIntStr, DictIntStrAny]] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        dependency_overrides_provider: Optional[Any] = None,
    ) -> Response:
        """
        .. testsetup::

            >>> from dataclasses import field
            >>> from dataclasses import is_dataclass
            >>> from dataclasses import dataclass
            >>> from fastapi_xml import XmlBody
            >>> from fastapi_xml import XmlAppResponse
            >>> from fastapi import FastAPI
            >>> from fastapi import Request
            >>> from pydantic.config import BaseConfig
            >>> from xsdata.formats.dataclass.parsers import XmlParser
            >>> from xsdata.formats.dataclass.serializers import XmlSerializer
            >>> current_decoder = BodyDecoder.__decoder__
            >>> current_decoder_map = BodyDecoder.__content_type__
            >>> BodyDecoder.__decoder__ = []
            >>> BodyDecoder.__content_type__ = {}

        .. doctest:: Test Scope

            >>> class TestResponse(NonJsonResponse):
            ...     media_type = "application/test"
            ...     def render(self, content: Any) -> bytes:
            ...        assert isinstance(content, Dummy)
            ...        return b'{"x": content.x}'

            >>> class TestDecoder(BodyDecoder):
            ...     supported_content_type = [TestResponse.media_type]
            ...
            ...     @classmethod
            ...     def decode(
            ...         cls, request: Request, field: ModelField, body: bytes
            ...     ) -> Optional[Dict[str, Any]]:
            ...         if body == b"raise BodyDecodeError":
            ...             raise BodyDecodeError("body decode exception test")
            ...         elif body == b"raise any":
            ...             raise Exception("something bad happened")
            ...         else:
            ...             return json.loads(body.decode())
            >>> BodyDecoder.register(TestDecoder)

            >>> @dataclass
            ... class Dummy:
            ...    x: str

            >>> def dummy_endpoint(x: Dummy) -> Dummy:
            ...     assert type(x) == Dummy
            ...     x.x = "success"
            ...     return x

            >>> test_scope = {
            ...     "type": "http",
            ...     "query_string": "",
            ...     "headers": [(b"content-type", TestResponse.media_type.encode())]
            ... }
            >>> model_field = ModelField(
            ...     name="x",
            ...     type_=Dummy,
            ...     model_config=BaseConfig,
            ...     class_validators=None
            ... )
            >>> test_dependant = Dependant(
            ...     body_params=[model_field],
            ...     call=dummy_endpoint,
            ... )

        .. doctest:: Test valid request

            >>> test_request = Request(scope=test_scope)
            >>> test_request._body = b'{"x": "test"}'
            >>> test_rq_handler = NonJsonRoute._request_handler(
            ...     dependant=test_dependant,
            ...     request=test_request,
            ...     is_coroutine=False,
            ...     is_body_form=False,
            ...     actual_response_class=TestResponse,
            ...     body_field=model_field,
            ... )
            >>> test_result = asyncio.run(test_rq_handler)
            >>> assert isinstance(test_result, TestResponse)
            >>> assert test_result.media_type == TestResponse.media_type
            >>> assert test_result.body == test_result.body

        .. doctest:: Test BodyDecodeError

            >>> test_request._body = b"raise BodyDecodeError"
            >>> test_rq_handler = NonJsonRoute._request_handler(
            ...     dependant=test_dependant,
            ...     request=test_request,
            ...     is_coroutine=False,
            ...     is_body_form=False,
            ...     actual_response_class=TestResponse,
            ...     body_field=model_field,
            ... )
            >>> test_result = asyncio.run(test_rq_handler)
            Traceback (most recent call last):
            starlette.exceptions.HTTPException

        .. testcleanup::

            >>> BodyDecoder.__decoder__ = current_decoder
            >>> BodyDecoder.__content_type__ = current_decoder_map
        """

        body = await NonJsonRoute._original_fastapi_body_decode(
            request, is_body_form, body_field
        )

        if isinstance(body, bytes):
            try:
                body = BodyDecoder.run_decoder(request, body_field, body)
            except BodyDecodeError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            except Exception:  # pragma: nocover
                # run_decoder cannot trigger this exception handler since run_decoder
                # raises BodyDecodeError always. However, better safe than sorry
                raise HTTPException(
                    status_code=400, detail="There was an error parsing the body"
                )
        (
            raw_response,
            background_tasks,
            sub_response,
        ) = await NonJsonRoute._original_fastapi_call_endpoint(
            request=request,
            dependant=dependant,
            is_coroutine=is_coroutine,
            body=body,
            dependency_overrides_provider=dependency_overrides_provider,
        )

        if (
            not isinstance(raw_response, Response)
            and isinstance(actual_response_class, type)
            and issubclass(actual_response_class, NonJsonResponse)
        ):
            raw_response = actual_response_class(content=raw_response)

        return await NonJsonRoute._original_fastapi_return_response(
            raw_response=raw_response,
            background_tasks=background_tasks,
            sub_response=sub_response,
            is_coroutine=is_coroutine,
            actual_response_class=actual_response_class,
            status_code=status_code,
            response_field=response_field,
            response_model_include=response_model_include,
            response_model_exclude=response_model_exclude,
            response_model_by_alias=response_model_by_alias,
            response_model_exclude_unset=response_model_exclude_unset,
            response_model_exclude_defaults=response_model_exclude_defaults,
            response_model_exclude_none=response_model_exclude_none,
        )

    @staticmethod
    def get_request_handler(
        dependant: Dependant,
        body_field: Optional[ModelField] = None,
        status_code: Optional[int] = None,
        response_class: Union["Type[Response]", DefaultPlaceholder] = Default(
            JSONResponse
        ),
        response_field: Optional[ModelField] = None,
        response_model_include: Optional[Union[SetIntStr, DictIntStrAny]] = None,
        response_model_exclude: Optional[Union[SetIntStr, DictIntStrAny]] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        dependency_overrides_provider: Optional[Any] = None,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """
        If fastapi fails to decode the body, this request handler will use
        :class:`BodyDecoder` to decode the body.

        Furthermore, any API endpoint may use :class:`NonJsonResponse`
        to serialize any data into a non-json format.
        """
        (
            is_coroutine,
            is_body_form,
            actual_response_class,
        ) = NonJsonRoute._original_fastapi_prepare_request_handler(
            dependant=dependant, body_field=body_field, response_class=response_class
        )

        wrapped_func = NonJsonRoute._request_handler

        async def wrapper(request: Request) -> Any:
            return await wrapped_func(
                request=request,
                dependant=dependant,
                is_coroutine=is_coroutine,
                is_body_form=is_body_form,
                body_field=body_field,
                actual_response_class=actual_response_class,
                status_code=status_code,
                response_field=response_field,
                response_model_include=response_model_include,
                response_model_exclude=response_model_exclude,
                response_model_by_alias=response_model_by_alias,
                response_model_exclude_unset=response_model_exclude_unset,
                response_model_exclude_defaults=response_model_exclude_defaults,
                response_model_exclude_none=response_model_exclude_none,
                dependency_overrides_provider=dependency_overrides_provider,
            )

        wrapper.__wrapped_func__ = wrapped_func  # type: ignore[attr-defined]

        return wrapper


class BodyDecoder:
    __decoder__: ClassVar[
        List["Type[BodyDecoder]"]
    ] = []  #: a collection for all body decoders
    __content_type__: ClassVar[Dict[str, List["Type[BodyDecoder]"]]] = {}
    supported_content_type: ClassVar[Iterable[str]] = []

    @classmethod
    def register(cls, decoder: "Type[BodyDecoder]") -> None:
        """
        adds a decoder to :attr:`__decoder__`.

        The decoder is queried by :meth:`run_decoder`.

        .. testsetup::

            >>> current_decoder = BodyDecoder.__decoder__
            >>> current_decoder_map = BodyDecoder.__content_type__
            >>> BodyDecoder.__decoder__ = []
            >>> BodyDecoder.__content_type__ = {}

        .. doctest:: registration

            >>> ct = "application/test"
            >>> class TestDecoder(BodyDecoder):
            ...     supported_content_type: ClassVar[Iterable[str]] = [ct]
            >>> BodyDecoder.register(TestDecoder)
            >>> assert ct in BodyDecoder.__content_type__
            >>> assert isinstance(BodyDecoder.__content_type__[ct], list)
            >>> assert len(BodyDecoder.__content_type__[ct]) == 1
            >>> assert BodyDecoder.__content_type__[ct][0] == TestDecoder
            >>> assert len(BodyDecoder.__decoder__) == 1
            >>> assert BodyDecoder.__decoder__[0] == TestDecoder

        .. testcleanup::

            >>> BodyDecoder.__decoder__ = current_decoder
            >>> BodyDecoder.__content_type__ = current_decoder_map
        """

        for content_type in decoder.supported_content_type:
            if content_type not in cls.__content_type__:
                cls.__content_type__[content_type] = []
            cls.__content_type__[content_type].append(decoder)
        cls.__decoder__.append(decoder)

    @classmethod
    def _get_decoder_collection(
        cls, content_type: Optional[str]
    ) -> Iterable["Type[BodyDecoder]"]:
        """
        >>> a = BodyDecoder._get_decoder_collection("application/xml")
        >>> b = BodyDecoder._get_decoder_collection("text/xml")
        >>> c = BodyDecoder._get_decoder_collection("asdf/xml")
        >>> d = BodyDecoder._get_decoder_collection(None)
        >>> la = list(a)
        ...
        >>> assert len(BodyDecoder.__content_type__) > 0
        >>> assert len(BodyDecoder.__decoder__) > 0
        >>> assert a == b
        >>> assert id(a) != id(b)
        >>> assert id(c) == id(d)
        >>> assert id(la[0]) != id(c)
        """
        if content_type in cls.__content_type__:
            return cls.__content_type__[content_type]
        else:
            return cls.__decoder__

    @classmethod
    def run_decoder(
        cls, request: Request, field: ModelField, body: bytes
    ) -> Union[bytes, Dict[str, Any]]:
        """
        Decodes the HTTP body using any decoder from :attr:`__decoder__`.

        :param request: the original request
        :param field:   the model field to deal with
        :param body:    the original http body

        :return: A decoded body if any decoder was capable to handel the body. Else,
                 the unmodified body.

        :raises BodyDecodeError: if any decoder raised an exception. Writes the
                                 error traceback to stderr if the underlying exception
                                 is not an instance of :class:`BodyDecodeError`

        .. testsetup::

            >>> from dataclasses import dataclass
            >>> from dataclasses import field
            >>> from fastapi_xml import XmlBody

            >>> app = FastAPI()
            >>> app.router.route_class = NonJsonRoute

            >>> @dataclass
            ... class Dummy:
            ...     x: str = field(metadata={"type": "Element"})

            >>> @app.router.post("/")
            ... def endpoint(x: Dummy = XmlBody()) -> None:  # pragma: nocover
            ...     pass

            >>> route = app.routes[-1]
            >>> assert isinstance(route, APIRoute)
            >>> body_field = route.body_field

        .. doctest:: unsupported content type

            >>> scope = {
            ...     "type": "http",
            ...     "query_string": "",
            ...     "headers": [(b"content-type", b"text/html")],
            ... }
            >>> test_request = Request(scope=scope)
            >>> test_body = b"invalid"
            >>> test_request.headers._list = [("content-type", "text/html")]
            >>> test_result = BodyDecoder.run_decoder(
            ...     test_request,
            ...     body_field,
            ...     test_body
            ... )
            >>> assert test_result == test_body

        .. doctest:: successfull decoding

            >>> scope["headers"] = [(b"content-type", b"application/xml")]
            >>> test_request = Request(scope=scope)
            >>> test_result = BodyDecoder.run_decoder(
            ...     test_request,
            ...     body_field,
            ...     b"<Dummy><x>foo</x></Dummy>"
            ... )
            >>> assert isinstance(test_result, dict)
            >>> assert test_result["x"] == "foo"

        .. doctest:: decoding error

            >>> test_result = BodyDecoder.run_decoder(
            ...     test_request,
            ...     body_field,
            ...     b"invalid"
            ... )
            Traceback (most recent call last):
            fastapi_xml.nonjson.BodyDecodeError: syntax error: line 1, column 0

        .. doctest:: unexcepted exception

            >>> test_result = BodyDecoder.run_decoder(
            ...     test_request,
            ...     None,
            ...     b"<Dummy><x>foo</x></Dummy>"
            ... )  # ignore: type
            Traceback (most recent call last):
            fastapi_xml.nonjson.BodyDecodeError: body decoding failed.
        """
        content_type = request.headers.get("content-type")
        content_type = content_type.lower() if isinstance(content_type, str) else None
        decoder_collection = cls._get_decoder_collection(content_type)

        for decoder in decoder_collection:
            try:
                result = decoder.decode(request, field, body)
            except BodyDecodeError:
                raise
            except Exception as e:
                sys.stderr.write(traceback.format_exc() + "\n")
                raise BodyDecodeError("body decoding failed.") from e
            if result is not None:
                return result
        return body

    @classmethod
    @abstractmethod
    def decode(
        cls, request: Request, field: ModelField, body: bytes
    ) -> Optional[Dict[str, Any]]:  # pragma: nocover
        """
        This method decodes the body. Any Implementation must review if the
        body has the correct format. If not, this method MUST return None. For
        instance, an xml decoder is not capable to decode binary data. Hence,
        the xml decoder validates if the body is valid xml first, and proceeds
        decoding afterwards.

        :param request: the original request
        :param field:   the model field to deal with
        :param body:    the original http body

        :raises BodyDecodeError: if this is the correct decoder but the body is invalid
                                 for some reason.
                                 The error message should not contain sensible data
                                 since :meth:`run_decoder` will forward it.

        :return: The Decoder MUST return None, if the decoding failed for any reason.
                Else, it MUST return a mapping for pydantic's constructor
        """
        raise NotImplementedError()


class NonJsonResponse(JSONResponse):
    """fastapi.openapi.utils.get_openapi_path does not support any
    response_schema except for JSONResponse:"""


def _get_unmodified_openapi(app: FastAPI) -> OpenAPI:
    """
    .. testsetup::

        >>> from dataclasses import dataclass
        >>> from dataclasses import field
        >>> from fastapi_xml.xmlbody import XmlBody

        >>> app = FastAPI()
        >>> app.router.route_class = NonJsonRoute

        >>> @dataclass
        ... class Dummy:
        ...     x: str = field(metadata={"type": "Element"})
        ...
        >>> @app.router.post("/")
        ... def endpoint(x: Dummy = XmlBody()) -> None:  # pragma: nocover
        ...     pass

     .. doctest:: schema unchanged

        >>> a = app.openapi()
        >>> b = _get_unmodified_openapi(app).dict(exclude_none=True, by_alias=True)
        >>> assert a == b
    """
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
    )
    return OpenAPI(**openapi_schema)


def _extend_openapi(app: FastAPI, **extension_kwargs: Any) -> Dict[str, Any]:
    """
    .. testsetup::

        >>> from dataclasses import dataclass
        >>> from fastapi_xml.xmlbody import XmlBody
        >>> @dataclass
        ... class Dummy:
        ...     x: str
        >>> app = FastAPI()
        >>> @app.router.post("/")
        ... def endpoint(x: Dummy = XmlBody()) -> None:  # pragma: nocover
        ...     pass

     .. doctest:: predefined schema

        >>> predefined = dict()
        >>> app.openapi_schema = predefined
        >>> result = _extend_openapi(app)
        >>> assert id(result) == id(predefined)
        >>> app.openapi_schema = None

     .. doctest:: schema modification

        >>> openapi_unmodified = _get_unmodified_openapi(app)
        >>> openapi_modified   = _extend_openapi(app)
        >>> assert openapi_modified != openapi_unmodified
    """
    if app.openapi_schema is not None:
        return app.openapi_schema
    openapi = _get_unmodified_openapi(app)

    for modifier in OPENAPI_SCHEMA_MODIFIER:
        modifier(app, openapi, extension_kwargs)

    app.openapi_schema = jsonable_encoder(openapi, by_alias=True, exclude_none=True)
    return app.openapi_schema


def add_openapi_extension(app: FastAPI, **extension_kwargs: Any) -> None:
    """
    .. testsetup::

        >>> from fastapi import FastAPI
        >>> from dataclasses import dataclass
        >>> from fastapi_xml.xmlbody import XmlBody

     .. doctest::

        >>> app = FastAPI()
        >>> add_openapi_extension(app)
        >>> assert isinstance(app.openapi, MethodType)
        >>> assert app.openapi.__func__ == _extend_openapi
        >>> assert isinstance(app.openapi(), dict)
    """
    app.openapi = MethodType(_extend_openapi, app)  # type: ignore[assignment]
