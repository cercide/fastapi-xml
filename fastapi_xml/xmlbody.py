from typing import Any
from typing import List
from typing import Optional

from fastapi import Body
from fastapi._compat import Undefined


def XmlBody(
    default: Any = Undefined,
    *,
    embed: bool = False,
    media_type: str = "application/xml",
    alias: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    gt: Optional[float] = None,
    ge: Optional[float] = None,
    lt: Optional[float] = None,
    le: Optional[float] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    regex: Optional[str] = None,
    example: Any = Undefined,
    examples: Optional[List[Any]] = None,
    **extra: Any,
) -> Any:
    """
    The XmlBody function is a shortcut for the Body function with media_type
    set to **application/xml**.

    :param default: Set a default value for the body
    :param embed: Indicate whether the body should be embedded
    :param media_type: Specify the media type of the body
    :param alias: Specify the name of the parameter in a query string
    :param title: Set the title of the parameter
    :param description: Describe the parameter
    :param gt: Specify a minimum value
    :param ge: Specify the minimum value of a numeric instance
    :param lt: Specify the maximum value of a number
    :param le: Specify the maximum value of a number
    :param min_length: Specify the minimum length of a string
    :param max_length: Specify the maximum length of a string
    :param regex: Validate the string against a regex pattern
    :param example: Define an example of the body
    :param examples Define a dictionary of examples
    :param extra: Allows for any other parameter that is not defined in the function
    :return: A body object
    """
    return Body(
        default,
        embed=embed,
        media_type=media_type,
        alias=alias,
        title=title,
        description=description,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        min_length=min_length,
        max_length=max_length,
        regex=regex,
        example=example,
        examples=examples,
        **extra,
    )
