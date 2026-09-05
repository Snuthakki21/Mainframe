"""Retargeting must keep source definitions that the old SQLite schema discarded."""
import unittest
from migration.targets.schema import parse_schema, ddl, capabilities
from migration.common import Blocked
SOURCE='CREATE TABLE T (I SMALLINT NOT NULL, C CHAR(6) NOT NULL, V VARCHAR(8), D DECIMAL(31,12), PRIMARY KEY (I));'
class SchemaTests(unittest.TestCase):
    def test_source_width_and_type_are_preserved(self):
        s=parse_schema(SOURCE);self.assertEqual(s['T']['columns']['I']['source_type'],'SMALLINT')
        self.assertEqual(s['T']['primary_key'],['I'])
        self.assertEqual(s['T']['columns']['C']['source_type'],'CHAR')
    def test_oracle_ddl_preserves_precision_and_key(self):
        text=ddl(parse_schema(SOURCE),'oracle')
        self.assertIn('NUMBER(31,12)',text);self.assertIn('PRIMARY KEY',text);self.assertIn('CHAR(6 CHAR)',text)
    def test_bigquery_decimal_and_constraints_are_not_silently_weakened(self):
        s=parse_schema(SOURCE);text=ddl(s,'bigquery')
        self.assertIn('BIGNUMERIC(31,12)',text)
        self.assertTrue(any(x['code']=='PRIMARY_KEY_NOT_ENFORCED' for x in capabilities(s,'bigquery')))
    def test_sqlite_decimal_is_not_float(self):
        self.assertIn('"D" TEXT',ddl(parse_schema(SOURCE),'sqlite'))
    def test_unknown_constraint_not_discarded(self):
        with self.assertRaises(Blocked):parse_schema('CREATE TABLE T (I INTEGER UNIQUE);')
    def test_integer_range_preserved(self):
        text=ddl(parse_schema(SOURCE),'oracle');self.assertIn('-32768',text);self.assertIn('32767',text)
