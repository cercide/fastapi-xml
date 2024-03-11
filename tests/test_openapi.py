#  type: ignore
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

import pydantic
from fastapi import APIRouter
from fastapi import FastAPI
from fastapi.openapi.models import Components
from fastapi.openapi.models import OpenAPI
from fastapi.openapi.models import Schema
from fastapi.openapi.models import XML
from pydantic import BaseModel
from pydantic import TypeAdapter
from pydantic.dataclasses import dataclass as pydantic_dataclass

from fastapi_xml import openapi


if TYPE_CHECKING:  # pragma: nocover
    from pydantic.dataclasses import PydanticDataclass


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
    def _get_schema(model: Union["PydanticDataclass"]) -> Schema:
        schema = TypeAdapter(model).json_schema(by_alias=True)
        return Schema(**schema)

    def test_named_attribute(self) -> None:
        @dataclass
        class NamedAttribute:
            x: str = field(metadata={"name": "XXX", "type": "Element"})

        dclazz = NamedAttribute
        model = pydantic_dataclass(dclazz)
        schema = self._get_schema(model)
        mfield = self._get_dataclass_field(dclazz, "x")

        openapi._add_model_schema(dclazz, schema, {})
        openapi._add_field_schema(dclazz, mfield, schema, {})

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

        openapi._add_model_schema(dclazz, schema, {})
        openapi._add_field_schema(dclazz, mfield, schema, {})

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

        openapi._add_model_schema(dclazz, schema, {})

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

        openapi._add_model_schema(dclazz, schema, {})

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

        openapi._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "properties",
            ignore={
                "title",
                "required",
                "description",
                "required",
                "properties",
                "defs",
            },
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

        openapi._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "properties",
            ignore={"title", "required", "description", "defs"},
        )
        assert schema.properties is not None
        prop = schema.properties["x"]
        print(prop.model_dump_json(indent=4))
        self.assertEqual(schema.type, "object")
        self.assertAllNoneExcept(prop, "xml", "ref", ignore={"title", "description"})
        self.assertIsInstance(prop.xml, XML)
        self.assertAllNoneExcept(prop.xml, "name")
        self.assertEqual(prop.xml.name, mfield.metadata["name"])

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

        openapi._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "properties",
            ignore={"title", "description", "required", "defs"},
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

        openapi._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "properties",
            ignore={"title", "description", "required", "defs"},
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

        openapi._add_field_schema(dclazz, mfield, schema, {})

        self.assertAllNoneExcept(
            schema,
            "type",
            "properties",
            ignore={"title", "description", "required", "defs"},
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
        openapi._add_field_schema(dclazz, mfield, schema, {})
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
            TypeError, openapi._add_field_schema, dclazz, mfield, schema, {}
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
            TypeError, openapi._add_field_schema, dclazz, mfield, schema, {}
        )

    def test_get_element_name_generator(self) -> None:
        """
        The test_get_element_name_generator function tests the
        :func:`fastapi_xml.xmlbody._get_element_name_generator` function.
        The test checks that if a class has an element name generator, it is returned by the function.
        If not, then the default element name generator is returned.
        """

        class Meta1:
            @staticmethod
            def element_name_generator(x: str) -> str:
                """dummy name generator."""
                return x.upper()

        class Meta2:
            pass

        g = openapi._get_element_name_generator(Meta1)
        self.assertEqual(g("test"), "TEST")
        g = openapi._get_element_name_generator(Meta2)
        self.assertEqual(g, openapi.DEFAULT_XML_CONTEXT.element_name_generator)

    def test_get_attribute_name_generator(self) -> None:
        """
        The test_get_attribute_name_generator function tests the
        :func:`fastapi_xml.xmlbody._get_attribute_name_generator` function.
        The test checks that if a class has an attribute name generator, it is returned by the function.
        If not, then the default attribute name generator is returned.
        """

        class Meta1:
            @staticmethod
            def attribute_name_generator(x: str):
                """dummy name generator."""
                return x.upper()

        class Meta2:
            pass

        g = openapi._get_attribute_name_generator(Meta1)
        self.assertEqual(g("test"), "TEST")
        g = openapi._get_attribute_name_generator(Meta2)
        self.assertEqual(g, openapi.DEFAULT_XML_CONTEXT.attribute_name_generator)

    def test_add_model_schema(self) -> None:
        """
        The test_add_model_schema function tests the
        :func:`fastapi_xml.xmlbody._add_model_schema` function.

        The test checks that the schema is an instance of Schema, and
        that it has a name, prefix, namespace and attribute.
        """

        @dataclass
        class Dummy:
            class Meta:
                name = "Foo"
                namespace = "http://testns"

            x: str

        test_schema = Schema()
        test_ns_map = {"http://testns": "bla"}
        openapi._add_model_schema(Dummy, test_schema, test_ns_map)
        self.assertIsInstance(test_schema.xml, XML)
        self.assertEqual(test_schema.xml.name, Dummy.Meta.name)
        self.assertEqual(test_schema.xml.prefix, "bla")
        self.assertEqual(test_schema.xml.namespace, "http://testns")
        self.assertIsNone(test_schema.xml.attribute)
        self.assertIsNone(test_schema.xml.wrapped)

    def test_is_xml_schema_empty(self) -> None:
        """The test_is_xml_schema_empty function tests the
        :func:`fastapi_xml.xmlbody._is_xml_schema_empty` function This test
        check an empty XML schema and each attribute."""
        self.assertTrue(openapi._is_xml_schema_empty(XML()))
        self.assertFalse(openapi._is_xml_schema_empty(XML(name="")))
        self.assertFalse(openapi._is_xml_schema_empty(XML(prefix="")))
        self.assertFalse(openapi._is_xml_schema_empty(XML(attribute=False)))
        self.assertFalse(openapi._is_xml_schema_empty(XML(wrapped=False)))

    def test_switch_ref_to_all_of__empty_xml(self) -> None:
        """
        The test_switch_ref_to_all_of__empty_xml function tests the
        :func:`fastapi_xml.xmlbody._switch_ref_to_all_of` function.
        This test assures that the function does not affect the xml schema object.
        """
        test_prop = Schema()
        test_xml = XML()
        self.assertIsNone(test_prop.xml)
        openapi._switch_ref_to_all_of(test_prop, test_xml)
        self.assertIsNone(test_prop.xml)
        self.assertIsNone(test_prop.allOf)
        self.assertIsNone(test_prop.ref)

    def test_switch_ref_to_all_of__non_empty_xml(self) -> None:
        """
        The test_switch_ref_to_all_of__non_empty_xml function tests the
        :func:`fastapi_xml.xmlbody.switch_ref_to_all_of` function.
        with a non-empty XML object as input. The test asserts that the XML object is not None, and that it has been
        assigned to the property's xml attribute.
        """
        test_prop = Schema()
        test_xml = XML(name="x")
        self.assertIsNone(test_prop.xml)
        openapi._switch_ref_to_all_of(test_prop, test_xml)
        self.assertIsNotNone(test_prop.xml)
        self.assertEqual(id(test_prop.xml), id(test_xml))
        self.assertIsNone(test_prop.allOf)
        self.assertIsNone(test_prop.ref)

    def test_switch_ref_to_all_of__existing_ref(self) -> None:
        """
        The test_switch_ref_to_all_of__existing_ref function tests the
        :func:`fastapi_xml.xmlbody._switch_ref_to_all_of` function.
        This test assures that the function places the $ref within the allOf property.
        """
        kwargs = {"$ref": "test_ref"}
        test_prop = Schema(**kwargs)
        test_xml = XML(name="x")
        self.assertIsNone(test_prop.xml)
        self.assertIsNotNone(test_prop.ref)
        openapi._switch_ref_to_all_of(test_prop, test_xml)
        self.assertIsNotNone(test_prop.xml)
        self.assertEqual(id(test_prop.xml), id(test_xml))
        self.assertIsInstance(test_prop.allOf, list)
        self.assertEqual(len(test_prop.allOf), 1)
        self.assertIsInstance(test_prop.allOf[0], Schema)
        self.assertEqual(test_prop.allOf[0].ref, "test_ref")
        self.assertIsNone(test_prop.ref)

    def test_add_field_schema(self) -> None:
        """The test_add_field_schema function tests the
        :func:`fastapi_xml.xmlbody._add_field_schema function` The test is
        incomplete, but it does check that a field can be added to an empty
        schema."""
        test_schema = Schema()
        openapi._add_field_schema(object, field(), test_schema, {})
        self.assertEqual(len(test_schema.model_dump(exclude_none=True)), 0)

    def test_get_route_models(self) -> None:
        """
        The test_get_route_models function tests the
        :func:`fastapi_xml.xmlbody._get_route_models` function.

        It validates that the function successfully returns the correct
        response Model.
        """

        @dataclass
        class TestModel:
            x: str

        router = APIRouter()

        @router.get("/", response_model=TestModel)
        def dummy_endpoint() -> None:  # pragma: no cover
            """a dummy endpoint."""
            pass

        app = FastAPI()
        app.include_router(router)
        schema = OpenAPI(**app.openapi())
        models = openapi._get_route_models(app, schema)
        self.assertEqual(len(models), 1)
        # fastapi converts the model into a pydantic dataclass. Hence, it is a different model
        # having the same attributes
        self.assertEqual(models[0].__name__, TestModel.__name__)

    def test_add_openapi_xml_schema(self) -> None:
        """
        The test_add_openapi_xml_schema function tests the
        :func:`fastapi_xml.xmlbody.add_openapi_xml_schema` function.

        It does so by creating a FastAPI app and adding an endpoint to
        it, then testing if the schema has been modified. The test also
        checks if the function returns None when components or its
        schemas are missing.
        """

        @pydantic.dataclasses.dataclass
        class TestModel:
            x: str

        router = APIRouter()

        @router.get("/", response_model=TestModel)
        def dummy_endpoint() -> None:  # pragma: no cover
            """a dummy endpoint."""
            pass

        test_app = FastAPI()
        test_app.include_router(router)

        # test if the schema has been modified
        test_app.openapi_schema = None
        test_openapi = OpenAPI(**test_app.openapi())
        self.assertTrue(openapi.add_openapi_xml_schema(test_app, test_openapi))

        # tests if the function returns None if components or its schemas are missing
        test_openapi = OpenAPI(**test_app.openapi())
        test_openapi.components = None
        self.assertFalse(openapi.add_openapi_xml_schema(test_app, test_openapi))
        test_openapi.components = Components()
        self.assertFalse(openapi.add_openapi_xml_schema(test_app, test_openapi))
