from __future__ import unicode_literals, print_function, division
from veil.development.test import *
from .table_dependency import check_writable_table_dependencies
from .table_dependency import check_readable_table_dependencies
from .table_dependency import disable_logging

class CheckWritableTableDependencyTest(TestCase):
    def setUp(self):
        super(CheckWritableTableDependencyTest, self).setUp()
        disable_logging()

    def test_select(self):
        check_write({}, 'a', 'SELECT xxx FROM...')

    def test_unexpected_update(self):
        with self.assertRaises(Exception):
            check_write({}, 'a', 'UPDATE xxx SET...')

    def test_expected_update(self):
        check_write({'a': ['xxx']}, 'a', 'UPDATE xxx SET...')

    def test_unexpected_insert(self):
        with self.assertRaises(Exception):
            check_write({}, 'a', 'INSERT xxx(col1, col2...')
        with self.assertRaises(Exception):
            check_write({}, 'a', 'INSERT  xxx (col1, col2...')

    def test_unexpected_insert_into(self):
        with self.assertRaises(Exception):
            check_write({}, 'a', 'INSERT INTO xxx(col1, col2...')
        with self.assertRaises(Exception):
            check_write({}, 'a', 'INSERT INTO  xxx (col1, col2...')

    def test_expected_insert_into(self):
        check_write({'a': ['xxx']}, 'a', 'INSERT INTO xxx(col1, col2...')

    def test_unexpected_delete_from(self):
        with self.assertRaises(Exception):
            check_write({}, 'a', 'DELETE FROM xxx WHERE...')


def check_write(writable_tables, component_name, sql):
    writable_tables_as_in_xxx = {k: [('xxx', e) for e in v] for k, v in writable_tables.items()}
    check_writable_table_dependencies(writable_tables_as_in_xxx, component_name, 'xxx', sql)


class CheckReadableTableDependencyTest(TestCase):
    def setUp(self):
        super(CheckReadableTableDependencyTest, self).setUp()
        disable_logging()

    def test_expected_select(self):
        check_read({'a': ['xxx']}, 'a', 'SELECT * FROM xxx WHERE ...')

    def test_unexpected_select(self):
        with self.assertRaises(Exception):
            check_read({}, 'a', 'SELECT * FROM xxx WHERE ...')

    def test_multiple_from(self):
        check_read({'a': ['xxx', 'yyy']}, 'a', 'SELECT * FROM xxx, yyy WHERE ...')

    def test_multiple_from_with_as(self):
        check_read({'a': ['xxx', 'yyy']}, 'a', 'SELECT * FROM xxx AS x, yyy AS y WHERE ...')

    def test_left_join(self):
        check_read({'a': ['xxx', 'yyy']}, 'a',
            'SELECT * FROM xxx LEFT JOIN yyy ON x=y WHERE ...')

    def test_unexpected_left_join(self):
        with self.assertRaises(Exception):
            check_read({'a': ['xxx']}, 'a', 'SELECT * FROM xxx LEFT JOIN yyy ON x=y WHERE ...')

    def test_unexpected_multiple_left_join(self):
        with self.assertRaises(Exception):
            check_read({'a': ['xxx', 'yyy']}, 'a',
                '''
                SELECT * FROM xxx
                LEFT JOIN yyy ON x=y
                LEFT JOIN zzz ON x=z
                WHERE ...
                ''')

    def test_right_join(self):
        check_read({'a': ['xxx', 'yyy']}, 'a',
            'SELECT * FROM xxx RIGHT OUTER JOIN yyy ON x=y WHERE ...')

    def test_inner_join(self):
        check_read({'a': ['xxx', 'yyy']}, 'a',
            'SELECT * FROM xxx INNER JOIN yyy ON x=y WHERE ...')

    def test_inner_join_then_left_join(self):
        check_read({'a': ['xxx', 'yyy', 'zzz']}, 'a',
            '''
            SELECT * FROM xxx
            INNER JOIN yyy ON x=y
            LEFT JOIN zzz ON x=z
            WHERE ...
            ''')

    def test_group_by(self):
        check_read({'a': ['xxx']}, 'a', 'SELECT * FROM xxx GROUP BY ...')

    def test_order_by(self):
        check_read({'a': ['xxx']}, 'a', 'SELECT * FROM xxx ORDER BY ...')

    def test_limit(self):
        check_read({'a': ['xxx']}, 'a', 'SELECT * FROM xxx LIMIT ...')

    def test_implicit_as(self):
        check_read({'a': ['xxx']}, 'a', 'SELECT * FROM xxx x WHERE ...')

    def test_subquery(self):
        check_read({'a': ['xxx']}, 'a', 'SELECT * FROM (SELECT c1, c2 FROM xxx x) AS zzz WHERE ...')
        check_read({'a': ['xxx']}, 'a', 'SELECT * FROM (SELECT c1, RANK() OVER (PARTITION BY c2) rank FROM xxx x) AS zzz WHERE ...')

    def test_subquery_with_joins(self):
        check_read({'a': ['xxx', 'yyy']}, 'a', 'SELECT * FROM (SELECT c1, RANK() OVER (PARTITION BY c2) rank FROM xxx x INNER JOIN yyy y) AS zzz WHERE ...')
        check_read({'a': ['product_variant', 'comment']}, 'a', '''
            SELECT *
            FROM (
                SELECT pv.product_id,
                    c.content
                FROM product_variant pv INNER JOIN comment c ON pv.id = c.product_variant_id
                WHERE pv.product_id IN (100, 200) AND c.visible
                ) psrc
            WHERE rank = 1
            ''')

    def test_join_start_with_subquery(self):
        check_read({'a': ['xxx', 'zzz']}, 'a', 'SELECT * FROM (SELECT c1, c2 FROM xxx x) AS yyy INNER JOIN zzz ON y=z WHERE ...')

    def test_joined_subquery(self):
        check_read({'a': ['yyy', 'xxx']}, 'a', 'SELECT * FROM yyy INNER JOIN (SELECT c1, c2 FROM xxx x) AS zzz ON y=z WHERE ...')


def check_read(readable_tables, component_name, sql):
    readable_tables_as_in_purpose = {k: [('purpose', e) for e in v] for k, v in readable_tables.items()}
    check_readable_table_dependencies(readable_tables_as_in_purpose, component_name, 'purpose', sql)
