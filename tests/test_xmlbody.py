#  type: ignore
import unittest

from fastapi_xml import XmlBody


class TestXmlBody(unittest.TestCase):
    def test_run_xmlbody(self):
        XmlBody()
