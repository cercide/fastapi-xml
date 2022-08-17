from typing import Any, Dict, Optional, Type, TYPE_CHECKING

from pydantic.typing import NoArgAnyCallable
from pydantic.class_validators import gather_all_validators
from pydantic.fields import Field, FieldInfo, Required, Undefined
from pydantic.main import create_model
from pydantic.typing import resolve_annotations
from pydantic.utils import ClassAttribute
from pydantic.dataclasses import _generate_pydantic_post_init, is_builtin_dataclass, _validate_dataclass, _get_validators

if TYPE_CHECKING:
    from pydantic.dataclasses import Dataclass


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
                # addresses https://github.com/pydantic/pydantic/issues/4353
                # BUGFIX: forward original fields to the new dataclass
                **_cls.__dataclass_fields__
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

    return cls
