import unittest
from dataclasses import dataclass
from dataclasses import Field
from dataclasses import field
from typing import Any
from typing import Collection
from typing import List
from typing import Optional
from typing import Set
from typing import Type
from typing import TYPE_CHECKING
from typing import Union

from fastapi.openapi.models import Schema
from fastapi.openapi.models import XML
from pydantic import BaseModel
from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic.json_schema import DEFAULT_REF_TEMPLATE
from pydantic import TypeAdapter
from fastapi_xml import xmlbody

if TYPE_CHECKING:  # pragma: nocover
    from pydantic.dataclasses import Dataclass


class OpenAPIXmlExtensionTests(unittest.TestCase):
    def assertEmpty(self, collection: Collection[Any], message: str = "") -> None:
        self.assertEqual(len(collection), 0, message)

    def assertLen(
        self, collection: Collection[Any], num: int = 1, message: str = ""
    ) -> None:
        self.assertEqual(len(collection), num, message)

    def assertAllNoneExcept(
        self, obj: BaseModel, *exceptions: str, ignore: Optional[Set[str]] = None
    ) -> None:
        ignore = ignore or set()
        all_fields = set(obj.model_fields.keys())
        should_not_none = set(exceptions)
        should_be_none = all_fields - should_not_none
        fields = obj.model_fields

        check_valid_fields = (should_not_none | ignore | should_be_none) - all_fields
        self.assertEmpty(check_valid_fields, f"invalid fields: {check_valid_fields}")

        check_covered_fields = all_fields - (should_not_none | ignore | should_be_none)
        self.assertEmpty(
            check_covered_fields, f"uncovered fields: {check_covered_fields}"
        )

        fields_not_none = {k for k in fields.keys() if getattr(obj, k) is not None}
        fields_are_none = {k for k in fields.keys() if getattr(obj, k) is None}

        check_for_none = should_be_none.intersection(fields_not_none) - ignore
        check_not_none = should_not_none.intersection(fields_are_none) - ignore
        self.assertEmpty(check_not_none, f"fields should not be None: {check_not_none}")
        self.assertEmpty(check_for_none, f"fields should be None: {check_for_none}")

    @staticmethod
    def _get_dataclass_field(dclazz: "Type[object]", field_name: str) -> "Field[Any]":
        fields = getattr(dclazz, "__dataclass_fields__", {})
        f = fields.get(field_name)
        assert isinstance(f, Field)
        return f

    @staticmethod
    def _get_schema(model: Union["Type[Dataclass]"]) -> Schema:
        return Schema(
                **TypeAdapter(model).json_schema(
                    by_alias=True, ref_template="#/components/schemas/{model}"
                )
            )

    def test_named_attribute(self) -> None:
        @dataclass
        class NamedAttribute:
            x: str = field(metadata={"name": "XXX", "type": "Element"})

        dclazz = NamedAttribute
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")

        xmlbody._add_model_schema(dclazz, schema, {})
        xmlbody._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "xml",
            "properties",
            ignore={"title", "description", "required"},
        )
        self.assertEqual(schema.type, "object")
        assert isinstance(schema.xml, XML)
        assert isinstance(schema.properties, dict)
        attr = schema.properties["x"]
        self.assertAllNoneExcept(
            attr,
            "type",
            "xml",
            ignore={"title", "description", "required"},
        )
        self.assertEqual(attr.type, "string")
        assert isinstance(attr.xml, XML)
        self.assertAllNoneExcept(attr.xml, "name")
        self.assertEqual(attr.xml.name, "XXX")

    def test_attribute(self) -> None:
        @dataclass
        class WithoutMetaName:
            x: str = field(metadata={"type": "Attribute"})

        dclazz = WithoutMetaName
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")

        xmlbody._add_model_schema(dclazz, schema, {})
        xmlbody._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "xml",
            "properties",
            ignore={"title", "description", "required"},
        )
        self.assertEqual(schema.type, "object")
        assert schema.xml is not None
        self.assertAllNoneExcept(schema.xml, "name")
        self.assertEqual(schema.xml.name, dclazz.__name__)

        assert schema.properties is not None
        prop = schema.properties["x"]
        self.assertAllNoneExcept(
            prop,
            "xml",
            ignore={"title", "description", "type"},
        )
        assert isinstance(prop.xml, XML)
        self.assertEqual(prop.xml.attribute, True)

    def test_model_without_meta_name(self) -> None:
        @dataclass
        class WithoutMetaName:
            x: str

        dclazz = WithoutMetaName
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)

        xmlbody._add_model_schema(dclazz, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "xml",
            ignore={"title", "properties", "description", "required"},
        )
        self.assertEqual(schema.type, "object")
        assert schema.xml is not None
        self.assertAllNoneExcept(schema.xml, "name")
        self.assertEqual(schema.xml.name, dclazz.__name__)

    def test_model_having_meta_name(self) -> None:
        @dataclass
        class HavingMetaName:
            class Meta:
                name = "MetaName"

            x: str

        dclazz = HavingMetaName
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)

        xmlbody._add_model_schema(dclazz, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "xml",
            ignore={"title", "description", "required", "properties"},
        )
        self.assertEqual(schema.type, "object")
        assert schema.xml is not None
        self.assertAllNoneExcept(schema.xml, "name")
        self.assertEqual(schema.xml.name, dclazz.Meta.name)

    def test_ref_without_name(self) -> None:
        @dataclass
        class Referenced:
            x: str

        @dataclass
        class PlainRefWithoutName:
            x: Referenced

        dclazz = PlainRefWithoutName
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")

        xmlbody._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "properties",
            ignore={"title", "required", "description", "required", "properties", "defs"},
        )
        assert schema.properties is not None
        prop = schema.properties["x"]

        self.assertEqual(schema.type, "object")
        self.assertAllNoneExcept(prop, "ref")

    def test_ref_having_name(self) -> None:
        @dataclass
        class Referenced:
            x: str

        @dataclass
        class PlainRefHavingName:
            x: Referenced = field(metadata={"name": "NewName"})

        dclazz = PlainRefHavingName
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")

        xmlbody._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "properties",
            ignore={"title", "required", "description", "defs"},
        )
        assert schema.properties is not None
        prop = schema.properties["x"]
        self.assertEqual(schema.type, "object")

        # allOf is not supported in pydantic v2
        # https://github.com/pydantic/pydantic/issues/8161

        self.assertAllNoneExcept(prop, "xml", ignore={"title", "description", "ref"})
        # self.assertAllNoneExcept(prop, "xml", "allOf", ignore={"title", "description"})
        assert isinstance(prop.xml, XML)
        # assert isinstance(prop.allOf, list)
        self.assertAllNoneExcept(prop.xml, "name")

        self.assertEqual(prop.xml.name, mfield.metadata["name"])
        # self.assertLen(prop.allOf, 1)
        # self.assertAllNoneExcept(prop.allOf[0], "ref")

    def test_unnamed_obj_list(self) -> None:
        @dataclass
        class Referenced:
            x: str

        @dataclass
        class PlainListRefWithoutName:
            x: List[Referenced]

        dclazz = PlainListRefWithoutName
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")

        xmlbody._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema, "type", "properties", ignore={"title", "description", "required", "defs"}
        )
        self.assertEqual(schema.type, "object")
        assert isinstance(schema.properties, dict)
        prop = schema.properties["x"]

        self.assertAllNoneExcept(prop, "type", "items", ignore={"title", "description"})
        assert isinstance(prop.items, Schema)
        self.assertEqual(prop.type, "array")
        self.assertAllNoneExcept(prop.items, "ref")

    def test_named_obj_list(self) -> None:
        @dataclass
        class Referenced:
            x: str

        @dataclass
        class PlainListRefWithoutName:
            x: List[Referenced] = field(metadata={"name": "List"})

        dclazz = PlainListRefWithoutName
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")

        xmlbody._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema, "type", "properties", ignore={"title", "description", "required", "defs"}
        )
        assert isinstance(schema.properties, dict)
        prop = schema.properties["x"]
        self.assertEqual(schema.type, "object")

        self.assertAllNoneExcept(
            prop, "type", "items", "xml", ignore={"title", "description"}
        )
        assert prop.xml is not None
        assert isinstance(prop.items, Schema)
        self.assertEqual(prop.type, "array")
        self.assertAllNoneExcept(prop.items, "ref")
        self.assertAllNoneExcept(prop.xml, "name")

        self.assertEqual(prop.type, "array")
        self.assertEqual(prop.xml.name, mfield.metadata["name"])

    def test_wrapped_obj_list(self) -> None:
        @dataclass
        class Referenced:
            x: str

        @dataclass
        class PlainListRefWithoutName:
            x: List[Referenced] = field(metadata={"name": "obj", "wrapper": "Items"})

        dclazz = PlainListRefWithoutName
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")

        xmlbody._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema, "type", "properties", ignore={"title", "description", "required", "defs"}
        )
        self.assertEqual(schema.type, "object")
        assert schema.properties is not None
        prop = schema.properties["x"]

        self.assertAllNoneExcept(
            prop, "type", "items", "xml", ignore={"title", "description"}
        )
        assert isinstance(prop.xml, XML)
        assert isinstance(prop.items, Schema)
        self.assertAllNoneExcept(prop.xml, "name", "wrapped")
        self.assertAllNoneExcept(prop.items, "xml", "allOf")
        assert isinstance(prop.items.xml, XML)
        assert isinstance(prop.items.allOf, list)
        self.assertAllNoneExcept(prop.items.xml, "name")

        self.assertEqual(prop.type, "array")
        self.assertEqual(prop.xml.name, mfield.metadata["wrapper"])
        self.assertEqual(prop.xml.wrapped, True)
        self.assertLen(prop.items.allOf, 1)
        self.assertAllNoneExcept(prop.items.allOf[0], "ref")
        self.assertEqual(prop.items.xml.name, mfield.metadata["name"])

    def test_wrapped_type_list(self) -> None:
        @dataclass
        class WrappedTypeList:
            x: List[str] = field(metadata={"name": "plain", "wrapper": "Items"})

        dclazz = WrappedTypeList
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")
        xmlbody._add_field_schema(dclazz, mfield, schema, {})
        assert isinstance(schema.properties, dict)
        prop = schema.properties["x"]

        self.assertAllNoneExcept(
            schema, "type", "properties", ignore={"title", "description", "required"}
        )
        self.assertEqual(schema.type, "object")

        self.assertAllNoneExcept(
            prop, "type", "items", "xml", ignore={"title", "description"}
        )
        self.assertEqual(prop.type, "array")
        assert isinstance(prop.xml, XML)
        assert isinstance(prop.items, Schema)

        self.assertAllNoneExcept(prop.items, "type", "xml")
        self.assertEqual(prop.items.type, "string")
        assert isinstance(prop.items.xml, XML)

        self.assertAllNoneExcept(prop.items.xml, "name")
        self.assertEqual(prop.items.xml.name, mfield.metadata["name"])
        self.assertEqual(prop.xml.name, mfield.metadata["wrapper"])
        self.assertEqual(prop.xml.wrapped, True)

    def test_non_list_wrapper(self) -> None:
        @dataclass
        class NonListWrapper:
            x: str = field(metadata={"name": "obj", "wrapper": "Items"})

        dclazz = NonListWrapper
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")

        self.assertRaises(
            TypeError, xmlbody._add_field_schema, dclazz, mfield, schema, {}
        )

    def test_items_no_schema(self) -> None:
        @dataclass
        class WrappedTypeList:
            x: List[str] = field(metadata={"name": "plain", "wrapper": "Items"})

        dclazz = WrappedTypeList
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")

        self.assertAllNoneExcept(
            schema, "type", "properties", ignore={"title", "description", "required"}
        )
        assert isinstance(schema.properties, dict)
        prop = schema.properties["x"]
        assert isinstance(prop, Schema)

        self.assertEqual(prop.type, "array")
        assert isinstance(prop.items, Schema)
        prop.items = None
        self.assertRaises(
            TypeError, xmlbody._add_field_schema, dclazz, mfield, schema, {}
        )
