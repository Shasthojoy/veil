from __future__ import unicode_literals, print_function, division
import logging

LOGGER = logging.getLogger(__name__)

def to_str(s):
    if isinstance(s, (str, bytes, type(None))):
        return s
    if isinstance(s, unicode):
        return s.encode('utf-8')
    raise Exception('to_str does not support {}'.format(type(s)))


def to_unicode(s, encoding=None, remedial_encoding=None):
    if isinstance(s, (unicode, type(None))):
        return s
    encoding = encoding or 'utf-8'
    try:
        return unicode(s, encoding=encoding)
    except UnicodeDecodeError:
        if remedial_encoding and remedial_encoding != encoding:
            LOGGER.warn('cannot decode s to unicode: %(s)s, %(encoding)s', {'s': s, 'encoding': encoding}, exc_info=1)
            return unicode(s, encoding=remedial_encoding)
        else:
            raise
