# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division
import logging

import lxml.objectify
from veil.model.collection import *
from veil.utility.http import *


API_URL = 'http://api.map.baidu.com/geoconv/v1/'
COORDS_COUNT_LIMIT = 100
JSON_OUTPUT = 'json'
XML_OUTPUT = 'xml'

LOGGER = logging.getLogger(__name__)


def convert_to_baidu_coord(coords, ak, sn=None, from_type=1, to_type=5, output=JSON_OUTPUT):
    if len(coords) > COORDS_COUNT_LIMIT:
        raise Exception('coords too much: limit is {}'.format(COORDS_COUNT_LIMIT))
    params = DictObject(coords=[';'.join(','.join(coord) for coord in coords)], ak=ak, sn=sn, to=to_type, output=output)
    params['from'] = from_type

    response = None
    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()
    except Exception:
        LOGGER.info('got exception when call convert to baidu coord: %(params)s, %(result)s', {
            'params': params,
            'result': response.content if response else ''
        })
    else:
        if output == JSON_OUTPUT:
            parsed_output = objectify(response.json())
        else:
            parsed_output = DictObject()
            root = lxml.objectify.fromstring(response)
            for e in root.iterchildren():
                if e.text:
                    parsed_output[e.tag] = e.text
        if parsed_output.status != 0:
            raise Exception('invalid output status when call convert to baidu coord: {}'.format(response.content))
        return parsed_output.result