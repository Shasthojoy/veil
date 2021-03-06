from __future__ import unicode_literals, print_function, division
from unittest.case import TestCase
from .collection import DictObject


class DictObjectTest(TestCase):
    def test_get_set(self):
        o = DictObject()
        o['hello'] = 'world'
        self.assertEqual('world', o.hello)
        o.world = 'hello'
        self.assertEqual('hello', o['world'])

    def test_in(self):
        o = DictObject()
        o['hello'] = 'world'
        self.assertIn('hello', o)
        self.assertNotIn('world', o)

    def test_hasattr(self):
        self.assertFalse(hasattr(DictObject(), 'hello'))
        self.assertTrue(hasattr(DictObject(hello='world'), 'hello'))

    def test_get_not_existing_attribute(self):
        with self.assertRaises(AttributeError):
            DictObject().hello
