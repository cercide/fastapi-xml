import asyncio
from contextlib import AsyncExitStack
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union

from fastapi import params
from fastapi._compat import _normalize_errors
from fastapi._compat import ModelField
from fastapi.datastructures import Default
from fastapi.datastructures import DefaultPlaceholder
from fastapi.datastructures import FormData
from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import solve_dependencies
from fastapi.exceptions import FastAPIError
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.routing import run_endpoint_function
from fastapi.routing import serialize_response
from fastapi.types import IncEx
from fastapi.utils import is_body_allowed_for_status_code
from starlette.background import BackgroundTasks
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import Response
from xsdata.formats.dataclass.context import XmlContext

from .decoder import BodyDecodeError
from .decoder import XmlDecoder
from .response import XmlResponse

DEFAULT_XML_CONTEXT: XmlContext = XmlContext()


class XmlRoute(APIRoute):
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
    async def _mod_fastapi_return_response(
        raw_response: Any,
        background_tasks: Optional[BackgroundTasks],
        sub_response: Response,
        is_coroutine: bool,
        actual_response_class: "Type[Response]",
        status_code: Optional[int] = None,
        response_field: Optional[ModelField] = None,
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
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
            response = raw_response
        else:
            response_args: Dict[str, Any] = {"background": background_tasks}
            # If status_code was set, use it, otherwise use the default from the
            # response class, in the case of redirect it's 307
            current_status_code = (
                status_code if status_code else sub_response.status_code
            )
            if current_status_code is not None:
                response_args["status_code"] = current_status_code
            if sub_response.status_code:
                response_args["status_code"] = sub_response.status_code
            content = await serialize_response(
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
            response = actual_response_class(content, **response_args)
            if not is_body_allowed_for_status_code(response.status_code):
                response.body = b""
            response.headers.raw.extend(sub_response.headers.raw)

        if response is None:
            raise FastAPIError(
                "No response object was returned. There's a high chance that the "
                "application code is raising an exception and a dependency with yield "
                "has a block with a bare except, or a block with except Exception, "
                "and is not raising the exception again. Read more about it in the "
                "docs: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#dependencies"
                "-with-yield-and-except"
            )
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
    async def _mod_fastapi_call_endpoint(
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
        async with AsyncExitStack() as async_exit_stack:
            solved_result = await solve_dependencies(
                request=request,
                dependant=dependant,
                body=body,
                dependency_overrides_provider=dependency_overrides_provider,
                async_exit_stack=async_exit_stack,
            )

        values, errors, background_tasks, sub_response, _ = solved_result
        if errors:
            validation_error = RequestValidationError(
                _normalize_errors(errors), body=body
            )
            raise validation_error
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
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        dependency_overrides_provider: Optional[Any] = None,
    ) -> Response:
        body: Any = None
        if body_field:
            body_bytes = await request.body()
            try:
                body = XmlDecoder.decode(request, body_field, body_bytes)
            except BodyDecodeError as e:  # pragma: nocover
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
        ) = await XmlRoute._mod_fastapi_call_endpoint(
            request=request,
            dependant=dependant,
            is_coroutine=is_coroutine,
            body=body,
            dependency_overrides_provider=dependency_overrides_provider,
        )

        if (
            not isinstance(raw_response, Response)
            and isinstance(actual_response_class, type)
            and issubclass(actual_response_class, XmlResponse)
        ):
            raw_response = actual_response_class(content=raw_response)

        return await XmlRoute._mod_fastapi_return_response(
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
        response_model_include: Optional[IncEx] = None,
        response_model_exclude: Optional[IncEx] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        dependency_overrides_provider: Optional[Any] = None,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """
        If fastapi fails to decode the body, this request handler will use
        :class:`XmlDecoder` to decode the body.

        Furthermore, any API endpoint may use :class:`XmlResponse`
        to serialize any data into a non-json format.
        """

        (
            is_coroutine,
            is_body_form,
            actual_response_class,
        ) = XmlRoute._original_fastapi_prepare_request_handler(
            dependant=dependant, body_field=body_field, response_class=response_class
        )

        wrapped_func = XmlRoute._request_handler

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
