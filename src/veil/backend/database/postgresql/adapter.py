from __future__ import unicode_literals, print_function, division
from contextlib import closing
from logging import getLogger
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED
from psycopg2.extras import NamedTupleCursor
from psycopg2.extras import register_uuid
from psycopg2.extensions import cursor as NormalCursor
from psycopg2 import OperationalError
from veil.model.collection import *
from veil.utility.json import *

LOGGER = getLogger(__name__)

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)
psycopg2.extensions.register_type(register_uuid())


class CustomJsonAdapter(psycopg2.extras.Json):
    def dumps(self, obj):
        return to_readable_json(obj) if obj.get('readable', True) else to_json(obj)

psycopg2.extensions.register_adapter(dict, CustomJsonAdapter)
psycopg2.extras.register_default_json(globally=True, loads=lambda obj: objectify(from_json(obj)))


class PostgresqlAdapter(object):
    def __init__(self, host, port, database, user, password, schema):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.schema = schema
        self.conn = self._get_conn()

    def _get_conn(self):
        conn = None
        try:
            conn = psycopg2.connect(host=self.host, port=self.port, database=self.database, user=self.user, password=self.password)
            conn.set_session(isolation_level=ISOLATION_LEVEL_READ_COMMITTED, autocommit=True)
            if self.schema:
                with closing(conn.cursor(cursor_factory=NormalCursor)) as c:
                    c.execute('SET search_path TO {}'.format(self.schema))
        except:
            LOGGER.critical('Cannot connect to database: %(adapter_with_connection_parameters)s', {'adapter_with_connection_parameters': repr(self)},
                exc_info=1)
            try:
                raise
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        LOGGER.exception('Cannot close database connection')
        else:
            return conn

    def reconnect_if_broken_per_verification(self, sql='SELECT 1'):
        try:
            with closing(self.conn.cursor(cursor_factory=NormalCursor)) as cur:
                cur.execute(sql)
        except Exception:
            LOGGER.warn('failed in verifying database connection', exc_info=1)
            self._reconnect()

    def reconnect_if_broken_per_exception(self, e):
        return self._reconnect() if isinstance(e, OperationalError) else False

    def _reconnect(self):
        LOGGER.info('Reconnect now: %(connection)s', {'connection': self})
        try:
            self.close()
        except Exception:
            LOGGER.exception('Cannot close database connection')
        try:
            self.conn = self._get_conn()
        except Exception:
            LOGGER.exception('failed to reconnect')
            return False
        else:
            return True

    def _reconnect_if_broken_per_lightweight_detection(self):
        """
        lightweight detection is supported by the driver library psycopg2
        """
        if self.conn.closed:
            LOGGER.warn('Detected database connection had been closed, reconnect now: %(connection)s', {'connection': self})
            self.conn = self._get_conn()

    @property
    def autocommit(self):
        return self.conn.autocommit

    @autocommit.setter
    def autocommit(self, on_off):
        self.conn.autocommit = on_off

    def rollback_transaction(self):
        self.conn.rollback()

    def commit_transaction(self):
        self.conn.commit()

    def close(self):
        if not self.conn.closed:
            self.conn.close()

    def cursor(self, returns_dict_object=True, primary_keys=False, **kwargs):
        self._reconnect_if_broken_per_lightweight_detection()
        cursor = self.conn.cursor(cursor_factory=NamedTupleCursor if returns_dict_object else NormalCursor, **kwargs)
        if returns_dict_object:
            return ReturningDictObjectCursor(cursor, primary_keys)
        else:
            return cursor

    def __repr__(self):
        return 'Postgresql adapter {} with connection parameters {}'.format(self.__class__.__name__,
            dict(host=self.host, port=self.port, database=self.database, user=self.user))


class ReturningDictObjectCursor(object):
    def __init__(self, cursor, primary_keys):
        self.cursor = cursor
        self.primary_keys = primary_keys

    def fetchone(self):
        return self.to_dict_object(self.cursor.fetchone())

    def fetchmany(self, size=None):
        return [self.to_dict_object(row) for row in self.cursor.fetchmany(size)]

    def fetchall(self):
        return [self.to_dict_object(row) for row in self.cursor.fetchall()]

    def to_dict_object(self, row):
        return Entity(row._asdict(), primary_keys=self.primary_keys) if self.primary_keys else DictObject(row._asdict())

    def __iter__(self):
        while 1:
            yield self.to_dict_object(self.cursor.next())

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return getattr(self, attr)
        return getattr(self.cursor, attr)