"""Tests specify correctness and failure behavior before the workbench is built."""
import json
from decimal import Decimal
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class NumericContract(unittest.TestCase):
    def setUp(self):
        from migration.runtime import Fields
        self.s = Fields([
            {'name':'ROW','root':'ROW','offset':0,'length':12,'kind':'group','scale':0},
            {'name':'ID','root':'ROW','offset':0,'length':6,'kind':'text','scale':0},
            {'name':'AMT','root':'ROW','offset':6,'length':6,'kind':'number','scale':2}])
    def test_leading_zero_identifier_is_not_a_number(self):
        self.s.set('ID','000007')
        self.assertEqual(self.s.get('ID'),'000007')
    def test_decimal_truncation_is_not_rounding(self):
        self.s.set('AMT',Decimal('123.456'))
        self.assertEqual(self.s.get('AMT'),Decimal('123.45'))
        self.assertEqual(self.s.raw('AMT'),'012345')
    def test_group_move_preserves_field_boundaries(self):
        self.s.set('ROW','ABC001000125')
        self.assertEqual(self.s.get('AMT'),Decimal('1.25'))
    def test_bad_numeric_bytes_are_not_silently_zero(self):
        self.s.set('ROW','ABC001XX0125')
        with self.assertRaises(ValueError): self.s.get('AMT')
    def test_unsigned_display_overflow_keeps_low_digits(self):
        self.s.set('AMT',Decimal('10001.25'))
        self.assertEqual(self.s.get('AMT'),Decimal('1.25'))

class ParserContract(unittest.TestCase):
    def test_unsupported_statement_is_not_discarded(self):
        from migration.compiler import parse_statements
        from migration.common import Blocked
        with self.assertRaises(Blocked): parse_statements('ALTER OLD-PARA TO PROCEED TO NEW-PARA.', 'demo.cbl')
    def test_nested_condition_retains_both_branches(self):
        from migration.compiler import parse_statements
        tree = parse_statements('IF FLAG = "X" MOVE 7 TO FEE ELSE COMPUTE FEE = AMOUNT / 100 END-IF.', 'demo.cbl')
        self.assertEqual(tree[0]['kind'],'if')
        self.assertEqual(tree[0]['yes'][0]['kind'],'move')
        self.assertEqual(tree[0]['no'][0]['kind'],'compute')
    def test_unknown_jcl_condition_blocks(self):
        from migration.discovery import parse_jcl
        from migration.common import Blocked
        with self.assertRaises(Blocked): parse_jcl('//J JOB\n//S EXEC PGM=TEST,COND=(4,LT)\n','J.jcl')
    def test_paths_cannot_escape_output_root(self):
        from migration.common import inside, Blocked
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(Blocked): inside(Path(t),'../outside.txt')
    def test_sql_decimal_storage_is_not_float(self):
        from migration.compiler import translate_ddl
        sql, schema = translate_ddl('CREATE TABLE T (ID CHAR(6) NOT NULL, AMT DECIMAL(15,2));')
        self.assertIn('TEXT',sql)
        self.assertNotIn('REAL',sql)
        self.assertEqual(schema['T']['AMT']['scale'],2)

class InventoryContract(unittest.TestCase):
    def test_excel_columns_are_read(self):
        from migration.inventory import read_inventory
        rows = read_inventory(ROOT/'sample'/'inventory.xlsx','Process')
        self.assertEqual(len(rows),6)
        self.assertEqual(rows[0]['job'],'JOB001')
        self.assertEqual(rows[-1]['program'],'TOTALS')

if __name__ == '__main__': unittest.main()

class ReferenceContract(unittest.TestCase):
    def test_by_reference_output_is_not_read_before_callee_writes(self):
        from migration.runtime import Fields
        layout=[{'name':'OUT','root':'OUT','offset':0,'length':6,'kind':'number','scale':0}]
        caller=Fields(layout)
        caller.buffers['OUT']=list('      ')
        callee=Fields([{'name':'RESULT','root':'RESULT','offset':0,'length':6,'kind':'number','scale':0}])
        callee.bind('RESULT',caller.reference('OUT'))
        callee.set('RESULT',7)
        self.assertEqual(caller.get('OUT'),Decimal(7))
    def test_aliasing_is_live_not_copy_in_copy_out(self):
        from migration.runtime import Fields
        f=lambda name:{'name':name,'root':name,'offset':0,'length':6,'kind':'number','scale':0}
        caller=Fields([f('X')]);callee=Fields([f('A'),f('B')])
        callee.bind('A',caller.reference('X'));callee.bind('B',caller.reference('X'))
        callee.set('A',99)
        self.assertEqual(callee.get('B'),Decimal(99))
