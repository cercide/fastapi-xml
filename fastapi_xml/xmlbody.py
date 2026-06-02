from typing import Annotated
from typing import Any
from typing import Callable

from annotated_doc import Doc
from fastapi import Body
from fastapi._compat import Undefined
from fastapi.datastructures import _Unset
from fastapi.openapi.models import Example
from pydantic import AliasChoices
from pydantic import AliasPath


def XmlBody(
    default: Annotated[
        Any,
        Doc("Default value if the parameter field is not set."),
    ] = Undefined,
    *,
    default_factory: Annotated[
        Callable[[], Any] | None,
        Doc("""
            A callable to generate the default value.

            This doesn't affect `Path` parameters as the value is always
            required. The parameter is available only for compatibility.
            """),
    ] = _Unset,
    embed: Annotated[
        bool | None,
        Doc("""
            When `embed` is `True`, the parameter will be expected in a JSON
            body as a key instead of being the JSON body itself.

            This happens automatically when more than one `Body` parameter is declared.

            Read more about it in the
            [FastAPI docs for Body - Multiple Parameters](https://fastapi.tiangolo.com/tutorial/body-multiple-params/#embed-a-single-body-parameter).
            """),
    ] = None,
    media_type: Annotated[
        str,
        Doc("""
            The media type of this parameter field.

            Changing it would affect the generated OpenAPI, but
            currently it doesn't affect the parsing of the data.
            """),
    ] = "application/xml",
    alias: Annotated[
        str | None,
        Doc("""
            An alternative name for the parameter field.

            This will be used to extract the data and for the generated
            OpenAPI. It is particularly useful when you can't use the
            name you want because it is a Python reserved keyword or
            similar.
            """),
    ] = None,
    alias_priority: Annotated[
        int | None,
        Doc("""
            Priority of the alias.

            This affects whether an alias generator is used.
            """),
    ] = _Unset,
    validation_alias: Annotated[
        str | AliasPath | AliasChoices | None,
        Doc("""
            'Whitelist' validation step.

            The parameter field will be the single one allowed by the
            alias or set of aliases defined.
            """),
    ] = None,
    serialization_alias: Annotated[
        str | None,
        Doc("""
            'Blacklist' validation step.

            The vanilla parameter field will be the single one of the
            alias' or set of aliases' fields and all the other fields
            will be ignored at serialization time.
            """),
    ] = None,
    title: Annotated[
        str | None,
        Doc("""Human-readable title."""),
    ] = None,
    description: Annotated[
        str | None,
        Doc("""Human-readable description."""),
    ] = None,
    gt: Annotated[
        float | None,
        Doc("""
            Greater than.

            If set, value must be greater than this. Only applicable to
            numbers.
            """),
    ] = None,
    ge: Annotated[
        float | None,
        Doc("""
            Greater than or equal.

            If set, value must be greater than or equal to this. Only
            applicable to numbers.
            """),
    ] = None,
    lt: Annotated[
        float | None,
        Doc("""
            Less than.

            If set, value must be less than this. Only applicable to
            numbers.
            """),
    ] = None,
    le: Annotated[
        float | None,
        Doc("""
            Less than or equal.

            If set, value must be less than or equal to this. Only
            applicable to numbers.
            """),
    ] = None,
    min_length: Annotated[
        int | None,
        Doc("""Minimum length for strings."""),
    ] = None,
    max_length: Annotated[
        int | None,
        Doc("""Maximum length for strings."""),
    ] = None,
    pattern: Annotated[
        str | None,
        Doc("""RegEx pattern for strings."""),
    ] = None,
    discriminator: Annotated[
        str | None,
        Doc("""Parameter field name for discriminating the type in a tagged
            union."""),
    ] = None,
    strict: Annotated[
        bool | None,
        Doc("""If `True`, strict validation is applied to the field."""),
    ] = _Unset,
    multiple_of: Annotated[
        float | None,
        Doc("""
            Value must be a multiple of this.

            Only applicable to numbers.
            """),
    ] = _Unset,
    allow_inf_nan: Annotated[
        bool | None,
        Doc("""
            Allow `inf`, `-inf`, `nan`.

            Only applicable to numbers.
            """),
    ] = _Unset,
    max_digits: Annotated[
        int | None,
        Doc("""Maximum number of digits allowed for decimal values."""),
    ] = _Unset,
    decimal_places: Annotated[
        int | None,
        Doc("""Maximum number of decimal places allowed for decimal values."""),
    ] = _Unset,
    examples: Annotated[
        list[Any] | None,
        Doc("""
            Example values for this field.

            Read more about it in the
            [FastAPI docs for Declare Request Example Data](https://fastapi.tiangolo.com/tutorial/schema-extra-example/)
            """),
    ] = None,
    openapi_examples: Annotated[
        dict[str, Example] | None,
        Doc("""
            OpenAPI-specific examples.

            It will be added to the generated OpenAPI (e.g. visible at `/docs`).

            Swagger UI (that provides the `/docs` interface) has better support for the
            OpenAPI-specific examples than the JSON Schema `examples`, that's the main
            use case for this.

            Read more about it in the
            [FastAPI docs for Declare Request Example Data](https://fastapi.tiangolo.com/tutorial/schema-extra-example/#using-the-openapi_examples-parameter).
            """),
    ] = None,
    include_in_schema: Annotated[
        bool,
        Doc("""
            To include (or not) this parameter field in the generated OpenAPI.
            You probably don't need it, but it's available.

            This affects the generated OpenAPI (e.g. visible at
            `/docs`).
            """),
    ] = True,
    json_schema_extra: Annotated[
        dict[str, Any] | None,
        Doc("""Any additional JSON schema data."""),
    ] = None,
) -> Any:
    """The XmlBody function is a shortcut for the Body function with media_type.

    set to **application/xml**.
    """
    return Body(
        default,
        default_factory=default_factory,
        embed=embed,
        media_type=media_type,
        alias=alias,
        alias_priority=alias_priority,
        validation_alias=validation_alias,
        serialization_alias=serialization_alias,
        title=title,
        description=description,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        min_length=min_length,
        max_length=max_length,
        pattern=pattern,
        discriminator=discriminator,
        strict=strict,
        multiple_of=multiple_of,
        allow_inf_nan=allow_inf_nan,
        max_digits=max_digits,
        decimal_places=decimal_places,
        examples=examples,
        openapi_examples=openapi_examples,
        include_in_schema=include_in_schema,
        json_schema_extra=json_schema_extra,
    )
