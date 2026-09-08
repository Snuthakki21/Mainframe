"""Source-linked Markdown process inventories accept documentation, never guess rows."""
from pathlib import Path
import tempfile
import unittest

from migration.common import Blocked
from migration.inventory import read_inventory


class MarkdownInventoryContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'process.md'

    def read(self, text, suffix='.md'):
        self.path = self.path.with_suffix(suffix)
        self.path.write_bytes(text.encode('utf-8'))
        return read_inventory(self.path)

    def assert_blocked(self, text, fragment, line=None):
        with self.assertRaises(Blocked) as caught:
            self.read(text)
        self.assertEqual(caught.exception.code, 'INVENTORY')
        self.assertIn(fragment, str(caught.exception))
        if line is not None:
            self.assertIn(f'line {line}', str(caught.exception))
            self.assertEqual(caught.exception.source, f'{self.path}:{line}')

    def test_composer_jobs_sections_and_partial_tables_keep_order_and_provenance(self):
        rows = self.read(
            '# SN002DA Job Flow Documentation\n'
            'Source: SN002DA_steps.xlsx [1-e8a316]\n\n'
            '# Job: ISNSOB\n\n'
            '| Step | Program | Input | Output |\n'
            '| --- | --- | --- | --- |\n'
            '| STEP0 | NONE | NONE | NONE |\n'
            '| STEP010 | SNB210 | NONE | INTSN.I.#RCYCL.SINVEXTR.R0008.D260821 |\n'
            '| STEP020 | SNB215 | INTSN.I.#RCYCL.SINVEXTR.R0008.D260821 | NONE |\n\n'
            '---\n\n'
            '# Job: ISNBBGSA\n'
            '## Input File Acquisition\n\n'
            '| Step | Program | Output |\n'
            '| --- | --- | --- |\n'
            '| STEPBLX | WEDELX | INTSN.I.#SALES.SBLBOOK.R0008.D260821 |\n\n'
            '## Qualification Processing\n\n'
            '| Step | Program | Description |\n'
            '| --- | --- | --- |\n'
            '| STEP103 | SORT | Sort BB Book file |\n'
            '| STEP104 | SNQUALR4 | Qualify BB records and create BBAS qualified outputs |\n')
        self.assertEqual([(r['job'], r['step']) for r in rows], [
            ('ISNSOB', 'STEP0'), ('ISNSOB', 'STEP010'), ('ISNSOB', 'STEP020'),
            ('ISNBBGSA', 'STEPBLX'), ('ISNBBGSA', 'STEP103'), ('ISNBBGSA', 'STEP104')])
        self.assertEqual(rows[0]['program'], 'NONE')
        self.assertTrue(rows[0]['documentation_only'])
        self.assertEqual(rows[0]['inputs'], [])
        self.assertEqual(rows[0]['outputs'], [])
        self.assertFalse(rows[1]['documentation_only'])
        self.assertEqual(rows[1]['outputs'], ['INTSN.I.#RCYCL.SINVEXTR.R0008.D260821'])
        self.assertEqual(rows[3]['row'], 19)
        self.assertEqual(rows[3]['source'], str(self.path))
        self.assertEqual(rows[3]['section'], 'Input File Acquisition')
        self.assertEqual(rows[3]['fields_present'], ['step', 'program', 'output'])
        self.assertEqual(rows[4]['description'], 'Sort BB Book file')
        self.assertEqual(rows[4]['fields_present'], ['step', 'program', 'description'])
        self.assertEqual(rows[4]['inputs'], [])
        self.assertEqual(rows[4]['outputs'], [])

    def test_bom_crlf_alignment_inline_formatting_and_dataset_separators(self):
        rows = self.read(
            '\ufeff# **Job:** `job001`\r\n'
            'Step Name | **Program Name** | Inputs | Outputs | Description\r\n'
            ':--- | :---: | ---: | --- | ---\r\n'
            '**step010** | `reader` | `in.one`; **in.two**<BR/>N/A | -;<br />`out.one` | Merge \\| sort\r\n',
            '.markdown')
        row = rows[0]
        self.assertEqual((row['job'], row['step'], row['program']), ('JOB001', 'STEP010', 'READER'))
        self.assertEqual(row['inputs'], ['IN.ONE', 'IN.TWO'])
        self.assertEqual(row['outputs'], ['OUT.ONE'])
        self.assertEqual(row['description'], 'Merge | sort')
        self.assertEqual(row['row'], 4)

    def test_job_column_supports_repeated_blank_job_cells(self):
        rows = self.read(
            '# Process\n'
            '| Job | Step | Program | Input | Output |\n'
            '| --- | --- | --- | --- | --- |\n'
            '| job001 | s1 | reader | input | output |\n'
            '| | s2 | writer | output | final |\n'
            '| job002 | s1 | reader | final | none |\n')
        self.assertEqual([r['job'] for r in rows], ['JOB001', 'JOB001', 'JOB002'])
        self.assertEqual(rows[-1]['section'], '')

    def test_none_program_with_datasets_is_not_a_documentation_only_row(self):
        rows = self.read('# Job: J\n| Step | Program | Output |\n| --- | --- | --- |\n| S | NONE | DATA.OUT |\n')
        self.assertFalse(rows[0]['documentation_only'])
        self.assertEqual(rows[0]['program'], 'NONE')

    def test_empty_io_columns_are_explicitly_documented(self):
        row = self.read('# Job: J\n| Step | Program | Input | Output |\n| --- | --- | --- | --- |\n| S | P | | |\n')[0]
        self.assertEqual(row['inputs'], [])
        self.assertEqual(row['outputs'], [])
        self.assertIn('input', row['fields_present'])
        self.assertIn('output', row['fields_present'])

    def test_unknown_documentation_columns_are_retained(self):
        row = self.read('# Job: J\n| Step | Program | Destination |\n| --- | --- | --- |\n| S | P | Business archive |\n')[0]
        self.assertEqual(row['extra_fields'], {'destination': 'Business archive'})

    def test_fenced_example_and_unrelated_tables_do_not_create_steps(self):
        rows = self.read(
            '```markdown\n# Job: EXAMPLE\n| Step | Program |\n| --- | --- |\n| S | P |\n```\n'
            '| Attribute | Value |\n| --- | --- |\n| Program | Description |\n\n'
            '# Job: REAL\n| Step | Program |\n| --- | --- |\n| S | P |\n')
        self.assertEqual([r['job'] for r in rows], ['REAL'])

    def test_duplicate_steps_across_sections_are_blocked_at_second_row(self):
        self.assert_blocked(
            '# Job: J\n## First\n| Step | Program |\n| --- | --- |\n| S | P |\n\n'
            '## Second\n| Step | Program |\n| --- | --- |\n| s | p |\n',
            'more than once', 10)

    def test_malformed_row_is_not_silently_dropped(self):
        self.assert_blocked('# Job: J\n| Step | Program | Output |\n| --- | --- | --- |\n| S | P |\n', '3 cells', 4)

    def test_physical_wrapping_is_not_guessed(self):
        self.assert_blocked('# Job: J\n| Step | Program | Output |\n| --- | --- | --- |\n| S | P |\nDATA.OUT |\n', '3 cells', 4)

    def test_missing_program_column_is_blocked(self):
        self.assert_blocked('# Job: J\n| Step | Description |\n| --- | --- |\n| S | Text |\n', 'Program', 2)

    def test_missing_program_value_is_blocked(self):
        self.assert_blocked('# Job: J\n| Step | Program |\n| --- | --- |\n| S | |\n', 'Program', 4)

    def test_table_without_job_context_is_blocked(self):
        self.assert_blocked('# Process\n| Step | Program |\n| --- | --- |\n| S | P |\n', 'Job', 4)

    def test_conflicting_job_heading_and_column_is_blocked(self):
        self.assert_blocked('# Job: J\n| Job | Step | Program |\n| --- | --- | --- |\n| OTHER | S | P |\n', 'differs', 4)

    def test_invalid_member_name_is_blocked(self):
        self.assert_blocked('# Job: J\n| Step | Program |\n| --- | --- |\n| S | SOME PROGRAM |\n', 'unsupported', 4)

    def test_duplicate_alias_headers_are_blocked(self):
        self.assert_blocked('# Job: J\n| Step | Program | Input | Inputs |\n| --- | --- | --- | --- |\n| S | P | A | B |\n', 'duplicate', 2)

    def test_missing_separator_is_blocked(self):
        self.assert_blocked('# Job: J\n| Step | Program |\n| S | P |\n', 'separator', 2)

    def test_no_recognized_table_is_blocked(self):
        self.assert_blocked('# Process\nSome text.\n', 'no recognized', 1)

    def test_recognized_empty_table_is_blocked(self):
        self.assert_blocked('# Job: J\n| Step | Program |\n| --- | --- |\n', 'Job J has no process rows', 1)

    def test_blank_line_does_not_silently_drop_a_following_step(self):
        self.assert_blocked('# Job: J\n| Step | Program |\n| --- | --- |\n| S1 | P1 |\n\n| S2 | P2 |\n',
                            'orphan', 6)

    def test_prose_does_not_silently_drop_a_following_step(self):
        self.assert_blocked('# Job: J\n| Step | Program |\n| --- | --- |\n| S1 | P1 |\n'
                            'The next stage follows.\n| S2 | P2 |\n', 'orphan', 6)

    def test_orphan_step_with_separator_cannot_be_mistaken_for_unrelated_table(self):
        self.assert_blocked('# Job: J\n| Step | Program |\n| --- | --- |\n| S1 | P1 |\n\n'
                            '| S2 | P2 |\n| --- | --- |\n| S3 | P3 |\n', 'orphan', 6)

    def test_incomplete_orphan_step_with_separator_is_not_discarded(self):
        self.assert_blocked('# Job: J\n| Step | Program |\n| --- | --- |\n| S1 | P1 |\n\n'
                            '| S2 | |\n| --- | --- |\n| S3 | P3 |\n', 'orphan', 6)

    def test_empty_declared_job_before_next_job_is_blocked_at_heading(self):
        self.assert_blocked('# Job: EMPTY\nPending documentation.\n# Job: REAL\n'
                            '| Step | Program |\n| --- | --- |\n| S | P |\n', 'Job EMPTY has no process rows', 1)

    def test_empty_declared_job_at_end_is_blocked_at_heading(self):
        self.assert_blocked('# Job: REAL\n| Step | Program |\n| --- | --- |\n| S | P |\n'
                            '# Job: EMPTY\nPending documentation.\n', 'Job EMPTY has no process rows', 5)

    def test_job_name_ending_hash_is_preserved_and_atx_closing_markup_is_removed(self):
        rows = self.read('# Job: JOB# ###\n| Step | Program |\n| --- | --- |\n| S | P |\n'
                         '# Job: OTHER#\n| Step | Program |\n| --- | --- |\n| S | P |\n')
        self.assertEqual([row['job'] for row in rows], ['JOB#', 'OTHER#'])

    def test_invalid_utf8_is_a_readable_inventory_error(self):
        self.path.write_bytes(b'\xff\xfe')
        with self.assertRaises(Blocked) as caught:
            read_inventory(self.path)
        self.assertEqual(caught.exception.code, 'INVENTORY')
        self.assertIn('UTF-8', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
