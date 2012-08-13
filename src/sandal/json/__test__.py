from __future__ import unicode_literals, print_function, division
from datetime import datetime
import pytz
from unittest.case import TestCase
from ._json import dumps
from ._json import loads

class CustomJSONEncoderDecoderTest(TestCase):
    def test(self):
        naive_now = datetime.now()
        aware_now = datetime.now(pytz.utc)
        for now in [naive_now, aware_now]:
            for obj in [now, now.date(), now.timetz(), now.time()]:
                encoded = dumps(obj)
                decoded = loads(encoded)
                self.assertEqual(obj, decoded)

    def test_in_list(self):
        naive_now = datetime.now()
        aware_now = datetime.now(pytz.utc)
        for now in [naive_now, aware_now]:
            for obj in [now, now.date(), now.timetz(), now.time()]:
                to_encode = [1, obj]
                encoded = dumps(to_encode)
                decoded = loads(encoded)
                self.assertEqual(to_encode, decoded)

    def test_in_dict(self):
        naive_now = datetime.now()
        aware_now = datetime.now(pytz.utc)
        for now in [naive_now, aware_now]:
            for obj in [now, now.date(), now.timetz(), now.time()]:
                to_encode = dict(a=1, b=obj)
                encoded = dumps(to_encode)
                decoded = loads(encoded)
                self.assertEqual(to_encode, decoded)

    def test_complex(self):
        naive_now = datetime.now()
        aware_now = datetime.now(pytz.utc)
        for now in [naive_now, aware_now]:
            for obj in [now, now.date(), now.timetz(), now.time()]:
                to_encode = dict(a=1, b=obj, c=dict(c1=2, c2=obj), d=[3, obj])
                encoded = dumps(to_encode)
                decoded = loads(encoded)
                self.assertEqual(to_encode, decoded)
