import sys
import traceback
import asyncio
import email.message
import json

from abc import abstractmethod

from typing import (
    Any,
    Iterable,
    Callable,
    ClassVar,
    Coroutine,
    Dict,
    List,
    Optional,
    Type,
    Union,
    Mapping,
    Set,
    Tuple,
    Protocol
)

from fastapi import utils
from fastapi import params
from fastapi.encoders import DictIntStrAny, SetIntStr
from fastapi.datastructures import Default, DefaultPlaceholder
from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import solve_dependencies
from fastapi.exceptions import RequestValidationError
from fastapi.routing import serialize_response, run_endpoint_function, APIRoute

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from pydantic.error_wrappers import ErrorWrapper
from pydantic.fields import ModelField, Undefined
from pydantic.schema import TypeModelSet, TypeModelOrEnum, default_ref_template, model_process_schema


class OpenApiSchemaModifier(Protocol):
    def __call__(self,
                 model: TypeModelOrEnum,
                 *,
                 schema: Dict[str, Any],
                 definitions: Dict[str, Any],
                 nested_models: Set[str],
                 by_alias: bool = True,
                 model_name_map: Dict[TypeModelOrEnum, str],
                 ref_prefix: Optional[str] = None,
                 ref_template: str = default_ref_template,
                 known_models: TypeModelSet = None,
                 field: Optional[ModelField] = None) -> None: ...


OPENAPI_SCHEMA_MODIFIER: List[OpenApiSchemaModifier] = []


def modify_openapi_schema(
    model: TypeModelOrEnum,
    *,
    by_alias: bool = True,
    model_name_map: Dict[TypeModelOrEnum, str],
    ref_prefix: Optional[str] = None,
    ref_template: str = default_ref_template,
    known_models: TypeModelSet = None,
    field: Optional[ModelField] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Set[str]]:
    m_schema, m_definitions, nested_models = model_process_schema(model,
                                                                  by_alias=by_alias,
                                                                  model_name_map=model_name_map,
                                                                  ref_prefix=ref_prefix,
                                                                  ref_template=ref_template,
                                                                  known_models=known_models,
                                                                  field=field)

    for modifier in OPENAPI_SCHEMA_MODIFIER:
        modifier(model,
                 schema=m_schema,
                 definitions=m_definitions,
                 nested_models=nested_models,

                 by_alias=by_alias,
                 model_name_map=model_name_map,
                 ref_prefix=ref_prefix,
                 ref_template=ref_template,
                 known_models=known_models,
                 field=field)
    return m_schema, m_definitions, nested_models


class BodyDecodeError(ValueError):
    pass


class NonJsonRoute(APIRoute):
    def get_route_handler(self) -> Callable:
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
    def get_request_handler(
        dependant: Dependant,
        body_field: Optional[ModelField] = None,
        status_code: Optional[int] = None,
        response_class: Union[Type[Response], DefaultPlaceholder] = Default(JSONResponse),
        response_field: Optional[ModelField] = None,
        response_model_include: Optional[Union[SetIntStr, DictIntStrAny]] = None,
        response_model_exclude: Optional[Union[SetIntStr, DictIntStrAny]] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        dependency_overrides_provider: Optional[Any] = None,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """this is a patched version of :func:´fastapi.routing.get_request_handler`. If fastapi fails to decode the body,
        this request handler will use :class:`BodyDecoder` to decode the body. In addition, if the endpoint returns an
        instance of :class:`CustomResponseModel` this request handler calls :meth:`CustomResponseModel.as_fastapi_respose`
        to receive a proper response."""
        # this is a modified copy of `fastapi.routing.get_request_handler`.
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
        assert dependant.call is not None, "dependant.call must be a function"
        is_coroutine = asyncio.iscoroutinefunction(dependant.call)
        is_body_form = body_field and isinstance(body_field.field_info, params.Form)
        if isinstance(response_class, DefaultPlaceholder):
            actual_response_class: Type[Response] = response_class.value
        else:
            actual_response_class = response_class

        async def app(request: Request) -> Response:
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
            # BEGIN EDIT
                        if isinstance(body, bytes):
                            body = BodyDecoder.run_decoder(request, body_field, body)
            except BodyDecodeError as e:
                raise HTTPException(
                    status_code=400, detail=str(e)
                ) from e
            # END EDIT
            except json.JSONDecodeError as e:
                raise RequestValidationError([ErrorWrapper(e, ("body", e.pos))], body=e.doc)
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail="There was an error parsing the body"
                ) from e

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

                # BEGIN EDIT
                if not isinstance(raw_response, Response) and isinstance(response_class, type) and issubclass(response_class, NonJsonResponse):
                    raw_response = response_class(content=raw_response)
                # END EDIT

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

        return app


class BodyDecoder:
    __decoder__:            ClassVar[List[Type['BodyDecoder']]]               = []        #: a collection for all body decoders
    __content_type__:       ClassVar[Mapping[str, List[Type["BodyDecoder"]]]] = dict()
    supported_content_type: ClassVar[Iterable[str]]                           = []

    @classmethod
    def register(cls, decoder: Type['BodyDecoder']) -> None:
        """adds a decoder to :attr:`__decoder__`. The decoder is queried by :meth:`run_decoder`."""
        for content_type in decoder.supported_content_type:
            if content_type not in cls.__content_type__:
                cls.__content_type__ = []
            cls.__content_type__[content_type] = decoder
        cls.__decoder__.append(decoder)

    @classmethod
    def run_decoder(cls, request: Request, field: ModelField, body: bytes) -> Union[bytes, Dict[str, Any]]:
        """
        Decodes the HTTP body using any decoder from :attr:`__decoder__`.

        :param request: the original request
        :param field:   the model field to deal with
        :param body:    the original http body

        :return: A decoded body if any decoder was capable to handel the body. Else, the unmodified body.

        :raises BodyDecodeError:    if any decoder raised an exception. Writes the error traceback to stderr if the
                                    underlying exception is not an instance of class:`BodyDecodeError`
        """
        content_type = request.headers.get("content-type")
        content_type = content_type.lower() if isinstance(content_type, str) else None
        if content_type in cls.__content_type__:
            decoder_collection = cls.__content_type__[content_type]
        else:
            decoder_collection = cls.__decoder__

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
    def decode(cls, request: Request, field: ModelField, body: bytes) -> Optional[Dict[str, Any]]:
        """
        This method decodes the body. Any Implementation must review if the body has the correct format. If not,
        this method MUST return None. For instance, an xml decoder is not capable to decode binary data. Hence, the
        xml decoder validates if the body is valid xml first, and proceeds decoding afterwards.

        :param request: the original request
        :param field:   the model field to deal with
        :param body:    the original http body

        :raises BodyDecodeError: if this is the correct decoder but the body is invalid for some reason.
                                 The error message should not contain sensible data since :meth:`run_decoder` will
                                 forward it.

        :return: The Decoder MUST return None, if the decoding failed for any reason.
                Else, it MUST return a mapping for pydantic's constructor
        """
        raise NotImplementedError()


class NonJsonResponse(JSONResponse):
    # fastapi.openapi.utils.get_openapi_path does not support any response_schema except for JSONResponse:
    pass


utils.model_process_schema = modify_openapi_schema
