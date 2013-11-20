# -*- coding: UTF-8 -*-
from __future__ import unicode_literals, print_function, division
import hashlib
import traceback
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
from veil.utility.encoding import to_unicode

TWO_PLACES = Decimal('0.01')

def unique(iterable, idfunc=lambda x:x):
    seen = set()
    return [x for x in iterable if idfunc(x) not in seen and not seen.add(idfunc(x))]


def chunks(seq, size, padding=False, padding_element=None):
    """
    Yield successive n-sized chunks from seq.
    """
    if padding:
        remain = len(seq) % size
        if remain != 0:
            if isinstance(seq, basestring):
                assert isinstance(padding_element, basestring) and len(padding_element) == 1
                seq = '{}{}'.format(seq, padding_element * (size - remain))
            else:
                for i in xrange(0, size - remain):
                    seq.append(padding_element)
    for i in xrange(0, len(seq), size):
        yield seq[i: i + size]


def iter_file_in_chunks(file_object, chunk_size=8192):
    """
    Lazy function (generator) to read a file piece by piece.
    Default chunk size: 8k.
    """
    return iter(lambda: file_object.read(chunk_size), b'')


def calculate_file_md5_hash(file_object, reset_position=False, hex=True):
    """
    Calculate the md5 hash for this file.
    This reads through the entire file.
    """
    assert file_object is not None and file_object.tell() == 0
    try:
        m = hashlib.md5()
        for chunk in iter_file_in_chunks(file_object):
            m.update(chunk)
        return m.hexdigest() if hex else m.digest()
    finally:
        if reset_position:
            file_object.seek(0)


def round_money_half_up(d):
    return d.quantize(TWO_PLACES, ROUND_HALF_UP)


def round_money_floor(d):
    return d.quantize(TWO_PLACES, ROUND_FLOOR)


def remove_elements_without_value_from_dict(d):
    for key in list(d.keys()):
        if not d[key]:
            del d[key]


def list_toggled_bit_offsets(int_val):
    if not int_val: # None or 0
        return []
    toggled_offsets = []
    val = abs(int_val)
    offset = 1
    while True:
        mask = 1 << (offset -1)
        if val < mask:
            break
        if (val & mask) == mask:
            toggled_offsets.append(offset)
        offset += 1
    return toggled_offsets


def format_exception(exception_info):
    return to_unicode(b''.join(traceback.format_exception(*exception_info)))
