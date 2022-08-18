# this module contains modified code snippets from pydantic. Hence a license copy is given below.
# Any changes are highlighted.
#
# The MIT License (MIT)
#
# Copyright (c) 2017, 2018, 2019, 2020, 2021 Samuel Colvin and other contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from typing import Any, Dict, Optional, Type, TYPE_CHECKING
from dataclasses import is_dataclass, asdict
from pydantic.typing import NoArgAnyCallable
from pydantic.class_validators import gather_all_validators
from pydantic.fields import Field, FieldInfo, Required, Undefined
from pydantic.main import create_model
from pydantic.typing import resolve_annotations
from pydantic.utils import ClassAttribute
from pydantic.dataclasses import _generate_pydantic_post_init, is_builtin_dataclass, _get_validators, setattr_validate_assignment, DataclassTypeError

if TYPE_CHECKING:
    from pydantic.dataclasses import Dataclass, DataclassT

_CACHE: Dict[Type, Type['Dataclass']] = {}


def pydantic_process_class_patched(
    _cls: Type[Any],
    init: bool,
    repr: bool,
    eq: bool,
    order: bool,
    unsafe_hash: bool,
    frozen: bool,
    config: Optional[Type[Any]],
) -> Type['Dataclass']:
    # BEGIN EDIT
    or_cls = _cls
    if or_cls in _CACHE:
        return _CACHE[or_cls]
    # END EDIT

    import dataclasses

    post_init_original = getattr(_cls, '__post_init__', None)
    if post_init_original and post_init_original.__name__ == '_pydantic_post_init':
        post_init_original = None
    if not post_init_original:
        post_init_original = getattr(_cls, '__post_init_original__', None)

    post_init_post_parse = getattr(_cls, '__post_init_post_parse__', None)

    _pydantic_post_init = _generate_pydantic_post_init(post_init_original, post_init_post_parse)

    # If the class is already a dataclass, __post_init__ will not be called automatically
    # so no validation will be added.
    # We hence create dynamically a new dataclass:
    # ```
    # @dataclasses.dataclass
    # class NewClass(_cls):
    #   __post_init__ = _pydantic_post_init
    # ```
    # with the exact same fields as the base dataclass
    # and register it on module level to address pickle problem:
    # https://github.com/samuelcolvin/pydantic/issues/2111
    if is_builtin_dataclass(_cls):
        uniq_class_name = f'_Pydantic_{_cls.__name__}_{id(_cls)}'
        _cls = type(
            # for pretty output new class will have the name as original
            _cls.__name__,
            (_cls,),
            {
                '__annotations__': resolve_annotations(_cls.__annotations__, _cls.__module__),
                '__post_init__': _pydantic_post_init,
                # attrs for pickle to find this class
                '__module__': __name__,
                '__qualname__': uniq_class_name,

                # BEGIN EDIT
                # addresses https://github.com/pydantic/pydantic/issues/4353
                # BUGFIX: forward original fields to the new dataclass
                **getattr(_cls, "__dataclass_fields__", {})
                # BEGIN EDIT
            },
        )
        globals()[uniq_class_name] = _cls
    else:
        _cls.__post_init__ = _pydantic_post_init
    cls: Type['Dataclass'] = dataclasses.dataclass(  # type: ignore
        _cls, init=init, repr=repr, eq=eq, order=order, unsafe_hash=unsafe_hash, frozen=frozen
    )
    cls.__processed__ = ClassAttribute('__processed__', True)

    field_definitions: Dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        default: Any = Undefined
        default_factory: Optional['NoArgAnyCallable'] = None
        field_info: FieldInfo

        if field.default is not dataclasses.MISSING:
            default = field.default
        elif field.default_factory is not dataclasses.MISSING:
            default_factory = field.default_factory
        else:
            default = Required

        if isinstance(default, FieldInfo):
            field_info = default
            cls.__has_field_info_default__ = True
        else:
            field_info = Field(default=default, default_factory=default_factory, **field.metadata)

        field_definitions[field.name] = (field.type, field_info)

    validators = gather_all_validators(cls)
    cls.__pydantic_model__ = create_model(
        cls.__name__,
        __config__=config,
        __module__=_cls.__module__,
        __validators__=validators,
        __cls_kwargs__={'__resolve_forward_refs__': False},
        **field_definitions,
    )

    cls.__initialised__ = False
    cls.__validate__ = classmethod(_validate_dataclass)  # type: ignore[assignment]
    cls.__get_validators__ = classmethod(_get_validators)  # type: ignore[assignment]
    if post_init_original:
        cls.__post_init_original__ = post_init_original

    if cls.__pydantic_model__.__config__.validate_assignment and not frozen:
        cls.__setattr__ = setattr_validate_assignment  # type: ignore[assignment]

    cls.__pydantic_model__.__try_update_forward_refs__(**{cls.__name__: cls})

    # BEGIN EDIT
    cls.__origin__ = or_cls
    _CACHE[or_cls] = cls
    # END EDIT
    return cls


def _validate_dataclass(cls: Type['DataclassT'], v: Any) -> 'DataclassT':
    if isinstance(v, cls):
        # BEGIN EDIT
        result = v
        # END EDIT
    elif isinstance(v, (list, tuple)):
        # BEGIN EDIT
        result = cls(*v)
        # END EDIT
    elif isinstance(v, dict):
        # BEGIN EDIT
        result = cls(**v)
        # END EDIT
    # In nested dataclasses, v can be of type `dataclasses.dataclass`.
    # But to validate fields `cls` will be in fact a `pydantic.dataclasses.dataclass`,
    # which inherits directly from the class of `v`.
    elif is_builtin_dataclass(v) and cls.__bases__[0] is type(v):
        # BEGIN EDIT
        # import dataclasses
        result = cls(**asdict(v))
        # END EDIT
    else:
        raise DataclassTypeError(class_name=cls.__name__)

    # BEGIN EDIT
    clazz = getattr(cls, "__origin__", None)
    if is_dataclass(clazz):
        return clazz(**asdict(result))
    else:
        return result
    # END EDIT
